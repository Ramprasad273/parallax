"""GitHub Actions PR Comment and Step Summary Runner for Parallax."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from parallax.cli.formatters.markdown import MarkdownFormatter
from parallax.core.ast_diff import ASTDiffEngine
from parallax.core.dbt_manifest import DbtManifest, ManifestError
from parallax.core.git import GitResolver
from parallax.core.lineage import LineageGraph
from parallax.core.logging import logger, setup_logging
from parallax.core.models import (
    DownstreamNode,
    ExposureNode,
    ModelASTDiff,
    RiskSeverity,
)
from parallax.core.risk_engine import RiskEngine


class GitHubActionRunner:
    """Handles GitHub PR comments and Step Summary publishing via native REST API."""

    def __init__(self, token: str | None = None, api_url: str = "https://api.github.com") -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
        self.api_url = api_url.rstrip("/")

    def get_pr_metadata(self) -> tuple[str | None, int | None]:
        """Extract repo (owner/repo) and pull request number from GitHub environment."""
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path or not Path(event_path).is_file():
            # Check direct environment inputs
            repo = os.environ.get("GITHUB_REPOSITORY")
            pr_num_str = os.environ.get("PR_NUMBER")
            pr_num = int(pr_num_str) if pr_num_str and pr_num_str.isdigit() else None
            return repo, pr_num

        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event_data: dict[str, Any] = json.load(f)
            repo = event_data.get("repository", {}).get("full_name") or os.environ.get(
                "GITHUB_REPOSITORY"
            )
            pr_num = event_data.get("pull_request", {}).get("number")
            return repo, pr_num
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to parse GITHUB_EVENT_PATH: %s", e)
            return None, None

    def write_step_summary(self, markdown_content: str) -> None:
        """Export markdown report to $GITHUB_STEP_SUMMARY."""
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return

        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n{markdown_content}\n")
            logger.debug("Successfully wrote to GITHUB_STEP_SUMMARY.")
        except OSError as e:
            logger.warning("Failed writing to GITHUB_STEP_SUMMARY: %s", e)

    def post_or_update_pr_comment(self, repo: str, pr_number: int, markdown_content: str) -> bool:
        """Post a new comment or update the existing pinned comment in place."""
        if not self.token:
            logger.warning("No GITHUB_TOKEN supplied. Skipping PR comment creation.")
            return False

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Parallax-CI",
        }

        # 1. Fetch existing issue comments
        list_url = f"{self.api_url}/repos/{repo}/issues/{pr_number}/comments"
        req = urllib.request.Request(list_url, headers=headers, method="GET")

        existing_comment_id: int | None = None
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                comments: list[dict[str, Any]] = json.loads(resp.read().decode("utf-8"))
                for c in comments:
                    body = c.get("body", "")
                    if MarkdownFormatter.COMMENT_MARKER in body:
                        existing_comment_id = c.get("id")
                        break
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to list PR comments: %s", e)

        # 2. Update existing or create new
        # Cap markdown length at ~60k to prevent GitHub API 422 errors (max 65,536 chars)
        comment_body = markdown_content
        if len(comment_body) > 60000:
            comment_body = (
                comment_body[:58000]
                + "\n\n> **[Note]** Output truncated due to GitHub PR comment size limits (65k chars). "
                + "See the Step Summary or HTML artifact for the complete report."
            )
        payload = json.dumps({"body": comment_body}).encode("utf-8")

        if existing_comment_id:
            patch_url = f"{self.api_url}/repos/{repo}/issues/comments/{existing_comment_id}"
            req = urllib.request.Request(patch_url, data=payload, headers=headers, method="PATCH")
            action = f"updated comment #{existing_comment_id}"
        else:
            post_url = f"{self.api_url}/repos/{repo}/issues/{pr_number}/comments"
            req = urllib.request.Request(post_url, data=payload, headers=headers, method="POST")
            action = "created new comment"

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201):
                    logger.info("Successfully %s on PR #%d.", action, pr_number)
                    return True
        except (urllib.error.URLError, OSError) as e:
            logger.error("Failed to post/update PR comment: %s", e)
            return False

        return False


def run_action() -> None:
    """Main entrypoint when executed inside a GitHub Action runner."""
    setup_logging(verbose=True)

    manifest_path = os.environ.get("INPUT_MANIFEST", "target/manifest.json")
    base_ref = os.environ.get("INPUT_BASE", "origin/main")
    head_ref = os.environ.get("INPUT_HEAD", "HEAD")
    dialect = os.environ.get("INPUT_DIALECT", "snowflake")
    fail_on_str = os.environ.get("INPUT_FAIL_ON", "CRITICAL").upper()
    fail_on = (
        RiskSeverity(fail_on_str)
        if fail_on_str in RiskSeverity.__members__
        else RiskSeverity.CRITICAL
    )

    # 1. Git resolution
    resolver = GitResolver()
    changed_files = resolver.get_changed_sql_files(
        base_ref=base_ref, head_ref=head_ref, include_working_tree=False
    )

    if not changed_files:
        logger.info("No modified .sql files found in PR diff. CI passed.")
        sys.exit(0)

    # 2. AST Diffing
    ast_engine = ASTDiffEngine(default_dialect=dialect)
    ast_diffs: list[ModelASTDiff] = []
    dropped_cols_map: dict[str, list[str]] = {}
    for cf in changed_files:
        diff = ast_engine.diff_model(
            model_name=Path(cf.path).stem,
            file_path=cf.path,
            base_sql=cf.base_content,
            head_sql=cf.head_content,
            dialect=dialect,
        )
        ast_diffs.append(diff)
        if diff.dropped_columns:
            dropped_cols_map[diff.model_name] = diff.dropped_columns

    # 3. Lineage
    downstream_models: list[DownstreamNode] = []
    impacted_exposures: list[ExposureNode] = []
    dag_edges: list[tuple[str, str]] = []
    max_depth = 0
    try:
        manifest = DbtManifest.from_file(manifest_path)
        lineage = LineageGraph(manifest)
        mod_ids = [
            manifest.get_model_id_by_path(cf.path)
            or manifest.get_model_id_by_name(Path(cf.path).stem)
            or ""
            for cf in changed_files
        ]
        valid_mod_ids = [m for m in mod_ids if m]
        for cf in changed_files:
            uid = manifest.get_model_id_by_path(cf.path) or manifest.get_model_id_by_name(Path(cf.path).stem)
            m_name = Path(cf.path).stem
            if uid and m_name in dropped_cols_map:
                dropped_cols_map[uid] = dropped_cols_map[m_name]
        downstream_models, impacted_exposures, max_depth = lineage.get_downstream_blast_radius(
            valid_mod_ids,
            dropped_or_modified_columns=dropped_cols_map,
            dialect=dialect,
        )
        dag_edges = lineage.get_subgraph_edges(valid_mod_ids)
    except (ManifestError, OSError, ValueError) as e:
        logger.warning("Manifest parsing error: %s", e)

    # 4. Risk
    risk_engine = RiskEngine()
    report = risk_engine.evaluate(
        modified_models=[cf.path for cf in changed_files],
        ast_diffs=ast_diffs,
        downstream_models=downstream_models,
        impacted_exposures=impacted_exposures,
        max_dag_depth=max_depth,
        dag_edges=dag_edges,
    )

    markdown = MarkdownFormatter.render(report)

    # 5. Export to Step Summary & PR Comment
    runner = GitHubActionRunner()
    runner.write_step_summary(markdown)

    repo, pr_number = runner.get_pr_metadata()
    # Zero-noise rule: Only comment if there is real risk
    if repo and pr_number and (report.risk_severity != RiskSeverity.LOW or bool(downstream_models)):
        runner.post_or_update_pr_comment(repo, pr_number, markdown)

    # 6. CI Gating
    if fail_on != RiskSeverity.NEVER and report.risk_severity >= fail_on:
        logger.error(
            "Blocking PR: %s meets or exceeds failure threshold %s",
            report.risk_severity.value,
            fail_on.value,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    run_action()
