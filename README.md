# Parallax

[![CI](https://github.com/parallax-ci/parallax/actions/workflows/ci.yml/badge.svg)](https://github.com/parallax-ci/parallax/actions)
[![PyPI](https://img.shields.io/pypi/v/parallax-ci.svg)](https://pypi.org/project/parallax-ci/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/PR_Check_Speed-%3C0.5s-brightgreen)](#performance)

> **Zero-Config Blast Radius & Semantic Drift CI for SQL and dbt.**  
> Catches silent business logic corruption and maps downstream dashboard breakage before your PR is merged.

---

## 💥 The Acute Problem

Modern analytics engineering teams rely on **SQLFluff** (linters) and **dbt tests** (`unique`, `not_null`). Both fail silently when query logic shifts subtly:

```diff
-- models/staging/stg_orders.sql
- WHERE status NOT IN ('returned', 'cancelled')
+ WHERE status = 'delivered'
```

1. **Linters are blind:** SQLFluff checks indentation, commas, and casing. The SQL syntax is 100% valid.
2. **dbt tests are blind:** The surviving delivered orders are still unique and non-null. All unit tests pass.
3. **The Silent Catastrophe:** The original query included orders in `'processing'` and `'in_transit'` (which count toward booked revenue under corporate accounting rules). The new filter silently erased **12% of total pipeline**—wiping out **$3.8M in ARR** from downstream executive dashboards for 3 months before anyone noticed.

---

## 🛡️ The Solution: Parallax

Parallax runs directly in GitHub Actions or your local terminal in **< 0.5 seconds**. It:
1. **Parses SQL ASTs:** Compares the Git diff between branches using [`sqlglot`](https://github.com/tobymao/sqlglot) to catch predicate tightening, loosened conditions, dropped columns, and mutated join types.
2. **Walks the dbt DAG:** Ingests `target/manifest.json` and uses [`networkx`](https://networkx.org/) to trace every downstream staging model, mart, and Looker/Tableau executive exposure.
3. **100% Static & In-Memory:** Requires **zero warehouse credentials**, zero staging database spins, and zero query cost.
4. **Never Spams PRs:** If a PR contains only cosmetic formatting or comment edits, Parallax runs silently with zero false-positive noise.

---

## ⚡ 10-Second Quickstart

Try the built-in horror story simulation with **zero setup**:

```bash
pip install parallax-ci
parallax demo
```

Or run it instantly without installing via `uvx`:
```bash
uvx parallax-ci demo
```

### Visual Terminal Output (`parallax demo` in 11ms):
```text
PARALLAX • Blast Radius & Semantic Drift CI
Comparing: main...pr/clean-order-filter  |  Duration: 11.15ms

┌───────────────────────────── Impact Assessment ─────────────────────────────┐
│  CRITICAL RISK                                                              │
│                                                                             │
│ 🚨 **CRITICAL RISK:** PR tightened filter `NOT status IN ('returned',       │
│ 'cancelled')` -> `status = 'delivered'` on `stg_orders`. This cascades      │
│ across **18 downstream models** and impacts **3 Executive Exposures**       │
│ (`Board Financials Summary`, `Executive ARR Dashboard`, `Sales Commission   │
│ Sync`).                                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

           Blast Radius Metrics            
┌──────────────────────────────┬──────────┐
│ Metric                       │ Value    │
├──────────────────────────────┼──────────┤
│ Modified Models              │ 1        │
│ Impacted Downstream Models   │ 18       │
│ Impacted BI Exposures        │ 3        │
│ Max Lineage DAG Depth        │ 4 layers │
│ Breaking Column Mutations    │ 0        │
└──────────────────────────────┴──────────┘

                              AST Semantic Diffs                               
┌────────────┬──────────┬───────────┬────────────────────┬────────────────────┐
│ Model      │ Category │ Type      │ Original           │ New / Altered      │
├────────────┼──────────┼───────────┼────────────────────┼────────────────────┤
│ stg_orders │ WHERE    │ TIGHTENED │ NOT status IN      │ status =           │
│            │          │           │ ('returned',       │ 'delivered'        │
│            │          │           │ 'cancelled')       │                    │
└────────────┴──────────┴───────────┴────────────────────┴────────────────────┘

┌───────────────────── Downstream Lineage & Blast Radius ─────────────────────┐
│ Modified Models: models/staging/stg_orders.sql                              │
│ ├── int_customer_orders (layer: intermediate, depth: 1)                     │
│ ├── int_net_payments (layer: intermediate, depth: 1)                        │
│ ├── fct_orders (layer: marts, depth: 2)                                     │
│ ├── rpt_executive_kpis (layer: reporting, depth: 3)                         │
│ ├──  📊 EXPOSURE: Board Financials Summary  (dashboard)                     │
│ ├──  📊 EXPOSURE: Executive ARR Dashboard  (dashboard)                      │
│ └──  📊 EXPOSURE: Sales Commission Sync  (reverse_etl)                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 GitHub Actions Integration

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
        uses: parallax-ci/action@v1
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

## 🛠️ CLI Usage

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

## ⚙️ Configuration (`.parallax.yml`)

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

---

## 🏛️ Architecture & Guiding Principles

| Principle | Engineering Implementation |
| :--- | :--- |
| **Zero Warehouse Credentials** | 100% static analysis of ASTs and dbt metadata. Never touches live warehouse credentials. |
| **Sub-Second Speed** | In-memory NetworkX DAG resolution and SQLGlot AST traversals complete in **< 0.5s** for 2,000+ models. |
| **Zero Noise** | Non-semantic PRs (whitespace, formatting, isolated docs) produce **0 comments**. |
| **Deterministic Explainer** | Algorithmic synthesis generates plain-English executive summaries without flaky or costly LLMs. |

---

## 🧪 Testing & Quality Standards

```bash
# Run full test suite (55 unit & integration tests)
pytest -v --cov=parallax

# Run static linter & typechecker
ruff check parallax tests
mypy parallax tests
```

---

## 📄 License

Apache 2.0. Created by the Parallax Open Source Community.
