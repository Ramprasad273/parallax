"""Built-in interactive demo: Silent Filter Tightening Simulation."""

import time
from pathlib import Path

from rich.console import Console

from parallax.cli.formatters.terminal import TerminalFormatter
from parallax.core.ast_diff import ASTDiffEngine
from parallax.core.dbt_manifest import DbtManifest
from parallax.core.lineage import LineageGraph
from parallax.core.models import BlastRadiusReport
from parallax.core.risk_engine import RiskEngine


def build_demo_manifest_data() -> dict:
    """Generates a realistic enterprise dbt manifest with 35 models and 3 executive exposures."""
    nodes: dict[str, dict] = {}
    child_map: dict[str, list[str]] = {}

    # Staging Models
    staging_models = [
        "stg_orders",
        "stg_customers",
        "stg_payments",
        "stg_subscriptions",
        "stg_refunds",
    ]
    for s in staging_models:
        uid = f"model.enterprise.{s}"
        nodes[uid] = {
            "name": s,
            "resource_type": "model",
            "original_file_path": f"models/staging/{s}.sql",
            "tags": ["staging"],
            "depends_on": {"nodes": []},
        }
        child_map[uid] = []

    # Intermediate Models
    intermediate_models = [
        "int_order_items",
        "int_customer_orders",
        "int_subscription_periods",
        "int_net_payments",
    ]
    for i in intermediate_models:
        uid = f"model.enterprise.{i}"
        nodes[uid] = {
            "name": i,
            "resource_type": "model",
            "original_file_path": f"models/intermediate/{i}.sql",
            "tags": ["intermediate"],
            "depends_on": {"nodes": ["model.enterprise.stg_orders"]},
        }
        child_map[uid] = []
        child_map["model.enterprise.stg_orders"].append(uid)

    # Marts (Core Reporting Models)
    marts_models = [
        "fct_orders",
        "fct_mrr_monthly",
        "fct_churn_daily",
        "fct_customer_transactions",
        "dim_customers",
        "dim_products",
        "dim_subscriptions",
        "dim_sales_reps",
    ]
    for m in marts_models:
        uid = f"model.enterprise.{m}"
        nodes[uid] = {
            "name": m,
            "resource_type": "model",
            "original_file_path": f"models/marts/{m}.sql",
            "tags": ["marts", "tier_1", "finance"],
            "depends_on": {"nodes": ["model.enterprise.int_customer_orders"]},
        }
        child_map[uid] = []
        child_map["model.enterprise.int_customer_orders"].append(uid)

    # Reporting Models
    reporting_models = [
        "rpt_executive_kpis",
        "rpt_monthly_finance_board",
        "rpt_sales_commission_sync",
        "rpt_regional_performance",
        "rpt_cohort_retention",
        "rpt_daily_pipeline",
    ]
    for r in reporting_models:
        uid = f"model.enterprise.{r}"
        nodes[uid] = {
            "name": r,
            "resource_type": "model",
            "original_file_path": f"models/reporting/{r}.sql",
            "tags": ["reporting", "executive"],
            "depends_on": {"nodes": ["model.enterprise.fct_orders"]},
        }
        child_map[uid] = []
        child_map["model.enterprise.fct_orders"].append(uid)

    # Exposures
    exposures = {
        "exposure.enterprise.exec_arr_dashboard": {
            "name": "exec_arr_dashboard",
            "label": "Executive ARR Dashboard",
            "type": "dashboard",
            "owner": {"name": "Chief Financial Officer", "email": "cfo@enterprise.com"},
            "depends_on": {"nodes": ["model.enterprise.rpt_executive_kpis"]},
        },
        "exposure.enterprise.board_financials": {
            "name": "board_financials",
            "label": "Board Financials Summary",
            "type": "dashboard",
            "owner": {"name": "VP Finance", "email": "vp_finance@enterprise.com"},
            "depends_on": {"nodes": ["model.enterprise.rpt_monthly_finance_board"]},
        },
        "exposure.enterprise.sales_commission_sync": {
            "name": "sales_commission_sync",
            "label": "Sales Commission Sync",
            "type": "reverse_etl",
            "owner": {"name": "Sales Ops", "email": "revops@enterprise.com"},
            "depends_on": {"nodes": ["model.enterprise.rpt_sales_commission_sync"]},
        },
    }

    # Add SQL code for column-level lineage AST resolution
    nodes["model.enterprise.stg_orders"]["raw_code"] = """
    SELECT
        order_id,
        customer_id,
        status,
        order_total * 0.95 as net_booked_amount,
        order_date
    FROM {{ ref('raw_orders') }}
    WHERE status NOT IN ('returned', 'cancelled');
    """

    nodes["model.enterprise.int_customer_orders"]["raw_code"] = """
    SELECT
        order_id,
        customer_id,
        order_date,
        net_booked_amount
    FROM {{ ref('stg_orders') }};
    """

    nodes["model.enterprise.fct_orders"]["raw_code"] = """
    SELECT
        order_id,
        customer_id,
        order_date as order_placed_date,
        net_booked_amount * 1.1 as gross_amount
    FROM {{ ref('int_customer_orders') }};
    """

    nodes["model.enterprise.rpt_monthly_finance_board"]["raw_code"] = """
    SELECT
        order_placed_date,
        SUM(gross_amount) as total_gross
    FROM {{ ref('fct_orders') }}
    GROUP BY 1;
    """

    nodes["model.enterprise.rpt_executive_kpis"]["raw_code"] = """
    SELECT
        order_placed_date as kpi_date,
        COUNT(order_id) as total_orders
    FROM {{ ref('fct_orders') }}
    GROUP BY 1;
    """

    # Link reporting models to exposures in child_map
    child_map["model.enterprise.rpt_executive_kpis"].append(
        "exposure.enterprise.exec_arr_dashboard"
    )
    child_map["model.enterprise.rpt_monthly_finance_board"].append(
        "exposure.enterprise.board_financials"
    )
    child_map["model.enterprise.rpt_sales_commission_sync"].append(
        "exposure.enterprise.sales_commission_sync"
    )

    return {
        "nodes": nodes,
        "exposures": exposures,
        "parent_map": {},
        "child_map": child_map,
    }


