# Product Requirements Document (PRD)

## Product: Parallax
**Tagline:** Zero-Config Blast Radius & Semantic Drift CI for SQL and dbt  
**Target Release:** Single Open-Source Release (v1.0.0) + Flagship Blog Post & Viral Demo  
**Status:** Approved for Implementation  
**Author:** Senior Product Manager  

---

## 1. Executive Summary & Vision

### 1.1 The Problem
In modern data teams, analytical code changes are governed by SQLFluff (style/syntax) and automated unit/data tests (dbt tests). Both fail silently when code logic shifts subtly:
1. **Linter Blindness:** Linters verify commas, casing, and indentation. They do not understand that changing `WHERE status != 'cancelled'` to `WHERE status = 'active'` drops edge cases (e.g., 'pending', 'disputed', 'legacy').
2. **Test Blindness:** Standard dbt tests (`unique`, `not_null`, `relationships`) test data integrity constraints, not **semantic drift**. A query with a restricted filter still produces non-null, unique customer IDs—while silently wiping out 12% of calculated Gross Merchandise Value (GMV).
3. **Downstream Blast Radius Opacity:** Analytics engineers modifying an upstream staging or intermediate model have no visibility into how many executive BI dashboards, metrics, or gold-tier reporting tables rely on the mutated columns. By the time a discrepancy is caught, 90 days of executive decision-making and operational tables have been corrupted.

### 1.2 The Solution
**Parallax** is an open-source, zero-config CLI and GitHub Action that performs **static, dialect-aware semantic diffing and downstream lineage blast-radius mapping on every PR**.
* **100% Static & In-Memory:** Requires **zero warehouse credentials**, zero staging database spins, and zero query cost. Analyzes SQL ASTs (via `sqlglot`) and dbt artifacts (`manifest.json` via `networkx`).
* **Runs in < 10 seconds** directly in GitHub Actions.
* **Outputs high-signal, visual PR comments and terminal graphs** that flag exact logical drifts, dropped edge cases, downstream model counts, and broken BI exposures.

### 1.3 The Launch Goal
Because this product follows a **single-release, maximum-impact strategy**, the open-source release must be self-contained, completely reproducible with a single command, visually arresting on GitHub and Twitter, and backed by a narrative-driven technical blog post for Hacker News.

---

## 2. Guiding Principles & Non-Negotiables

| Principle | Non-Negotiable Rule | Rationale |
| :--- | :--- | :--- |
| **Zero Warehouse Credentials** | Zero connection strings (no Snowflake/BigQuery/Postgres credentials needed). | Removes 100% of enterprise security friction. Teams can adopt it in 2 minutes without infosec approval. |
| **Zero False-Positive Spam** | Do not comment on PRs if there is no semantic or lineage impact (e.g., pure formatting, comments, or isolated leaf model docs). | Developers instantly uninstall noisy bots. Parallax only interrupts when real risk exists. |
| **Instant CI Execution** | Entire analysis must complete in under 10 seconds for repos with up to 2,000 dbt models. | Developers will not tolerate slow CI checks for simple SQL PRs. |
| **High Visual Polish** | Terminal output and PR comments must look like handcrafted human engineering reports, complete with ASCII trees, ANSI color-coding, and markdown collapsible cards. | Drives virality, screenshots on social media, and immediate comprehension. |
| **1-Command Demo** | A bundled demo command (`parallax demo`) must run an end-to-end simulation out of the box with zero configuration or installation prerequisites beyond Python. | Crucial for immediate user validation and Hacker News demo evaluations. |

---

## 3. User Personas & Core Workflows

### 3.1 Primary Personas
* **Lead Analytics Engineer / Data Platform Lead:** Responsible for warehouse health, dbt CI/CD standards, and preventing executive dashboard breakage. Wants a drop-in GitHub Action that enforces semantic safety across junior analysts and external contributors.
* **Analytics Engineer / Data Analyst (PR Author):** Edits upstream SQL models. Needs immediate, local, and PR-level feedback on what downstream models or dashboards they might inadvertently break before merging.

