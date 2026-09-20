# Parallax

[![CI](https://img.shields.io/github/actions/workflow/status/Ramprasad273/parallax/ci.yml?branch=main&label=CI&style=flat-square)](https://github.com/Ramprasad273/parallax/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.1.0-blue?style=flat-square)](https://github.com/Ramprasad273/parallax/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?style=flat-square)](https://www.python.org/)

> **Zero-Config Blast Radius & Semantic Drift CI for SQL and dbt.**  
> Catches silent business logic corruption and maps downstream dashboard breakage before your PR is merged.
>
> *dbt™ is a registered trademark of dbt Labs, Inc. Parallax is an independent open-source project and is not affiliated with, sponsored by, or endorsed by dbt Labs, Inc.*

<p align="center">
  <img src="docs/assets/images/parallax-walkthrough.gif" alt="Parallax Walkthrough: Terminal CLI to HTML Report to GitHub Actions CI Gate" width="820">
</p>

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

Parallax runs directly in GitHub Actions or your local terminal with zero warehouse connections. It:
1. **Parses SQL ASTs:** Compares the Git diff between branches using [`sqlglot`](https://github.com/tobymao/sqlglot) to catch predicate tightening, loosened conditions, dropped columns, and mutated join types.
2. **Walks the dbt DAG:** Ingests `target/manifest.json` and uses [`networkx`](https://networkx.org/) to trace every downstream staging model, mart, and Looker/Tableau executive exposure.
3. **Static & In-Memory:** Requires **zero warehouse credentials**, zero staging database spins, and zero query cost.
4. **Signal-Focused:** If a PR contains only cosmetic formatting or comment edits, Parallax runs silently with zero false-positive review noise.

---

## End-to-End Workflow

Parallax provides automated blast radius defense across every stage of development:

<details open>
<summary><b>1. Local Pre-Commit Scan &mdash; <code>parallax check</code></b></summary>
<br>

Run instantly in your local development terminal before opening a pull request. Compares your branch against `main` in milliseconds without touching the data warehouse:

- **Semantic AST Detection:** Catches tightened filters, dropped columns, and altered calculations.
- **Immediate Terminal Feedback:** Flags `CRITICAL RISK` and lists breaking downstream references before code leaves your machine.

<p align="center">
  <a href="docs/assets/images/cli-report.png"><img src="docs/assets/images/cli-report.png" alt="Local Terminal CLI Report" width="100%"></a>
</p>

</details>

<details open>
<summary><b>2. Interactive Standalone Report &mdash; <code>parallax report</code></b></summary>
<br>

Generates a zero-dependency, self-contained HTML artifact with browser-based interactive exploration:

- **Deterministic DAG Lineage:** Visualizes the full path from modified upstream models to impacted Looker/Tableau dashboards.
- **Broken Column Contracts:** Lists exact downstream models that will fail compilation or throw runtime exceptions.
- **Column-Level Lineage Chains:** Multi-hop provenance tracing for modified metrics.

<p align="center">
  <a href="docs/assets/images/html-report.png"><img src="docs/assets/images/html-report.png" alt="Interactive HTML Report" width="100%"></a>
</p>

</details>

<details open>
<summary><b>3. Automated GitHub Actions CI Gate</b></summary>
<br>

Runs inside your GitHub Actions pipeline on pull requests with zero warehouse credentials or staging databases:

- **Automated PR Audits:** Posts actionable, structured blast radius summaries directly onto pull requests.
- **Merge Protection:** Automatically fails status checks (`CI Gate: BLOCK`) on breaking schema drifts or critical exposure regressions.

<p align="center">
  <a href="docs/assets/images/github-ci-pr.png"><img src="docs/assets/images/github-ci-pr.png" alt="GitHub Actions CI PR Gate" width="100%"></a>
</p>

</details>

---

## Quickstart

Try the built-in simulation with **zero setup**:

```bash
# Install directly from GitHub
pip install git+https://github.com/Ramprasad273/parallax.git

# Or clone and install in editable mode
git clone https://github.com/Ramprasad273/parallax.git
cd parallax
pip install -e .

# Run instant demo
parallax demo
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
  github.com/Ramprasad273/parallax
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
        uses: Ramprasad273/parallax@v0.1.0  # Or @main
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
| **In-Memory Graph Analysis** | Traverses downstream model and exposure dependencies via NetworkX in memory without database roundtrips. |
| **Signal-to-Noise Priority** | Non-semantic PRs (whitespace, formatting, isolated comment edits) are evaluated as zero-risk, avoiding PR review noise. |
| **Deterministic Synthesis** | Rule-based algorithmic synthesis generates plain-English summaries without external or nondeterministic LLMs. |
| **Zero Telemetry** | Collects zero usage data, phone-home beacons, or external telemetry. The only network call is to `api.github.com` via your own `GITHUB_TOKEN` to post PR comments. |
| **Graceful Degradation (Zero CI Crash)** | If vendor-specific SQL extensions or macro syntax cannot be parsed into an AST, Parallax gracefully preserves full topological DAG lineage from `manifest.json` and issues a non-blocking diagnostic warning instead of crashing CI. |

---

## Performance Benchmarks

Parallax evaluates semantic diffs and graph lineage completely in memory:

| Project Size | Models | DAG Depth | Total Execution |
| :--- | :--- | :--- | :--- |
| **Small project** | ~50 models | 4 hops | ~0.28s |
| **Mid-market team** | ~350 models | 8 hops | ~0.85s |
| **Enterprise monorepo** | ~1,800+ models | 14 hops | ~2.40s |

*Benchmarks measured on local developer environments with cached manifests. Performance scales with project size and number of modified files.*

---

### Git File Rename Handling

In `v0.1.0`, Parallax invokes Git diff with `--no-renames`. This intentionally treats a file relocation or rename (such as `git mv models/staging/stg_orders.sql models/core/stg_orders.sql`) as a `DROP` of the previous path and an `ADD` of the new path. This conservative design ensures that any downstream models or BI exposures still pointing to the old path are flagged for breaking references. Heuristic rename tracking will be introduced in a future release.

---

## Disclaimer & Limitations

Parallax performs static syntactic and dependency analysis based on SQL ASTs and dbt metadata:
- **Predicate Analysis:** Boolean conjuncts (`AND`) are decomposed into discrete terms. For compound `OR` conditions and complex nested boolean algebra, Parallax treats the condition as an atomic unit and classifies modifications conservatively as `MUTATED_OPERATOR`. Full boolean equivalence for arbitrary SQL is an NP-hard problem intentionally bounded for sub-second CI performance.
- **Runtime Data:** Parallax does not inspect runtime warehouse data rows, live database partitions, or table grants.
- **Column Lineage:** Downstream column lineage uses static AST expression trees (powered by SQLGlot) with multi-hop derivation tracing and heuristic fallback. While robust across complex pipelines, it is best-effort static analysis and complements rather than replaces full warehouse execution.

**Legal Disclaimer:** As provided under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0), this tool is distributed on an "AS IS" basis, without warranties or conditions of any kind, either express or implied (Section 7). In no event shall any contributor be liable for any direct, indirect, incidental, or consequential damages (Section 8). Teams should use Parallax as an automated safety layer alongside automated testing, linters, and human peer review.

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
