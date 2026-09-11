"""Unit tests for Jinja sanitization and AST semantic diffing."""

from parallax.core.ast_diff import ASTDiffEngine
from parallax.core.jinja import JinjaSanitizer
from parallax.core.models import (
    ColumnDiffType,
    JoinDiffType,
    PredicateClauseType,
    PredicateDiffType,
)


def test_jinja_sanitizer_ref_and_source() -> None:
    raw_sql = """
    {{ config(materialized='table') }}
    {# This is a comment #}
    SELECT id, status FROM {{ ref('stg_orders') }}
    JOIN {{ source('raw_feed', 'customers') }} ON stg_orders.cust_id = customers.id
    """
    sanitized = JinjaSanitizer.sanitize(raw_sql)
    assert "stg_orders" in sanitized
    assert "raw_feed__customers" in sanitized
    assert "config(" not in sanitized
    assert "This is a comment" not in sanitized


def test_jinja_sanitizer_incremental() -> None:
    raw_sql = """
    SELECT id, created_at FROM {{ ref('events') }}
    WHERE 1=1
    {% if is_incremental() %}
      AND created_at > (SELECT max(created_at) FROM {{ this }})
    {% endif %}
    """
    sanitized = JinjaSanitizer.sanitize(raw_sql)
    assert "created_at > (SELECT max(created_at) FROM this)" in sanitized
    assert "{% if" not in sanitized


def test_the_3_8_million_dollar_bug() -> None:
    engine = ASTDiffEngine(default_dialect="snowflake")

    base_sql = """
    SELECT id, status, customer_id
    FROM {{ ref('raw_orders') }}
    WHERE status NOT IN ('returned', 'cancelled')
    """

    head_sql = """
    SELECT id, status, customer_id
    FROM {{ ref('raw_orders') }}
    WHERE status = 'delivered'
    """

    diff = engine.diff_model("stg_orders", "models/stg_orders.sql", base_sql, head_sql)

    assert diff.has_semantic_changes is True
    assert len(diff.predicates) == 1

    p = diff.predicates[0]
    assert p.clause == PredicateClauseType.WHERE
    assert p.diff_type == PredicateDiffType.TIGHTENED
    assert "tightened" in p.explanation.lower()


def test_dropped_column_breaking_change() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT id, order_id, amount FROM orders;"
    head_sql = "SELECT id, amount FROM orders;"

    diff = engine.diff_model("stg_orders", "models/stg_orders.sql", base_sql, head_sql)
    assert diff.has_semantic_changes is True
    assert diff.dropped_columns == ["order_id"]
    assert len(diff.columns) == 1
    assert diff.columns[0].diff_type == ColumnDiffType.DROPPED


def test_column_calculation_altered() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT id, amount * 0.9 AS net_amount FROM orders;"
    head_sql = "SELECT id, amount * 0.85 AS net_amount FROM orders;"

    diff = engine.diff_model("fct_orders", "models/fct_orders.sql", base_sql, head_sql)
    assert diff.has_semantic_changes is True
    assert len(diff.columns) == 1
    c = diff.columns[0]
    assert c.column_name == "net_amount"
    assert c.diff_type == ColumnDiffType.EXPRESSION_ALTERED


def test_column_added() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT id FROM orders;"
    head_sql = "SELECT id, created_at FROM orders;"

    diff = engine.diff_model("fct_orders", "models/fct_orders.sql", base_sql, head_sql)
    assert len(diff.columns) == 1
    assert diff.columns[0].diff_type == ColumnDiffType.ADDED
    assert diff.columns[0].column_name == "created_at"


def test_join_type_changed_inner_to_left() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT o.id, c.name FROM orders o INNER JOIN customers c ON o.cust_id = c.id;"
    head_sql = "SELECT o.id, c.name FROM orders o LEFT JOIN customers c ON o.cust_id = c.id;"

    diff = engine.diff_model("fct_orders", "models/fct_orders.sql", base_sql, head_sql)
    assert diff.has_semantic_changes is True
    assert len(diff.structural.join_diffs) == 1
    j = diff.structural.join_diffs[0]
    assert j.diff_type == JoinDiffType.TYPE_CHANGED
    assert "LEFT" in (j.new_join_type or "")


def test_operator_mutated() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT id FROM orders WHERE amount >= 100;"
    head_sql = "SELECT id FROM orders WHERE amount > 100;"

    diff = engine.diff_model("fct_orders", "models/fct_orders.sql", base_sql, head_sql)
    assert len(diff.predicates) == 1
    assert diff.predicates[0].diff_type == PredicateDiffType.MUTATED_OPERATOR


def test_predicate_dropped() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT id FROM orders WHERE status = 'active' AND is_deleted = false;"
    head_sql = "SELECT id FROM orders WHERE status = 'active';"

    diff = engine.diff_model("fct_orders", "models/fct_orders.sql", base_sql, head_sql)
    assert len(diff.predicates) == 1
    p = diff.predicates[0]
    assert p.diff_type == PredicateDiffType.DROPPED
    assert "is_deleted" in (p.old_expression or "") and "FALSE" in (p.old_expression or "").upper()


def test_added_model_file() -> None:
    engine = ASTDiffEngine()

    head_sql = "SELECT id, name FROM new_model WHERE active = true;"
    diff = engine.diff_model("new_model", "models/new_model.sql", None, head_sql)

    assert len(diff.columns) == 2
    assert all(c.diff_type == ColumnDiffType.ADDED for c in diff.columns)
    assert len(diff.predicates) == 1
    assert diff.predicates[0].diff_type == PredicateDiffType.ADDED


def test_deleted_model_file() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT id, name FROM old_model;"
    diff = engine.diff_model("old_model", "models/old_model.sql", base_sql, None)

    assert len(diff.columns) == 2
    assert all(c.diff_type == ColumnDiffType.DROPPED for c in diff.columns)


def test_group_by_and_distinct_diff() -> None:
    engine = ASTDiffEngine()

    base_sql = "SELECT cust_id, count(*) FROM orders GROUP BY cust_id;"
    head_sql = "SELECT DISTINCT cust_id, count(*) FROM orders GROUP BY cust_id, status;"

    diff = engine.diff_model("fct_orders", "models/fct_orders.sql", base_sql, head_sql)
    assert diff.structural.distinct_altered is True
    assert diff.structural.group_by_altered is True
