"""Integration tests for Parallax CLI commands."""

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from parallax.cli.main import cli


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
