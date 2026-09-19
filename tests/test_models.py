from pathlib import Path

"""Unit tests for Parallax core models and configuration."""

import pytest
from pydantic import ValidationError

from parallax.core.config import ParallaxConfig
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


def test_risk_severity_ordering() -> None:
    assert RiskSeverity.CRITICAL > RiskSeverity.HIGH
    assert RiskSeverity.HIGH > RiskSeverity.MEDIUM
    assert RiskSeverity.MEDIUM > RiskSeverity.LOW
    assert RiskSeverity.LOW > RiskSeverity.NEVER

    assert RiskSeverity.CRITICAL >= RiskSeverity.CRITICAL
    assert RiskSeverity.HIGH >= RiskSeverity.MEDIUM
    assert not (RiskSeverity.LOW >= RiskSeverity.HIGH)


def test_model_layer_inference() -> None:
    assert ModelLayer.from_path("models/staging/stg_orders.sql") == ModelLayer.STAGING
    assert ModelLayer.from_path("models/intermediate/int_payments.sql") == ModelLayer.INTERMEDIATE
    assert ModelLayer.from_path("models/marts/fct_orders.sql") == ModelLayer.MARTS
    assert ModelLayer.from_path("models/reporting/rpt_revenue.sql") == ModelLayer.REPORTING
    assert ModelLayer.from_path("models/utilities/date_spine.sql") == ModelLayer.OTHER


def test_predicate_diff_creation() -> None:
    diff = PredicateDiff(
        clause=PredicateClauseType.WHERE,
        diff_type=PredicateDiffType.TIGHTENED,
        old_expression="status NOT IN ('returned', 'cancelled')",
        new_expression="status = 'delivered'",
        explanation="Filter tightened from NOT IN to exact match",
    )
    assert diff.clause == PredicateClauseType.WHERE
    assert diff.diff_type == PredicateDiffType.TIGHTENED
    assert "status = 'delivered'" in (diff.new_expression or "")


def test_model_ast_diff_properties() -> None:
    pred_diff = PredicateDiff(
        clause=PredicateClauseType.WHERE,
        diff_type=PredicateDiffType.TIGHTENED,
        old_expression="a = 1",
        new_expression="a = 2",
        explanation="Modified filter",
    )
    col_diff = ColumnDiff(
        column_name="order_id",
        diff_type=ColumnDiffType.DROPPED,
        old_expression="order_id",
        new_expression=None,
        explanation="Column removed",
    )
    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/staging/stg_orders.sql",
        predicates=[pred_diff],
        columns=[col_diff],
    )
    assert ast_diff.has_semantic_changes is True
    assert ast_diff.dropped_columns == ["order_id"]


def test_immutability() -> None:
    diff = ColumnDiff(
        column_name="net_amount",
        diff_type=ColumnDiffType.EXPRESSION_ALTERED,
        explanation="Changed discount factor",
    )
    with pytest.raises(ValidationError):
        diff.column_name = "new_name"  # type: ignore


def test_blast_radius_report() -> None:
    downstream = DownstreamNode(
        unique_id="model.jaffle_shop.fct_orders",
        name="fct_orders",
        layer=ModelLayer.MARTS,
        tags=["finance", "tier_1"],
        broken_columns=["order_id"],
    )
    exposure = ExposureNode(
        name="executive_arr_dashboard",
        label="Executive ARR Dashboard",
        exposure_type=ExposureType.DASHBOARD,
    )
    report = BlastRadiusReport(
        modified_models=["stg_orders"],
        ast_diffs=[],
        downstream_models=[downstream],
        impacted_exposures=[exposure],
        max_dag_depth=3,
        risk_severity=RiskSeverity.CRITICAL,
        plain_english_summary="Critical risk detected.",
    )
    assert report.has_breaking_changes is True
    assert report.risk_severity == RiskSeverity.CRITICAL
    assert len(report.impacted_exposures) == 1


def test_parallax_config_defaults(tmp_path: Path) -> None:
    config = ParallaxConfig.load(str(tmp_path / "non_existent.yml"))
    assert config.dialect == "snowflake"
    assert config.fail_on == RiskSeverity.CRITICAL
    assert "tier_1" in config.tier_tags


def test_parallax_config_from_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / ".parallax.yml"
    config_file.write_text(
        "dialect: bigquery\nfail_on: HIGH\ntier_tags:\n  - gold\n  - executive\n",
        encoding="utf-8",
    )
    config = ParallaxConfig.load(str(config_file))
    assert config.dialect == "bigquery"
    assert config.fail_on == RiskSeverity.HIGH
    assert config.tier_tags == ["gold", "executive"]


def test_parallax_config_invalid_yaml_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    bad_config = tmp_path / "bad.yml"
    bad_config.write_text("invalid: [yaml: :", encoding="utf-8")
    config = ParallaxConfig.load(str(bad_config))
    assert config.dialect == "snowflake"
    assert "Failed to load configuration" in caplog.text

