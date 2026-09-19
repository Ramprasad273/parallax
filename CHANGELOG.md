# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-09-12

### Added
- **AST Semantic Diff Engine**:
  - Pure-Python SQL AST diffing powered by SQLGlot across 25+ SQL dialects (Snowflake, BigQuery, Postgres, DuckDB, Databricks, ANSI).
  - Deterministic boolean conjunct flattening to classify predicate changes (`TIGHTENED`, `LOOSENED`, `DROPPED`, `MUTATED_OPERATOR`).
  - Projection list diffing detecting dropped columns and expression modifications (`EXPRESSION_ALTERED`, `DROPPED`).
  - Join structure analysis detecting join type mutations (e.g. `INNER JOIN` -> `LEFT JOIN`).
  - Group By dimension cardinality tracking.
- **Lineage Blast Radius & Column Lineage DAG Engine**:
  - In-memory directed acyclic graph built from dbt `target/manifest.json` using NetworkX.
  - Multi-hop static Column-Level Lineage (CLL) engine powered by SQLGlot AST expression trees, tracing column mutations across intermediate and reporting layers.
  - Exact column derivation path tracking with case-insensitive dialect resolution (Snowflake, BigQuery, Postgres, DuckDB).
  - Shortest path distance calculations to all downstream models and BI exposures.
  - Exposure impact tracking across Looker, Tableau, Reverse ETL, and ML models.
  - Robust broken schema contract detection across downstream consumers with regex fallback.
- **Multi-Factor Risk Scoring Engine**:
  - Four risk tiers: `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW`.
  - Configurable `fail_on` gate to block PR merges when severity meets or exceeds threshold.
  - Tier-1 and executive exposure elevation logic.
- **Developer Surfaces**:
  - Rich CLI output with interactive terminal tables, blast radius trees, and execution timers (`parallax check`, `parallax demo`).
  - Standalone interactive HTML blast-radius report (`parallax report`) with responsive SVG DAG visualization, node inspection drawer, and copyable remediation checklists.
  - Markdown summary generation with collapsible diff cards for CI PR comments.
  - GitHub Action composite step (`action.yml`) with automated pinned PR commenting and deduplication via HTML markers.
  - Built-in interactive demo simulation reproducing upstream predicate tightening and downstream exposure blast radius with zero credentials or dbt compile required.
- **Configuration & Extensibility**:
  - Optional `.parallax.yml` configuration for custom governance tiers, ignore patterns, and dialect settings.
