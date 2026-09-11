"""Unit tests for DAG blast radius propagation and column break analysis."""

from parallax.core.dbt_manifest import DbtManifest
from parallax.core.lineage import LineageGraph
from parallax.core.models import ModelLayer


def test_blast_radius_traversal() -> None:
    nodes = {
        "model.jaffle_shop.stg_orders": {
            "name": "stg_orders",
            "resource_type": "model",
            "original_file_path": "models/staging/stg_orders.sql",
        },
        "model.jaffle_shop.fct_orders": {
            "name": "fct_orders",
            "resource_type": "model",
            "original_file_path": "models/marts/fct_orders.sql",
            "raw_code": "SELECT order_id, amount FROM stg_orders;",
        },
        "model.jaffle_shop.dim_customers": {
            "name": "dim_customers",
            "resource_type": "model",
            "original_file_path": "models/marts/dim_customers.sql",
            "raw_code": "SELECT customer_id, total_amount FROM fct_orders;",
        },
    }
    exposures = {
        "exposure.jaffle_shop.exec_dashboard": {
            "name": "exec_dashboard",
            "label": "Executive Dashboard",
            "type": "dashboard",
        }
    }
    child_map = {
        "model.jaffle_shop.stg_orders": ["model.jaffle_shop.fct_orders"],
        "model.jaffle_shop.fct_orders": [
            "model.jaffle_shop.dim_customers",
            "exposure.jaffle_shop.exec_dashboard",
        ],
        "model.jaffle_shop.dim_customers": [],
    }

    manifest = DbtManifest(nodes, exposures, {}, child_map)
    graph = LineageGraph(manifest)

    # stg_orders modified, dropping order_id
    downstream, impacted_exp, max_depth = graph.get_downstream_blast_radius(
        modified_model_ids=["model.jaffle_shop.stg_orders"],
        dropped_or_modified_columns={"model.jaffle_shop.stg_orders": ["order_id"]},
    )

    # 2 downstream models
    assert len(downstream) == 2
    names = [m.name for m in downstream]
    assert "fct_orders" in names
    assert "dim_customers" in names

    # Max depth should be 2 (stg -> fct -> dim)
    assert max_depth == 2

    # Exposure reached
    assert len(impacted_exp) == 1
    assert impacted_exp[0].name == "exec_dashboard"

    # Column break heuristic: fct_orders uses order_id, so it should be flagged
    fct = next(m for m in downstream if m.name == "fct_orders")
    assert "order_id" in fct.broken_columns
    assert fct.layer == ModelLayer.MARTS