def create_demo_report() -> BlastRadiusReport:
    """Creates the simulation BlastRadiusReport for demo or testing."""
    start_time = time.perf_counter()

    # 1. Base SQL vs Head SQL: Simulates both filter tightening and dropped column 'order_date'
    base_sql = """
    SELECT
        order_id,
        customer_id,
        status,
        order_total * 0.95 as net_booked_amount,
        order_date
    FROM {{ ref('raw_orders') }}
    WHERE status NOT IN ('returned', 'cancelled');
    """

    head_sql = """
    SELECT
        order_id,
        customer_id,
        status,
        order_total * 0.95 as net_booked_amount
    FROM {{ ref('raw_orders') }}
    WHERE status = 'delivered';
    """

    # 2. AST Diffing
    ast_engine = ASTDiffEngine(default_dialect="snowflake")
    ast_diff = ast_engine.diff_model(
        model_name="stg_orders",
        file_path="models/staging/stg_orders.sql",
        base_sql=base_sql,
        head_sql=head_sql,
        dialect="snowflake",
    )

    # 3. In-memory DAG Lineage & Column-Level Lineage Tracing
    manifest_data = build_demo_manifest_data()
    manifest = DbtManifest(
        nodes=manifest_data["nodes"],
        exposures=manifest_data["exposures"],
        parent_map={},
        child_map=manifest_data["child_map"],
    )
    lineage = LineageGraph(manifest)

    dropped_or_modified = {}
    if ast_diff.dropped_columns:
        dropped_or_modified["model.enterprise.stg_orders"] = ast_diff.dropped_columns

    downstream_models, impacted_exposures, max_depth = lineage.get_downstream_blast_radius(
        modified_model_ids=["model.enterprise.stg_orders"],
        dropped_or_modified_columns=dropped_or_modified,
        dialect="snowflake",
    )
    dag_edges = lineage.get_subgraph_edges(modified_model_ids=["model.enterprise.stg_orders"])

    # 4. Risk Evaluation
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    risk_engine = RiskEngine(tier_tags=["tier_1", "finance", "executive", "board"])
    return risk_engine.evaluate(
        modified_models=["models/staging/stg_orders.sql"],
        ast_diffs=[ast_diff],
        downstream_models=downstream_models,
        impacted_exposures=impacted_exposures,
        max_dag_depth=max_depth,
        execution_duration_ms=duration_ms,
        dag_edges=dag_edges,
    )


def run_demo(
    console: Console | None = None,
    output_format: str = "terminal",
    output_file: str | None = None,
) -> BlastRadiusReport:
    """Run the packaged filter tightening simulation."""
    c = console or Console()
    report = create_demo_report()

    if output_format == "html" or (output_file and output_file.endswith(".html")):
        from parallax.cli.formatters.html import HTMLFormatter

        html_out = HTMLFormatter.render(report)
        target = Path(output_file or "blast_radius_report.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_out, encoding="utf-8")
        c.print(
            f"[bold green]Parallax HTML demo report written to: {target.resolve()}[/bold green]"
        )
        return report

    if output_format == "markdown" or (output_file and output_file.endswith(".md")):
        from parallax.cli.formatters.markdown import MarkdownFormatter

        md_out = MarkdownFormatter.render(report)
        if output_file:
            target = Path(output_file)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(md_out, encoding="utf-8")
            c.print(
                f"[bold green]Parallax Markdown demo report written to: {target.resolve()}[/bold green]"
            )
        else:
            c.print(md_out)
        return report

    if output_format == "json" or (output_file and output_file.endswith(".json")):
        import json

        json_out = json.dumps(report.model_dump(), indent=2)
        if output_file:
            target = Path(output_file)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json_out, encoding="utf-8")
            c.print(
                f"[bold green]Parallax JSON demo report written to: {target.resolve()}[/bold green]"
            )
        else:
            c.print(json_out)
        return report

    formatter = TerminalFormatter(console=c)
    formatter.render(report, base_ref="main", head_ref="pr/clean-order-filter")
    return report
