"""Unit tests for packaged demo experience."""

import io

from click.testing import CliRunner
from rich.console import Console

from parallax.cli.main import cli
from parallax.demo.scenario import build_demo_manifest_data, run_demo


def test_build_demo_manifest() -> None:
    data = build_demo_manifest_data()
    assert len(data["nodes"]) >= 20
    assert len(data["exposures"]) == 3
    assert "model.enterprise.stg_orders" in data["nodes"]
    assert "exposure.enterprise.exec_arr_dashboard" in data["exposures"]


def test_run_demo_execution() -> None:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    run_demo(console=console)
    output = buf.getvalue()

    assert "CRITICAL RISK" in output
    assert "stg_orders" in output
    assert "Executive ARR Dashboard" in output
    assert "Board Financials Summary" in output
    assert "Sales Commission Sync" in output


def test_cli_demo_command() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["demo"])
    assert result.exit_code == 0
    assert "CRITICAL RISK" in result.output
    assert "Executive ARR Dashboard" in result.output
