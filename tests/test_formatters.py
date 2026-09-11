"""Unit tests for terminal, markdown, and HTML formatters."""

from parallax.cli.formatters.html import HTMLFormatter
from parallax.cli.formatters.markdown import MarkdownFormatter
from parallax.cli.formatters.terminal import TerminalFormatter
from parallax.core.models import (
    BlastRadiusReport,
    ColumnDiff,
    ColumnDiffType,
    DownstreamNode,
    ExposureNode,
    ExposureType,
    ModelASTDiff,
    ModelLayer,
    PredicateClauseType,
    PredicateDiff,
    PredicateDiffType,
    RiskSeverity,
)


def sample_report() -> BlastRadiusReport:
    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/staging/stg_orders.sql",
        predicates=[
            PredicateDiff(
                clause=PredicateClauseType.WHERE,
                diff_type=PredicateDiffType.TIGHTENED,
                old_expression="status NOT IN ('returned', 'cancelled')",
                new_expression="status = 'delivered'",
                explanation="Tightened filter",
            )
        ],
        columns=[
            ColumnDiff(
                column_name="order_id",
                diff_type=ColumnDiffType.DROPPED,
                old_expression="order_id",
                explanation="Dropped order_id",
            )
        ],
    )
    downstream = [
        DownstreamNode(
            unique_id="model.fct_orders",
            name="fct_orders",
            layer=ModelLayer.MARTS,
            broken_columns=["order_id"],
            distance_from_source=1,
        )
    ]
    exposures = [
        ExposureNode(
            name="board_arr_summary",
            label="Board ARR Summary",
            exposure_type=ExposureType.DASHBOARD,
            owner_name="VP Finance",
        )
    ]
    return BlastRadiusReport(
        modified_models=["stg_orders"],
        ast_diffs=[ast_diff],
        downstream_models=downstream,
        impacted_exposures=exposures,
        max_dag_depth=2,
        risk_severity=RiskSeverity.CRITICAL,
        plain_english_summary="Critical risk detected upstream of Board ARR Summary.",
        remediation_advice=[
            "Verify status filter with stakeholders.",
            "Fix broken column order_id.",
        ],
        execution_duration_ms=45.2,
    )


def test_terminal_formatter_output() -> None:
    report = sample_report()
    formatter = TerminalFormatter()
    output = formatter.to_string(report)

    assert "CRITICAL RISK" in output
    assert "stg_orders" in output
    assert "fct_orders" in output
    assert "Board ARR Summary" in output
    assert "status = 'delivered'" in output
    assert "45.20ms" in output


def test_markdown_formatter_output() -> None:
    report = sample_report()
    md = MarkdownFormatter.render(report)

    assert MarkdownFormatter.COMMENT_MARKER in md
    assert "img.shields.io" in md
    assert "CRITICAL_RISK" in md
    assert "<details>" in md
    assert "</details>" in md
    assert "Board ARR Summary" in md
    assert "`order_id` in `fct_orders`" in md
    assert "- [ ] Verify status filter with stakeholders." in md


def test_html_formatter_output() -> None:
    report = sample_report()
    html_out = HTMLFormatter.render(report)

    assert "<!DOCTYPE html>" in html_out
    assert "PARALLAX" in html_out
    assert "CRITICAL RISK" in html_out
    assert "Board ARR Summary" in html_out
    assert "fct_orders" in html_out
    assert "order_id" in html_out
