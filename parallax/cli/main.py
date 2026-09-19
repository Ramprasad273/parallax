"""Command-line interface entrypoint for Parallax."""

import io
import sys
import time
from pathlib import Path

if sys.platform == "win32":  # pragma: no cover
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation, OSError):
        pass

import click

from parallax import __version__
from parallax.cli.formatters.html import HTMLFormatter
from parallax.cli.formatters.markdown import MarkdownFormatter
from parallax.cli.formatters.terminal import TerminalFormatter
from parallax.core.ast_diff import ASTDiffEngine
from parallax.core.config import ParallaxConfig
from parallax.core.dbt_manifest import DbtManifest, ManifestError
from parallax.core.git import GitError, GitResolver
from parallax.core.lineage import LineageGraph
from parallax.core.logging import logger, setup_logging
from parallax.core.models import (
    DownstreamNode,
    ExposureNode,
    ModelASTDiff,
    RiskSeverity,
)
from parallax.core.risk_engine import RiskEngine


@click.group()
@click.version_option(version=__version__, prog_name="parallax")
def cli() -> None:
    """Parallax: Zero-Config Blast Radius & Semantic Drift CI for SQL and dbt."""


@cli.command("check")
@click.option("--manifest", "-m", default=None, help="Path to dbt target/manifest.json.")
@click.option("--base", "-b", default=None, help="Git base reference (default: origin/main).")
@click.option("--head", "-h", default=None, help="Git head reference (default: HEAD).")
@click.option(
    "--dialect", "-d", default=None, help="SQL dialect (snowflake, bigquery, postgres, etc.)."
)
@click.option(
    "--fail-on",
    type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW", "NEVER"], case_sensitive=False),
    default=None,
    help="Minimum severity level to trigger exit code 1.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["terminal", "markdown", "json", "html"], case_sensitive=False),
    default="terminal",
    help="Output format (terminal, markdown, json, html).",
)
@click.option("--output", "-o", default=None, help="File path to write report output.")
@click.option("--config", "-c", default=None, help="Path to .parallax.yml configuration file.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose debug logging.")
@click.option("--git-root", default=None, help="Path to the git repository root (defaults to CWD).")
def check(
    manifest: str | None,
    base: str | None,
    head: str | None,
    dialect: str | None,
    fail_on: str | None,
    output_format: str,
    output: str | None,
    config: str | None,
    verbose: bool,
    git_root: str | None,
) -> None:
    """Check SQL changes between Git branches for semantic drift and blast radius."""
    setup_logging(verbose=verbose)
    start_time = time.perf_counter()

    cfg = ParallaxConfig.load(config)
    active_manifest_path = manifest or cfg.manifest_path
    active_base = base or cfg.base_ref
    active_head = head or cfg.head_ref
    active_dialect = dialect or cfg.dialect
    active_fail_on = RiskSeverity(fail_on.upper()) if fail_on else cfg.fail_on

    # 1. Resolve modified SQL files from Git
    resolver = GitResolver(repo_root=git_root or ".")
    try:
        changed_files = resolver.get_changed_sql_files(
            base_ref=active_base,
            head_ref=active_head,
            include_working_tree=True,
            ignore_patterns=cfg.ignore_patterns,
        )
    except GitError as e:
        logger.error("Git error: %s", e)
        sys.exit(1)

    if not changed_files:
        logger.info("No modified .sql files detected. Parallax CI check passed.")
        if output:
            Path(output).write_text("No modified .sql files detected.", encoding="utf-8")
        sys.exit(0)

    logger.debug("Found %d modified SQL file(s).", len(changed_files))

    # 2. Parse AST semantic diffs
    ast_engine = ASTDiffEngine(default_dialect=active_dialect)
    ast_diffs: list[ModelASTDiff] = []
    diff_by_path: dict[str, ModelASTDiff] = {}

    for cf in changed_files:
        model_name = Path(cf.path).stem
        diff = ast_engine.diff_model(
            model_name=model_name,
            file_path=cf.path,
            base_sql=cf.base_content,
            head_sql=cf.head_content,
            dialect=active_dialect,
        )
        ast_diffs.append(diff)
        diff_by_path[cf.path] = diff

    # 3. Ingest dbt manifest.json
    try:
        dbt_manifest = DbtManifest.from_file(active_manifest_path)
    except ManifestError as e:
        logger.warning("Manifest not found or invalid: %s. Proceeding with AST-only diff.", e)
        dbt_manifest = None

    # 4. Traverse DAG lineage if manifest is available
    downstream_models: list[DownstreamNode] = []
    impacted_exposures: list[ExposureNode] = []
    dag_edges: list[tuple[str, str]] = []
    max_depth = 0

    if dbt_manifest is not None:
        lineage = LineageGraph(dbt_manifest)
        modified_ids: list[str] = []
        dropped_by_id: dict[str, list[str]] = {}

        for cf in changed_files:
            uid = dbt_manifest.get_model_id_by_path(cf.path) or dbt_manifest.get_model_id_by_name(
                Path(cf.path).stem
            )
            if uid:
                modified_ids.append(uid)
                m_diff = diff_by_path.get(cf.path)
                if m_diff and m_diff.dropped_columns:
                    dropped_by_id[uid] = m_diff.dropped_columns

        if modified_ids:
            downstream_models, impacted_exposures, max_depth = lineage.get_downstream_blast_radius(
                modified_model_ids=modified_ids,
                dropped_or_modified_columns=dropped_by_id,
                dialect=active_dialect,
            )
            dag_edges = lineage.get_subgraph_edges(modified_ids)

    # 5. Evaluate Risk
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    risk_engine = RiskEngine(tier_tags=cfg.tier_tags)
    report = risk_engine.evaluate(
        modified_models=[cf.path for cf in changed_files],
        ast_diffs=ast_diffs,
        downstream_models=downstream_models,
        impacted_exposures=impacted_exposures,
        max_dag_depth=max_depth,
        execution_duration_ms=duration_ms,
        dag_edges=dag_edges,
    )

    # 6. Format and Render Output
    rendered_output = ""
    fmt = output_format.lower()
    if fmt == "terminal":
        terminal_formatter = TerminalFormatter()
        terminal_formatter.render(report, base_ref=active_base, head_ref=active_head)
        rendered_output = terminal_formatter.to_string(
            report, base_ref=active_base, head_ref=active_head
        )
    elif fmt == "markdown":
        rendered_output = MarkdownFormatter.render(report)
        click.echo(rendered_output)
    elif fmt == "json":
        rendered_output = report.model_dump_json(indent=2)
        click.echo(rendered_output)
    elif fmt == "html":
        rendered_output = HTMLFormatter.render(report, base_ref=active_base, head_ref=active_head)
        out_path = Path(output or "parallax-report.html")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered_output, encoding="utf-8")
        click.echo(f"Parallax HTML report: {out_path.resolve()}")

    if output and fmt != "html":
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Write clean markdown or text to file
        if fmt == "terminal":
            # For output file, prefer markdown rather than ANSI codes
            out_path.write_text(MarkdownFormatter.render(report), encoding="utf-8")
        else:
            out_path.write_text(rendered_output, encoding="utf-8")
        logger.debug("Wrote report to '%s'.", output)

    # 7. CI Gating
    if active_fail_on != RiskSeverity.NEVER and report.risk_severity >= active_fail_on:
        logger.error(
            "Parallax CI blocked: Detected %s risk which meets or exceeds failure threshold %s.",
            report.risk_severity.value,
            active_fail_on.value,
        )
        sys.exit(1)

    sys.exit(0)


