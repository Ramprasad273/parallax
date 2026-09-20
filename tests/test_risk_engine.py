"""Unit tests for risk scoring and rule-based explainer engine."""

from parallax.core.models import (
    ColumnDiff,
    ColumnDiffType,
    DownstreamNode,
    ExposureNode,
    ExposureType,
    JoinDiff,
    JoinDiffType,
    ModelASTDiff,
    ModelLayer,
    PredicateClauseType,
    PredicateDiff,
    PredicateDiffType,
    RiskSeverity,
    StructuralDiff,
)
from parallax.core.risk_engine import RiskEngine


def test_risk_critical_when_broken_columns_downstream() -> None:
    engine = RiskEngine()

    downstream = [
        DownstreamNode(
            unique_id="model.fct_orders",
            name="fct_orders",
            layer=ModelLayer.MARTS,
            broken_columns=["order_id"],
        )
    ]
    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
        columns=[
            ColumnDiff(
                column_name="order_id",
                diff_type=ColumnDiffType.DROPPED,
                explanation="Dropped",
            )
        ],
    )

    report = engine.evaluate(["stg_orders"], [ast_diff], downstream, [], 1)
    assert report.risk_severity == RiskSeverity.CRITICAL
    assert "CRITICAL RISK" in report.plain_english_summary
    assert any("order_id" in a for a in report.remediation_advice)


def test_risk_critical_when_predicate_upstream_of_exposure() -> None:
    engine = RiskEngine()

    exposures = [
        ExposureNode(
            name="exec_arr",
            label="Executive ARR Dashboard",
            exposure_type=ExposureType.DASHBOARD,
        )
    ]
    downstream = [
        DownstreamNode(
            unique_id="model.fct_orders",
            name="fct_orders",
            layer=ModelLayer.MARTS,
        )
    ]
    pred = PredicateDiff(
        clause=PredicateClauseType.WHERE,
        diff_type=PredicateDiffType.TIGHTENED,
        old_expression="status != 'cancelled'",
        new_expression="status = 'delivered'",
        explanation="Tightened",
    )
    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
        predicates=[pred],
    )

    report = engine.evaluate(["stg_orders"], [ast_diff], downstream, exposures, 2)
    assert report.risk_severity == RiskSeverity.CRITICAL
    assert "Executive ARR Dashboard" in report.plain_english_summary


def test_risk_high_when_join_type_mutated() -> None:
    engine = RiskEngine()

    downstream = [
        DownstreamNode(
            unique_id="model.rpt_finance",
            name="rpt_finance",
            layer=ModelLayer.REPORTING,
        )
    ]
    join_diff = JoinDiff(
        table_name="customers",
        diff_type=JoinDiffType.TYPE_CHANGED,
        old_join_type="INNER",
        new_join_type="LEFT",
        explanation="Inner to Left",
    )
    ast_diff = ModelASTDiff(
        model_name="fct_orders",
        file_path="models/fct_orders.sql",
        structural=StructuralDiff(join_diffs=[join_diff]),
    )

    report = engine.evaluate(["fct_orders"], [ast_diff], downstream, [], 1)
    assert report.risk_severity == RiskSeverity.HIGH
    assert "HIGH RISK" in report.plain_english_summary


def test_risk_low_for_no_semantic_changes() -> None:
    engine = RiskEngine()

    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
    )
    report = engine.evaluate(["stg_orders"], [ast_diff], [], [], 0)
    assert report.risk_severity == RiskSeverity.LOW
    assert "NO RISK" in report.plain_english_summary


def test_risk_high_when_predicate_cascades_to_many_models() -> None:
    engine = RiskEngine()

    downstream = [
        DownstreamNode(
            unique_id=f"model.downstream_{i}",
            name=f"downstream_{i}",
            layer=ModelLayer.INTERMEDIATE,
        )
        for i in range(6)
    ]
    pred = PredicateDiff(
        clause=PredicateClauseType.WHERE,
        diff_type=PredicateDiffType.TIGHTENED,
        old_expression="1=1",
        new_expression="status = 'active'",
        explanation="Tightened",
    )
    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
        predicates=[pred],
    )
    report = engine.evaluate(["stg_orders"], [ast_diff], downstream, [], 2)
    assert report.risk_severity == RiskSeverity.HIGH
    assert "HIGH RISK" in report.plain_english_summary


def test_risk_high_when_dropped_columns_without_consumers() -> None:
    engine = RiskEngine()

    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
        columns=[
            ColumnDiff(
                column_name="legacy_col",
                diff_type=ColumnDiffType.DROPPED,
                explanation="Dropped",
            )
        ],
    )
    report = engine.evaluate(["stg_orders"], [ast_diff], [], [], 0)
    assert report.risk_severity == RiskSeverity.HIGH


def test_risk_medium_when_calculation_altered() -> None:
    engine = RiskEngine()

    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
        columns=[
            ColumnDiff(
                column_name="amount",
                diff_type=ColumnDiffType.EXPRESSION_ALTERED,
                explanation="Altered tax calculation",
            )
        ],
    )
    report = engine.evaluate(["stg_orders"], [ast_diff], [], [], 0)
    assert report.risk_severity == RiskSeverity.MEDIUM
    assert "MEDIUM RISK" in report.plain_english_summary


def test_risk_medium_when_column_added() -> None:
    engine = RiskEngine()

    ast_diff = ModelASTDiff(
        model_name="stg_orders",
        file_path="models/stg_orders.sql",
        columns=[
            ColumnDiff(
                column_name="new_col",
                diff_type=ColumnDiffType.ADDED,
                explanation="Added new column",
            )
        ],
    )
    report = engine.evaluate(["stg_orders"], [ast_diff], [], [], 0)
    assert report.risk_severity == RiskSeverity.MEDIUM
    assert "MEDIUM RISK" in report.plain_english_summary