### 3.2 Target User Workflows

```
[ Developer edits models/marts/fct_orders.sql on branch ]
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
Workflow A: Local CLI         Workflow B: GitHub Actions CI
`parallax check`              `uses: parallax-ci/action@v1`
         │                             │
  Sub-second terminal           Parses branch diff vs main
  rich blast-radius tree        Extracts dbt manifest.json
  & predicate diff table        Posts rich interactive PR comment
         │                             │
   Fix logic before push        Blocks PR if breaking change detected
```

---

## 4. Product Scope Matrix (Single-Release v1.0.0)

To achieve maximum virality and stability in a single release, features are strictly bifurcated:

### In Scope (Must-Have for v1.0.0)
1. **Dialect-Aware AST Semantic Diffing** (`sqlglot`): Detection of predicate drift (`WHERE`, `HAVING`, `JOIN ON`), column expression mutations, column additions/deletions/renames, and structural changes (`JOIN` types, `GROUP BY`, `UNION`).
2. **dbt DAG & Blast Radius Graph Engine** (`networkx` + `manifest.json`): Downstream dependency resolution, column-level propagation heuristic, and exposure identification (Looker, Tableau, Metabase, Hex, dbt metrics).
3. **Risk Scoring Engine:** Algorithmic calculation of a Risk Severity Level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) based on downstream reach and tier tags.
4. **Rich Terminal CLI:** Interactive, ANSI-colored terminal reports using `rich` with tree graphs and drift tables.
5. **GitHub Action & Automated PR Comment Bot:** Deterministic markdown generation, collapsible deep dives, status checks, and summary badges.
6. **Built-in Packaged Demo & Fixtures:** `parallax demo` showcasing the infamous "$3.8M silent WHERE-clause change" on an anonymized enterprise retail model.
7. **CI Step Summary Export:** Output to `$GITHUB_STEP_SUMMARY` and structured JSON for programmatic consumption.