@cli.command("report")
@click.option("--manifest", "-m", default=None, help="Path to dbt manifest.json.")
@click.option("--base", "-b", default=None, help="Git base ref.")
@click.option("--head", "-h", default=None, help="Git head ref.")
@click.option("--dialect", "-d", default=None, help="SQL dialect.")
@click.option("--out", "-o", default="parallax-report.html", help="HTML report output path.")
@click.option("--demo", is_flag=True, default=False, help="Generate report from built-in simulation scenario.")
@click.option("--open", "open_browser", is_flag=True, default=False, help="Open the HTML report in your browser after generation.")
@click.option("--config", "-c", default=None, help="Path to .parallax.yml config file.")
@click.option("--git-root", default=None, help="Path to the git repository root (defaults to CWD).")
def report(
    manifest: str | None,
    base: str | None,
    head: str | None,
    dialect: str | None,
    out: str,
    demo: bool,
    open_browser: bool,
    config: str | None,
    git_root: str | None,
) -> None:
    """Generate a standalone static HTML blast-radius report."""
    setup_logging()
    cfg = ParallaxConfig.load(config)
    active_manifest_path = manifest or cfg.manifest_path
    active_base = base or cfg.base_ref
    active_head = head or cfg.head_ref
    active_dialect = dialect or cfg.dialect

    if demo:
        from parallax.demo.scenario import create_demo_report

        rep = create_demo_report()
    else:
        start_time = time.perf_counter()
        resolver = GitResolver(repo_root=git_root or ".")
        try:
            changed_files = resolver.get_changed_sql_files(
                base_ref=active_base,
                head_ref=active_head,
                include_working_tree=True,
                ignore_patterns=cfg.ignore_patterns,
            )
        except GitError as e:
            logger.error("Git error: %s", e)
            sys.exit(1)

        ast_engine = ASTDiffEngine(default_dialect=active_dialect)
        ast_diffs: list[ModelASTDiff] = []
        diff_by_path: dict[str, ModelASTDiff] = {}
        for cf in changed_files:
            diff = ast_engine.diff_model(
                model_name=Path(cf.path).stem,
                file_path=cf.path,
                base_sql=cf.base_content,
                head_sql=cf.head_content,
                dialect=active_dialect,
            )
            ast_diffs.append(diff)
            diff_by_path[cf.path] = diff

        dag_edges: list[tuple[str, str]] = []
        downstream: list[DownstreamNode] = []
        exposures: list[ExposureNode] = []
        max_depth = 0
        try:
            dbt_manifest = DbtManifest.from_file(active_manifest_path)
            lineage = LineageGraph(dbt_manifest)
            mod_ids: list[str] = []
            dropped_by_id: dict[str, list[str]] = {}
            for cf in changed_files:
                uid = dbt_manifest.get_model_id_by_path(cf.path) or dbt_manifest.get_model_id_by_name(
                    Path(cf.path).stem
                )
                if uid:
                    mod_ids.append(uid)
                    m_diff = diff_by_path.get(cf.path)
                    if m_diff and m_diff.dropped_columns:
                        dropped_by_id[uid] = m_diff.dropped_columns

            valid_mod_ids = [m for m in mod_ids if m]
            if valid_mod_ids:
                downstream, exposures, max_depth = lineage.get_downstream_blast_radius(
                    valid_mod_ids,
                    dropped_or_modified_columns=dropped_by_id,
                    dialect=active_dialect,
                )
                dag_edges = lineage.get_subgraph_edges(valid_mod_ids)
        except (ManifestError, OSError, ValueError) as e:
            logger.warning("Manifest not found or invalid: %s. Proceeding without DAG lineage.", e)
            downstream, exposures, max_depth, dag_edges = [], [], 0, []

        duration = (time.perf_counter() - start_time) * 1000.0
        risk_engine = RiskEngine(tier_tags=cfg.tier_tags)
        rep = risk_engine.evaluate(
            [cf.path for cf in changed_files],
            ast_diffs,
            downstream,
            exposures,
            max_depth,
            duration,
            dag_edges=dag_edges,
        )

    html_content = HTMLFormatter.render(rep, base_ref=active_base, head_ref=active_head)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    click.echo(f"Parallax HTML report generated: {out_path.resolve()}")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(out_path.resolve().as_uri())
        except Exception:  # noqa: BLE001
            click.echo("Could not open browser automatically. Open the file manually.")

    if not demo and len(rep.modified_models) == 0:
        click.echo("Note: 0 modified SQL files detected between Git branches.")
        click.echo("Tip: Run with --demo to preview a report with full simulation data:")
        click.echo(f"   parallax report --demo --out {out}")


@cli.command("demo")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["terminal", "markdown", "json", "html"], case_sensitive=False),
    default="terminal",
    help="Output format (terminal, markdown, json, html).",
)
@click.option("--output", "--out", "-o", "output_file", default=None, help="File path to write report output.")
def demo(output_format: str, output_file: str | None) -> None:
    """Run an instant in-memory simulation of silent filter tightening and downstream blast radius."""
    from parallax.demo.scenario import run_demo

    run_demo(output_format=output_format, output_file=output_file)


if __name__ == "__main__":
    cli()
