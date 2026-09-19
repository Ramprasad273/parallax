"""Integration tests for Parallax CLI commands."""

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from parallax.cli.main import cli
from parallax.core.git import GitError, GitResolver


@pytest.fixture
def temp_dbt_git_repo(tmp_path: Path) -> Path:
    """Create an isolated git repository with a synthetic manifest.json and models."""

    def run(args: list[str]) -> None:
        subprocess.run(
            ["git"] + args,
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )

    run(["init"])
    run(["config", "user.name", "Test User"])
    run(["config", "user.email", "test@example.com"])

    models_dir = tmp_path / "models" / "staging"
    models_dir.mkdir(parents=True)
    stg_orders = models_dir / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status != 'cancelled';", encoding="utf-8"
    )

    # target/manifest.json
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    manifest = {
        "nodes": {
            "model.jaffle_shop.stg_orders": {
                "name": "stg_orders",
                "resource_type": "model",
                "original_file_path": "models/staging/stg_orders.sql",
                "depends_on": {"nodes": []},
            },
            "model.jaffle_shop.fct_orders": {
                "name": "fct_orders",
                "resource_type": "model",
                "original_file_path": "models/marts/fct_orders.sql",
                "depends_on": {"nodes": ["model.jaffle_shop.stg_orders"]},
            },
        },
        "exposures": {
            "exposure.jaffle_shop.arr_dash": {
                "name": "arr_dash",
                "label": "ARR Dashboard",
                "type": "dashboard",
                "depends_on": {"nodes": ["model.jaffle_shop.fct_orders"]},
            }
        },
        "child_map": {
            "model.jaffle_shop.stg_orders": ["model.jaffle_shop.fct_orders"],
            "model.jaffle_shop.fct_orders": ["exposure.jaffle_shop.arr_dash"],
        },
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    run(["add", "."])
    run(["commit", "-m", "Initial commit"])
    run(["branch", "-M", "main"])

    return tmp_path


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Parallax" in result.output
    assert "check" in result.output
    assert "report" in result.output
    assert "demo" in result.output


def test_cli_check_no_changes(temp_dbt_git_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check",
            "--base",
            "main",
            "--manifest",
            str(temp_dbt_git_repo / "target" / "manifest.json"),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "No modified .sql files detected" in result.output or "passed" in result.output.lower()


def test_cli_check_critical_blocks_pr(
    temp_dbt_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(temp_dbt_git_repo)

    # Modify stg_orders.sql (tightening filter upstream of exposure)
    stg_orders = temp_dbt_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status = 'delivered';", encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check",
            "--base",
            "main",
            "--manifest",
            "target/manifest.json",
            "--fail-on",
            "CRITICAL",
        ],
    )
    # Should exit 1 because CRITICAL risk was detected
    assert result.exit_code == 1


def test_cli_check_fail_on_never_passes(
    temp_dbt_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(temp_dbt_git_repo)

    stg_orders = temp_dbt_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status = 'delivered';", encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check",
            "--base",
            "main",
            "--manifest",
            "target/manifest.json",
            "--fail-on",
            "NEVER",
            "--format",
            "json",
        ],
    )
    # Should exit 0 because fail_on is NEVER
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["risk_severity"] == "CRITICAL"


def test_cli_check_writes_output_file(
    temp_dbt_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(temp_dbt_git_repo)

    stg_orders = temp_dbt_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status = 'delivered';", encoding="utf-8"
    )

    out_file = temp_dbt_git_repo / "pr_comment.md"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check",
            "--base",
            "main",
            "--manifest",
            "target/manifest.json",
            "--fail-on",
            "NEVER",
            "--format",
            "markdown",
            "--output",
            str(out_file),
        ],
    )
    assert result.exit_code == 0
    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert "<!-- parallax-ci-comment -->" in content


def test_cli_report_command(temp_dbt_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(temp_dbt_git_repo)
    stg_orders = temp_dbt_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status = 'delivered';", encoding="utf-8"
    )

    out_html = temp_dbt_git_repo / "custom_report.html"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            "--base",
            "main",
            "--manifest",
            "target/manifest.json",
            "--out",
            str(out_html),
        ],
    )
    assert result.exit_code == 0
    assert out_html.is_file()
    assert "<!DOCTYPE html>" in out_html.read_text(encoding="utf-8")


def test_cli_report_command_with_config(temp_dbt_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(temp_dbt_git_repo)
    stg_orders = temp_dbt_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status = 'delivered';", encoding="utf-8"
    )
    cfg_file = temp_dbt_git_repo / ".parallax.yml"
    cfg_file.write_text("version: 1\ntier_tags: ['custom_tier']\n", encoding="utf-8")

    out_html = temp_dbt_git_repo / "custom_report_cfg.html"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            "--base",
            "main",
            "--manifest",
            "target/manifest.json",
            "--config",
            str(cfg_file),
            "--out",
            str(out_html),
        ],
    )
    assert result.exit_code == 0
    assert out_html.is_file()
    html_content = out_html.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content
    assert "restricts order states" not in html_content


def test_cli_report_git_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_changed_sql_files(*args: object, **kwargs: object) -> list[object]:
        raise GitError("Simulated git failure")

    monkeypatch.setattr(GitResolver, "get_changed_sql_files", fake_get_changed_sql_files)
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert result.exit_code == 1


def test_cli_report_with_dropped_column(temp_dbt_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(temp_dbt_git_repo)
    stg_orders = temp_dbt_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text("SELECT id FROM raw_orders WHERE status != 'cancelled';", encoding="utf-8")

    # Add raw_code with dropped 'status' column to fct_orders in manifest
    manifest_path = temp_dbt_git_repo / "target" / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["nodes"]["model.jaffle_shop.fct_orders"]["raw_code"] = "SELECT id, status FROM {{ ref('stg_orders') }};"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    out_html = temp_dbt_git_repo / "dropped_col_report.html"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            "--base",
            "main",
            "--manifest",
            "target/manifest.json",
            "--out",
            str(out_html),
        ],
    )
    assert result.exit_code == 0
    assert out_html.is_file()
    html_content = out_html.read_text(encoding="utf-8")
    assert "broken column reference" in html_content