### Explicitly Out of Scope (Post v1.0 / Commercial SaaS)
* Connecting to live warehouse instances (Snowflake, BigQuery) for live table row-level diffing.
* Web dashboard / hosted SaaS platform (everything runs in git / local CLI).
* Direct API integrations with Looker/Tableau cloud APIs (v1 uses dbt's native `exposures.yml` declarations).
* Automatic PR auto-fixing / AI code rewriting (flags issues, does not mutate user code).

---

## 5. Detailed Feature Specifications & Requirements

---

### Feature 1: Semantic AST Diff Engine (Core Compiler Layer)

#### 1.1 Purpose
Parse raw SQL files modified in the Git diff between the current PR branch and the merge base (default: `origin/main`), convert them into Abstract Syntax Trees (ASTs) via `sqlglot`, and extract structural and semantic changes.

#### 1.2 Functional Requirements
* **FR-1.1 Dialect Detection:** Automatically detect or configure SQL dialect (`snowflake`, `bigquery`, `postgres`, `duckdb`, `databricks`, `ansi`). Defaults to dialect defined in `dbt_project.yml` or fallback to `duckdb`.
* **FR-1.2 Jinja Pre-Processing / dbt Compilation Support:**
  * Support pre-compiled SQL files (standard output of `dbt compile` in `target/compiled/`).
  * If uncompiled files are provided, gracefully strip or mock standard dbt Jinja wrappers (`{{ config(...) }}`, `{{ ref(...) }}`, `{{ source(...) }}`) to allow valid AST generation without a full dbt compile cycle.
* **FR-1.3 Predicate Drift Analysis (High Severity):**
  * Extract AST nodes for `WHERE`, `HAVING`, and `JOIN ... ON` expressions for both original and modified queries.
  * Compare normalized boolean expressions. Detect:
    * **Filter Tightening/Loosening:** E.g., `status = 'active'` vs `status != 'cancelled'`.
    * **Removed Predicates:** E.g., an entire condition dropped from a multi-clause `AND` block.
    * **Inverted / Mutated Operators:** E.g., `>=` to `>`, `IS NOT NULL` to `IS NULL`.
* **FR-1.4 Column & Projection Mutations:**
  * Detect deleted columns (breaking schema change).
  * Detect renamed or aliased columns.
  * Detect altered column expressions (e.g., `amount * 0.9` changed to `amount * 0.85`, or `ROUND(val, 2)` to `TRUNC(val)`).
* **FR-1.5 Structural Mutations:**
  * Detect join type alterations (e.g., `INNER JOIN` altered to `LEFT JOIN`, introducing NULLs downstream).
  * Detect changes in `GROUP BY` cardinalities or `DISTINCT` additions.

---

### Feature 2: Lineage Graph & Blast Radius Engine

#### 2.1 Purpose
Ingest dbt's compiled graph artifact (`target/manifest.json`), construct an in-memory directed acyclic graph (DAG), and trace every downstream node affected by the modified SQL files.

#### 2.2 Functional Requirements
* **FR-2.1 Manifest Ingestion:**
  * Ingest `target/manifest.json` (supported schemas: dbt Core 1.5 through 1.9+).
  * Build a directed graph using `networkx.DiGraph`.
* **FR-2.2 Downstream Transitive Tracing:**
  * Given modified model $M$, find all descendant nodes $D = \text{descendants}(G, M)$.
  * Categorize descendants into:
    * **Downstream dbt Models:** Grouped by layer (`staging`, `intermediate`, `marts`, `reporting`).
    * **Exposures:** Downstream BI dashboards, notebooks, or operational syncs declared in dbt schema files (e.g. Looker dashboards, Tableau workbooks, Reverse ETL syncs).
    * **Metrics / Semantic Models:** Any dbt semantic layer elements dependent on $M$.
    * **Tests:** Downstream data tests that will be executed or bypassed.
* **FR-2.3 Column-Level Blast Radius Mapping:**
  * If column $C_k$ is dropped or modified in model $M$, inspect downstream models to check if $C_k$ is referenced in downstream compiled SQL or model schemas.
  * Explicitly flag downstream models where column reference breakage will occur.
* **FR-2.4 Critical Path & Exposure Tagging:**
  * Detect models tagged with high-visibility flags (e.g., `tags: ["tier_1", "finance", "executive", "board"]`).
  * Escalate blast-radius severity when Tier-1 models or executive exposures are in the direct downstream path.

---

### Feature 3: Risk Scoring & Heuristic Engine

#### 3.1 Purpose
Synthesize AST diffs and lineage depth into a single, unambiguous Risk Score with actionable signals, avoiding alarm fatigue.

#### 3.2 Scoring Matrix & Severity Levels

| Severity | Criteria / Triggers | Example | CI Default Action |
| :--- | :--- | :--- | :--- |
| **CRITICAL** | • Dropped or renamed column with downstream consumers.<br>• Predicate change in a model upstream of an Executive Exposure or `tier-1` tag. | Removing `order_id` or mutating `WHERE is_valid` upstream of CEO Revenue Dashboard. | Block PR (Exit code 1) |
| **HIGH** | • Filter alteration on a core Mart model with $> 5$ downstream models.<br>• Join type changed (e.g., `INNER` to `LEFT`). | Altering currency conversion logic in `fct_transactions`. | Warn + Request Reviewer Approval |
| **MEDIUM** | • Added/altered column calculation with no breaking schema impact.<br>• Filter change on leaf model with no exposures. | Adding discount calculation to an ad-hoc analyst table. | Informational Comment |
| **LOW** | • Non-semantic refactoring (alias reorganization, identical compiled SQL, comment additions). | Indentation or trivial formatting. | Silent Pass (No PR noise) |

#### 3.3 Plain-English Risk Explainer
A deterministic rule-based generator that crafts an executive sentence summarizing the risk:
> *"⚠️ **CRITICAL RISK:** PR alters the `WHERE` filter on `stg_orders.sql`, changing `status != 'cancelled'` to `status = 'active'`. This cascades across **14 downstream models** and **2 Looker Executive Dashboards** (`board_arr_summary`, `monthly_churn_v2`), silently omitting un-cancelled edge cases."*

---

### Feature 4: Dual-Surface Reporting Layer (CLI & GitHub PR Bot)

#### 4.1 Surface A: Terminal / Local CLI (`rich`)
* Invoked locally by developers prior to pushing: `parallax check`.
* Rendered with Python `rich`:
  * **Header:** Dialect, branches compared, execution duration (e.g., `0.42s`).
  * **Summary Card:** Overall Risk Grade with colored badges (`[CRITICAL]`, `[HIGH]`, `[PASS]`).
  * **Visual Tree Graph:** ASCII/Unicode tree showing `Modified Model` $\to$ `Downstream Models` $\to$ `Exposures`.
  * **AST Diff Table:** Tabular breakdown of changed filters and modified column expressions with line numbers.

#### 4.2 Surface B: GitHub PR Comment Bot
* Automatically posts or updates a single pinned PR comment (never spams multiple comments on repeated pushes).
* **Comment Structure:**
  1. **Badge Header:** `![Parallax CI: Critical Risk](https://img.shields.io/badge/Parallax-CRITICAL_RISK-red)`
  2. **Executive Summary Callout:** 1-2 sentence risk explanation.
  3. **Blast Radius Metrics:**
     * `Impacted Models: 14`
     * `Impacted Exposures: 3 (Looker: 2, Reverse ETL: 1)`
     * `Downstream Depth: 4 layers`
  4. **Collapsible Details `<details>`:**
     * Line-by-line AST predicate diffs.
     * Full list of affected downstream models and files.
     * Specific exposures at risk.
  5. **Remediation Advice:** Exact steps for the developer to verify before merging.

#### 4.3 Surface C: CI Step Summary & Artifacts
* Writes output directly to `$GITHUB_STEP_SUMMARY` for a native GitHub Actions summary tab experience.
* Generates an optional standalone static HTML report: `parallax-report.html` (viewable offline or stored as a GitHub CI artifact).

---

### Feature 5: CLI Interface & Configuration

#### 5.1 CLI Commands & Options

```bash
# Core validation command against git diff
parallax check \
  --manifest target/manifest.json \
  --base origin/main \
  --head HEAD \
  --dialect snowflake \
  --fail-on HIGH \
  --format markdown \
  --output pr_comment.md

# Instant zero-config demo with built-in horror story
parallax demo

# Generate static HTML blast-radius report
parallax report --manifest target/manifest.json --out report.html
```

#### 5.2 Configuration File: `.parallax.yml` (Optional)

```yaml
version: 1
dialect: snowflake
manifest_path: target/manifest.json
fail_on: CRITICAL  # Options: LOW, MEDIUM, HIGH, CRITICAL

tier_tags:
  - tier_1
  - finance
  - executive

ignore:
  - "models/sandbox/**"
  - "models/dev_*"

github:
  update_existing_comment: true
```

---

## 6. Packaged Demo Experience (The "Viral Hook")

### 6.1 The Horror Story Scenario: `$3.8M Silent Revenue Bug`
To make the blog post and GitHub demo immediately viral, Parallax ships with an internal synthetic dbt project (`jaffle_shop_enterprise`):
* **The Setup:** An enterprise dbt project with 35 models and 3 Looker exposures (`Executive ARR Dashboard`, `Board Financials`, `Sales Commission Sync`).
* **The Commit:** An innocent-looking PR titled *"Clean up order status filter"*:
  ```diff
  -- models/staging/stg_orders.sql
  - WHERE status NOT IN ('returned', 'cancelled')
  + WHERE status = 'delivered'
  ```
* **The Silent Catastrophe:** The original SQL included orders in `'processing'` and `'in_transit'` (which under corporate accounting rules count toward booked pipeline and ARR). The new filter drops them completely—silently wiping $3.8M in pipeline from downstream board dashboards.
* **The Parallax Demo Command:** Running `parallax demo` immediately loads this scenario in-memory, runs the AST & DAG diff, and prints the stunning CLI tree and PR markdown in under 1 second.

---

## 7. Technical Architecture & Component Design

```
parallax/
├── cli/
│   ├── main.py              # Click/Typer CLI entrypoints (check, demo, report)
│   └── formatters/          # Terminal rich formatting & Markdown rendering
├── core/
│   ├── git.py               # Git diff resolution & file change detection
│   ├── ast_diff.py          # SQLGlot AST parsing, traversal & semantic diff
│   ├── dbt_manifest.py      # dbt manifest.json parser & NetworkX graph builder
│   ├── lineage.py           # Blast radius & exposure propagation engine
│   └── risk_engine.py       # Severity classification & rule synthesis
├── demo/
│   ├── scenario.py          # Self-contained "$3.8M bug" mock manifest & diff
│   └── sample_project/      # Minimal synthetic dbt project
└── github/
    └── action.py            # GitHub API PR comment updater & step summary writer
```

### 7.1 Core Dependencies (Ultra-Lightweight)
* `sqlglot` ($\ge 23.0$): Fast, zero-dependency SQL parser, transpiler, and AST engine.
* `networkx` ($\ge 3.0$): Pure Python DAG engine for dbt dependency resolution.
* `rich` ($\ge 13.0$): Premium terminal UI, tables, and colored trees.
* `click` or `typer`: Ergonomic CLI commands.
* `pydantic` ($\ge 2.0$): Data modeling for AST diff results, graph nodes, and config validation.

---

## 8. GitHub Action Integration Specification

### 8.1 Marketplace Action: `action.yml`

```yaml
name: "dbt CI Blast Radius Check"
on:
  pull_request:
    paths:
      - "models/**"
      - "seeds/**"

jobs:
  parallax:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Full history for git diff

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Compile dbt Manifest
        run: dbt compile # Generates target/manifest.json

      - name: Run Parallax Blast Radius CI
        uses: parallax-ci/parallax@v1
        with:
          manifest: target/manifest.json
          fail_on: CRITICAL
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

---

## 9. Launch, Blog Post & Virality Strategy

### 9.1 The Flagship Blog Post
* **Headline:** *"The $3.8M SQL Change That Passed All Unit Tests: Why Linters Can't Catch Semantic Drift, and the Open-Source Action That Maps Your Blast Radius in CI"*
* **Target Publication:** Substack / Hacker News / Data Engineering Reddit / Towards Data Science.
* **Narrative Arc:**
  1. **The Monday Morning Confession:** The true horror story of a 1-line `WHERE` filter change that passed CI, passed dbt tests, was approved, and resulted in 3 months of wrong metrics presented to the board.
  2. **The Structural Blind Spot:** Deep dive into why linters (syntax) and dbt unit tests (schema constraints) fundamentally cannot detect semantic drift.
  3. **The AST Solution:** How SQLGlot parses SQL into trees, extracts logical clauses, and contrasts them with dbt's dependency graph.
  4. **Zero-Config Philosophy:** Why running statically in GitHub Actions without database access is the only scalable CI approach.
  5. **Try It in 5 Seconds:** The `pip install parallax-ci && parallax demo` callout.

---

## 10. Implementation Schedule (7-Day Sprint Plan)

* **Day 1:** Git diff extraction + SQLGlot AST semantic diff parser (`WHERE`, `HAVING`, `JOIN`, projections).
* **Day 2:** dbt `manifest.json` ingestion + NetworkX DAG construction + downstream exposure tracing.
* **Day 3:** Column-level blast radius propagation + Risk Scoring engine.
* **Day 4:** `rich` terminal CLI interface + Markdown PR comment generator.
* **Day 5:** Built-in `parallax demo` command + bundled synthetic horror story fixtures.
* **Day 6:** Composite GitHub Action (`action.yml`) + static HTML report generator.
* **Day 7:** Documentation, README with `vhs` GIF/SVG demo, flagship blog post draft, and release tagging (`v1.0.0`).
