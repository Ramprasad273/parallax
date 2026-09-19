"""Unit tests for the Multi-Hop Column-Level Lineage (CLL) Engine."""

from parallax.core.column_lineage import ColumnLineageEngine


def test_single_hop_column_derivation() -> None:
    engine = ColumnLineageEngine(default_dialect="postgres")
    nodes = {
        "model.stg_orders": {
            "name": "stg_orders",
            "raw_code": "SELECT order_id, customer_id, amount FROM raw.orders",
        },
        "model.int_orders": {
            "name": "int_orders",
            "raw_code": "{{ config(materialized='view') }}\nSELECT customer_id, SUM(amount) AS total_amount FROM {{ ref('stg_orders') }} GROUP BY customer_id",
        },
    }

    impacts, broken = engine.trace_subgraph_column_lineage(
        nodes=nodes,
        modified_models=["stg_orders"],
        dropped_or_modified_columns={"stg_orders": ["amount"]},
        subgraph_node_ids=["model.int_orders"],
        dialect="postgres",
    )

    assert "model.int_orders" in impacts
    col_impacts = impacts["model.int_orders"]
    assert any(ci.column_name == "total_amount" and ci.upstream_column == "amount" for ci in col_impacts)
    assert "amount" in broken["model.int_orders"]


def test_multi_hop_column_propagation() -> None:
    engine = ColumnLineageEngine(default_dialect="postgres")
    nodes = {
        "model.stg_vitals": {
            "name": "stg_vitals",
            "raw_code": "SELECT patient_id, heart_rate FROM raw.patient_vitals",
        },
        "model.int_vitals": {
            "name": "int_vitals",
            "raw_code": "SELECT patient_id, AVG(heart_rate) AS avg_heart_rate FROM {{ ref('stg_vitals') }} GROUP BY patient_id",
        },
        "model.fct_vitals": {
            "name": "fct_vitals",
            "raw_code": "SELECT patient_id, avg_heart_rate * 1.5 AS scaled_hr FROM {{ ref('int_vitals') }}",
        },
    }

    impacts, _ = engine.trace_subgraph_column_lineage(
        nodes=nodes,
        modified_models=["stg_vitals"],
        dropped_or_modified_columns={"stg_vitals": ["heart_rate"]},
        subgraph_node_ids=["model.int_vitals", "model.fct_vitals"],
        dialect="postgres",
    )

    assert "model.int_vitals" in impacts
    assert "model.fct_vitals" in impacts

    fct_impacts = impacts["model.fct_vitals"]
    scaled_impact = next((ci for ci in fct_impacts if ci.column_name == "scaled_hr"), None)
    assert scaled_impact is not None
    assert scaled_impact.upstream_column == "heart_rate"
    assert "int_vitals.avg_heart_rate" in scaled_impact.lineage_path or "scaled_hr" in scaled_impact.lineage_path


def test_where_clause_dependency_detection() -> None:
    engine = ColumnLineageEngine(default_dialect="postgres")
    nodes = {
        "model.stg_orders": {
            "name": "stg_orders",
            "raw_code": "SELECT order_id, status FROM raw.orders",
        },
        "model.int_orders": {
            "name": "int_orders",
            "raw_code": "SELECT order_id FROM {{ ref('stg_orders') }} WHERE status = 'shipped'",
        },
    }

    _, broken = engine.trace_subgraph_column_lineage(
        nodes=nodes,
        modified_models=["stg_orders"],
        dropped_or_modified_columns={"stg_orders": ["status"]},
        subgraph_node_ids=["model.int_orders"],
        dialect="postgres",
    )

    assert "model.int_orders" in broken
    assert "status" in broken["model.int_orders"]


def test_malformed_sql_graceful_fallback() -> None:
    engine = ColumnLineageEngine(default_dialect="postgres")
    nodes = {
        "model.stg_broken": {
            "name": "stg_broken",
            "raw_code": "SELECT order_id, amount FROM raw.orders",
        },
        "model.int_broken": {
            "name": "int_broken",
            "raw_code": "THIS IS INVALID SQL BUT CONTAINS amount AND order_id",
        },
    }

    # Should not raise exception, falls back to word-boundary regex
    _, broken = engine.trace_subgraph_column_lineage(
        nodes=nodes,
        modified_models=["stg_broken"],
        dropped_or_modified_columns={"stg_broken": ["amount"]},
        subgraph_node_ids=["model.int_broken"],
        dialect="postgres",
    )

    assert "model.int_broken" in broken
    assert "amount" in broken["model.int_broken"]
