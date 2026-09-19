# Lineage DAG & Blast Radius

Parallax evaluates semantic changes in the context of your entire data pipeline, from raw staging models to executive BI dashboards.

---

## dbt Manifest Ingestion

When dbt runs `dbt compile`, it generates `target/manifest.json`. This file contains complete metadata about:
- Models, seeds, snapshots, and sources
- Directed acyclic graph (DAG) dependencies (`depends_on.nodes`)
- Column-level schemas and data types
- Exposures (external dashboards, ML pipelines, and reverse-ETL jobs)

Parallax loads this manifest into an in-memory **NetworkX** directed graph in milliseconds.

---

## Layer-Aware Traversal

When a model is modified, Parallax traverses all downstream nodes and categorizes them into standard analytics engineering layers:

| Layer | Typical Prefix / Path | Blast Radius Implication |
| :--- | :--- | :--- |
| **Intermediate** | `int_` | Internal data preparation; high ripple risk to downstream marts |
| **Marts** | `fct_`, `dim_` | Core business entity representations used across teams |
| **Reporting** | `rpt_` | End-user tables feeding dashboards and metric layers |

Each downstream node is annotated with its **hop distance** (topological depth) from the modified model.

---

## BI Exposure Detection

dbt exposures declare downstream consumers outside of dbt (e.g. Looker dashboards, Tableau workbooks, Census/Hightouch reverse-ETL syncs).

Parallax identifies all exposures downstream of altered models and surfaces:
- **Exposure Name & Label** (e.g. `Board Financials Summary`)
- **Exposure Type** (`dashboard`, `notebook`, `analysis`, `ml`, `reverse_etl`)
- **Business Owner** (e.g. `Chief Financial Officer`, `VP Finance`)

This alerts the pull request author and reviewers when an upstream refactor directly jeopardizes executive-facing reports or automated operational syncs.

---

## Column Lineage Propagation

If an upstream model drops or renames a column (e.g. `order_amount`), Parallax checks whether any downstream models explicitly reference that column. If detected, Parallax flags them as **breaking column references**, elevating the risk level to **CRITICAL**.
