# Parallax

[![CI](https://github.com/parallax-ci/parallax/actions/workflows/ci.yml/badge.svg)](https://github.com/parallax-ci/parallax/actions)
[![PyPI](https://img.shields.io/pypi/v/parallax-ci.svg)](https://pypi.org/project/parallax-ci/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/PR_Check_Speed-%3C0.5s-brightgreen)](#performance)

> **Zero-Config Blast Radius & Semantic Drift CI for SQL and dbt.**  
> Catches silent business logic corruption and maps downstream dashboard breakage before your PR is merged.

---

## The Problem

Modern analytics engineering teams rely on **SQLFluff** (linters) and **dbt tests** (`unique`, `not_null`). Both fail silently when query logic shifts subtly:

```diff
-- models/staging/stg_orders.sql
- WHERE status NOT IN ('returned', 'cancelled')
+ WHERE status = 'delivered'
```

1. **Linters are blind:** SQLFluff checks indentation, commas, and casing. The SQL syntax is 100% valid.
2. **dbt tests are blind:** The surviving delivered orders are still unique and non-null. All unit tests pass.
3. **The Silent Regression:** The original query included orders in `'processing'` and `'in_transit'`. The new filter silently dropped them from all downstream models, corrupting downstream marts and executive reporting dashboards while all unit tests remained green.

---

### The Solution

Parallax runs directly in GitHub Actions or your local terminal in **< 0.5 seconds** (for in-memory DAG traversal; total wall time includes Git I/O and SQL parsing). It:
1. **Parses SQL ASTs:** Compares the Git diff between branches using [`sqlglot`](https://github.com/tobymao/sqlglot) to catch predicate tightening, loosened conditions, dropped columns, and mutated join types.
2. **Walks the dbt DAG:** Ingests `target/manifest.json` and uses [`networkx`](https://networkx.org/) to trace every downstream staging model, mart, and Looker/Tableau executive exposure.
3. **Static & In-Memory:** Requires **zero warehouse credentials**, zero staging database spins, and zero query cost.
4. **Signal-Focused:** If a PR contains only cosmetic formatting or comment edits, Parallax runs silently with zero false-positive review noise.

---

## Quickstart

Try the built-in simulation with **zero setup**:

```bash
# Using uv (recommended)
uv run parallax demo

# Or with pip
pip install parallax-ci
parallax demo

# Or run instantly without installing via uvx
uvx parallax-ci demo
```

### Visual Terminal Output (`parallax demo` in ~11ms):
```text
────────────────────────────  PARALLAX  Blast Radius & Semantic Drift  ─────────────────────────────
  main  >  pr/clean-order-filter    2026-09-12 15:26 UTC    11.4 ms

╭─  RISK: CRITICAL  ───────────────────────────────────────────────────────────────────────────────╮
│  CRITICAL RISK: PR tightened filter `NOT status IN ('returned', 'cancelled')` -> `status =       │
│  'delivered'` on `stg_orders`. This cascades across 18 downstream models and impacts 3           │
│  Executive Exposures (`Board Financials Summary`, `Executive ARR Dashboard`, `Sales Commission   │
│  Sync`).                                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

╭─ Overview ───────────────────────────────────────────────────────────────────────────────────────╮
│   Modified models                           1                                                    │
│   Downstream models impacted               18                                                    │
│   BI exposures affected                     3                                                    │
│   Longest lineage path (hops)               4                                                    │
│   Breaking column references             none                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

────────────────────────────────────────  Semantic Changes  ────────────────────────────────────────

╭──────────────────────────────────────────────────────────────────────────────────────────────────╮
│  Model    stg_orders                                                                             │
│  Scope    WHERE                                                                                  │
│  Change   TIGHTENED                                                                              │
│  Before   NOT status IN ('returned', 'cancelled')                                                │
│  After    status = 'delivered'                                                                   │
│  Note     Filter tightened from negative exclusion (NOT status IN ('returned', 'cancelled')) to  │
│           strict match (status = 'delivered'), omitting unhandled categories.                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

────────────────────────────────────  Downstream Blast Radius  ─────────────────────────────────────

  Downstream Models

  INTERMEDIATE  4 models  (hop 1)
    int_customer_orders
    int_net_payments
    int_order_items
    int_subscription_periods

  MARTS  8 models  (hop 2)
    dim_customers
    dim_products
    dim_sales_reps
    dim_subscriptions
    fct_churn_daily
    fct_customer_transactions
    fct_mrr_monthly
    fct_orders

  REPORTING  6 models  (hop 3)
    rpt_cohort_retention
    rpt_daily_pipeline
    rpt_executive_kpis
    rpt_monthly_finance_board
    rpt_regional_performance
    rpt_sales_commission_sync

  Impacted BI Exposures
  Exposure                     Type              Owner                    
──────────────────────────────────────────────────────────────────────────
  Board Financials Summary     DASHBOARD         VP Finance               
  Executive ARR Dashboard      DASHBOARD         Chief Financial Officer  
  Sales Commission Sync        REVERSE_ETL       Sales Ops                

──────────────────────────────────────  Recommended Actions  ───────────────────────────────────────

   1.  Verify business metrics: Confirm that filter/calculation changes do not unintentionally
       alter executive metrics on: Board Financials Summary, Executive ARR Dashboard, Sales
       Commission Sync.
   2.  Audit dropped records: Confirm whether omitting non-matching statuses (e.g.
       pending/in-transit/disputed) was intended by business stakeholders.

─────────────────────────────────────────  CI gate: BLOCK  ─────────────────────────────────────────
  github.com/parallax-ci/parallax
```

---

## GitHub Actions Integration

Drop this 6-line step into your `.github/workflows/dbt_ci.yml` after `dbt compile`:

```yaml
name: "dbt CI"
on:
  pull_request:
    paths:
      - "models/**"

jobs:
  blast_radius_check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Compile dbt Manifest
        run: dbt compile

      - name: Run Parallax Blast Radius CI
        uses: parallax-ci/parallax@v0.1.0  # Or pin to full commit SHA for immutable CI
        with:
          manifest: target/manifest.json
          fail_on: CRITICAL
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

### GitHub PR Comment Features:
* **In-Place Updates:** Pinned comment updates on subsequent commits (zero PR spam).
* **Native Step Summary:** Writes interactive reports to `$GITHUB_STEP_SUMMARY`.
* **Collapsible Details:** `<details>` cards for line-by-line AST diffs and lineage paths.
* **Gated Merges:** Blocks the PR with exit code `1` if risk $\ge$ failure threshold.

---

## CLI Usage

```bash
# Check local working tree or branch diff
parallax check --manifest target/manifest.json --base origin/main

# Block CI on HIGH or CRITICAL severity
parallax check --fail-on HIGH

# Output markdown for PR comments
parallax check --format markdown --output pr_comment.md

# Output machine-readable JSON for custom pipelines
parallax check --format json

# Generate standalone offline HTML report
parallax report --out blast_radius_report.html

# Run instant demo
parallax demo
```

---

## Configuration (`.parallax.yml`)

Parallax works with zero configuration by default. For custom governance rules, place `.parallax.yml` in your repository root:

```yaml
version: 1
dialect: snowflake # Options: snowflake, bigquery, postgres, duckdb, databricks
manifest_path: target/manifest.json
base_ref: origin/main
fail_on: CRITICAL  # Options: LOW, MEDIUM, HIGH, CRITICAL, NEVER

tier_tags:
  - tier_1
  - finance
  - executive
  - board

ignore_patterns:
  - "models/sandbox/**"
  - "models/dev_*"
```

## Core Tenets & Operating Principles

| Tenet | Engineering Implementation |
| :--- | :--- |
| **Static Analysis by Design** | Evaluates SQL ASTs and dbt metadata without requiring database credentials, creating staging databases, or incurring cloud query costs. |
| **Sub-Second Execution** | In-memory NetworkX DAG resolution completes in **< 0.5s** for 2,000+ models (total wall time includes Git I/O and SQL parsing). |
| **Signal-to-Noise Priority** | Non-semantic PRs (whitespace, formatting, isolated comment edits) are evaluated as zero-risk, avoiding PR review noise. |
| **Deterministic Synthesis** | Rule-based algorithmic synthesis generates plain-English summaries without external or nondeterministic LLMs. |

### Git File Rename Handling

In `v0.1.0`, Parallax invokes Git diff with `--no-renames`. This intentionally treats a file relocation or rename (such as `git mv models/staging/stg_orders.sql models/core/stg_orders.sql`) as a `DROP` of the previous path and an `ADD` of the new path. This conservative design ensures that any downstream models or BI exposures still pointing to the old path are flagged for breaking references. Heuristic rename tracking will be introduced in a future release.

---

## Disclaimer & Limitations

Parallax performs static syntactic and dependency analysis based on SQL ASTs and dbt metadata. It does not inspect runtime warehouse data rows or validate dynamic query execution plans. Downstream column lineage uses static AST expression trees (powered by SQLGlot) with multi-hop derivation tracing and heuristic fallback; while robust across complex pipelines, it is best-effort static analysis and complements rather than replaces full warehouse execution. As provided under the Apache 2.0 license, this tool is distributed on an "AS IS" basis, without warranties or conditions of any kind. Teams should use Parallax as an automated safety layer alongside automated testing and code review.

---

## Testing & Quality Standards

```bash
# Run full test suite with coverage
pytest -v --cov=parallax --cov-report=term-missing

# Run static linter & typechecker
ruff check parallax tests
mypy parallax tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full developer environment setup and dialect contribution guidelines.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

---

## License

Apache 2.0. Created by the Parallax Open Source Community.
