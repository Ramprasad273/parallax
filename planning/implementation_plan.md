# Technical Implementation Plan: Parallax (Production-Grade Open Source)

**Location:** `F:\projects\Parallax`  
**Tagline:** Zero-Config Blast Radius & Semantic Drift CI for SQL and dbt  
**Strategy:** Incremental Build with Educational dbt Walkthroughs & Strict Test Gates  
**Constraints:** 100% Offline, Zero Cloud/Paid APIs, Zero Warehouse Credentials, Execution < 10 seconds.

---

## 1. Context & Repository Review

### 1.1 Directory Status
* The project has been moved to its own dedicated root: `F:\projects\Parallax`.
* **Folder Contents:** Currently contains `planning/` with:
  * `PRD.md`: Full product requirements document.
  * `idea.md`: Product vision and acute pain point.
  * `implementation_plan.md`: Initial plan.
* **Release Implication:** Having `F:\projects\Parallax` as its own folder is the **ideal structure**:
  * It can be initialized as an independent Git repository (`git init`).
  * It can be pushed directly to GitHub (`github.com/<org>/parallax`).
  * GitHub Actions Marketplace (`uses: parallax-ci/action@v1`) can index the repository root directly without monorepo workarounds.
  * PyPI packaging (`uv build` -> `parallax-ci`) is completely self-contained.

---

## 2. dbt Primer (Why Parallax Exists & What It Does)

Because you are new to dbt, here is the exact mental model of how dbt works and why Parallax is so critical:

```
Raw Warehouse Tables (Postgres / Snowflake / BigQuery)
                     │
                     ▼
  [ Staging Layer ]  stg_orders.sql        <-- Developer modifies WHERE filter here
                     │
                     ▼
  [ Marts Layer ]    fct_orders.sql        <-- Downstream calculation silently altered
                     │
                     ▼
  [ Reporting ]      dim_customers.sql     <-- Historical metrics skewed
                     │
                     ▼
  [ Exposures ]      Looker / Tableau / Metabase Executive Dashboards ($3.8M silent loss)
```

1. **What is dbt?**  
   In modern data engineering, teams do not write messy pipelines in procedural code. Instead, they write modular SQL `SELECT` queries called **models**.
2. **How does dbt connect models?**  
   Instead of hardcoding table names, developers write:
   ```sql
   SELECT * FROM {{ ref('stg_orders') }} WHERE is_active = true
   ```
   dbt inspects all `{{ ref(...) }}` calls and compiles them into a **DAG (Directed Acyclic Graph)**.
3. **What is `manifest.json`?**  
   When dbt compiles a project, it generates a single JSON file called `target/manifest.json`. This file is the complete blueprint of the entire data warehouse:
   * Every SQL model and seed table.
   * Every dependency edge (which model feeds into which model).
   * Every column declared in YAML schemas.
   * Every **exposure** (which Looker dashboards, Tableau reports, or reverse-ETL syncs consume which models).
4. **The Critical Blind Spot Parallax Solves:**  
   * If a developer changes `WHERE status NOT IN ('returned', 'cancelled')` to `WHERE status = 'delivered'`, standard CI tools fail silently:
     * **SQLFluff (Linter)** passes because the syntax and formatting are valid.
     * **dbt Tests** (`unique`, `not_null`) pass because the surviving delivered orders are still unique and non-null.
     * **Result:** Orders that are `'in_transit'` or `'processing'` are dropped silently. 12% of company revenue vanishes from downstream executive reports.
   * **Parallax** catches this statically in CI in < 1 second:
     1. It reads the Git diff to see which SQL files changed.
     2. It parses the SQL Abstract Syntax Tree (AST) using `sqlglot` to catch that the `WHERE` filter was tightened.
     3. It reads `manifest.json` and walks the DAG using `networkx` to trace all downstream models and Looker dashboards.
     4. It posts a rich terminal report and GitHub PR comment flagging the exact blast radius.

---

## 3. Engineering Standards & Quality Checklist

Every phase of Parallax will adhere to:
1. **Strict Type Annotations & Static Analysis:**
   * Python 3.10+ typing with Pydantic v2 data models.
   * Linting and formatting with `ruff`.
   * Type checking with `mypy`.
2. **Modular Logging:**
   * Standard library `logging` with structured formatting (log levels: DEBUG, INFO, WARNING, ERROR).
   * Configurable log level via `--verbose` / `-v` flag.
3. **Comprehensive Testing Strategy:**
   * **Unit Tests:** Fast, isolated tests for pure functions (AST normalization, filter comparison, graph building).
   * **Integration Tests:** End-to-end runs with synthetic dbt projects and real git diffs.
   * **Static Code Analysis:** `ruff check`, `ruff format --check`, `mypy`.
4. **Zero Fluff & High Security:**
   * 0 external paid APIs, 0 cloud dependencies, 0 warehouse connections.
   * 0 dynamic code execution (`no eval`, `no exec`, `shell=False` everywhere).

---

## 4. Incremental Build Phases & Review Checkpoints

```
┌────────────────────────────────────────────────────────────────────────┐
│                          PARALLAX BUILD PHASES                         │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 1: Environment Setup, Tooling & Pydantic Data Contracts          │
│ Phase 2: Safe Git Diff Resolver (Base vs Head + Working Tree)          │
│ Phase 3: Jinja Sanitizer & SQLGlot AST Semantic Diff Engine            │
│ Phase 4: dbt Manifest Ingestion & DAG Blast Radius Lineage Engine     │
│ Phase 5: Risk Scoring Matrix & Plain-English Explainer Engine          │
│ Phase 6: Dual-Surface Formatters (Rich Terminal, PR Markdown, HTML)    │
│ Phase 7: CLI Commands & Configuration (.parallax.yml, check, report)   │
│ Phase 8: Packaged Demo Experience (The $3.8M Silent Revenue Bug)       │
│ Phase 9: GitHub Action Integration (action.yml & PR Comment Bot)      │
│ Phase 10: Final Quality Gates, Documentation & Git Release Setup       │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Environment Setup, Tooling & Pydantic Data Contracts
* **Concept Taught:** How Python packages are structured (`pyproject.toml`) and how Pydantic v2 creates immutable data contracts between the compiler layer and the graph layer.
* **Files to Create:**
  * `pyproject.toml` (package definition, dependencies, entry points, tool configurations).
  * `.gitignore` (Python, virtualenv, pytest, dbt artifacts).
  * `parallax/__init__.py` (package version metadata).
  * `parallax/core/models.py` (Pydantic models for AST diffs, lineage nodes, risk scores).
  * `parallax/core/config.py` (configuration schema for `.parallax.yml`).
  * `tests/test_models.py` (unit tests for schemas).
* **Testing & Verification:**
  * Unit test: `pytest tests/test_models.py`
  * Static check: `ruff check parallax tests`
* **Review Checkpoint 1:** You review the code, learn how models interact, and approve.

---

### Phase 2: Safe Git Diff Resolver (`core/git.py`)
* **Concept Taught:** How CI tools determine what changed in a PR without running dangerous shell strings.
* **Files to Create:**
  * `parallax/core/git.py`
  * `tests/test_git.py`
* **Features Implemented:**
  * `get_changed_sql_files(base_ref, head_ref)`: Identifies modified, added, and deleted SQL files.
  * `get_file_content_at_ref(path, ref)`: Retrieves historical base SQL using `git show <base>:<path>` without checking out branches.
  * Local working tree support for `parallax check` prior to running `git commit`.
* **Testing & Verification:**
  * Unit test: `pytest tests/test_git.py` using synthetic temporary git repositories.
  * Static check: `ruff check parallax/core/git.py`
* **Review Checkpoint 2:** You review how git diff extraction works.

---

### Phase 3: Jinja Sanitizer & SQLGlot AST Semantic Diff Engine (`core/jinja.py` & `core/ast_diff.py`)
* **Concept Taught:** Abstract Syntax Trees (ASTs) vs. Linters. Why `status != 'cancelled'` is logically different from `status = 'delivered'`, and how `sqlglot` breaks SQL into a traversable tree.
* **Files to Create:**
  * `parallax/core/jinja.py` (safe regex-based mock parser for `{{ ref(...) }}`, `{{ source(...) }}`, `{{ config(...) }}`).
  * `parallax/core/ast_diff.py` (AST traversal, boolean expression flattening, projection diffing, join analysis).
  * `tests/test_ast_diff.py` (25+ test cases).
* **Features Implemented:**
  * Jinja preprocessor that allows parsing uncompiled dbt models.
  * Predicate diffing (`WHERE`, `HAVING`, `JOIN ON`): detects filter tightening, loosening, dropped conditions, and inverted operators.
  * Column diffing: detects dropped columns, renamed aliases, and expression mutations.
  * Join diffing: detects changes in join types (e.g. `INNER` $\to$ `LEFT`).
* **Testing & Verification:**
  * Unit test: `pytest tests/test_ast_diff.py` (validating the $3.8M bug scenario and edge cases).
* **Review Checkpoint 3:** You review how SQL is turned into trees and diffed.

---

### Phase 4: dbt Manifest Ingestion & DAG Blast Radius Lineage Engine (`core/dbt_manifest.py` & `core/lineage.py`)
* **Concept Taught:** How dbt organizes dependencies in `manifest.json`, how to construct a directed graph in `networkx`, and how to trace downstream blast radius.
* **Files to Create:**
  * `parallax/core/dbt_manifest.py` (JSON parser extracting models, seeds, exposures, tags).
  * `parallax/core/lineage.py` (NetworkX DiGraph builder, descendant traversal, column reference tracking).
  * `tests/test_manifest.py` & `tests/test_lineage.py`.
* **Features Implemented:**
  * Fast manifest ingestion supporting dbt 1.5 - 1.9+.
  * Downstream transitive tracing: categorizing affected nodes into Staging, Intermediate, Marts, and Exposures (Looker/Tableau).
  * Column-level breaking change detection: flags downstream models that explicitly reference a deleted or renamed column.
* **Testing & Verification:**
  * Unit test: `pytest tests/test_manifest.py tests/test_lineage.py`.
* **Review Checkpoint 4:** You review the graph traversal and exposure mapping.

---

### Phase 5: Risk Scoring Matrix & Plain-English Explainer Engine (`core/risk_engine.py`)
* **Concept Taught:** Rule-based expert systems. How to generate plain-English executive explanations deterministically without relying on unpredictable or expensive LLMs.
* **Files to Create:**
  * `parallax/core/risk_engine.py`.
  * `tests/test_risk_engine.py`.
* **Features Implemented:**
  * Algorithmic risk matrix (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
  * Plain-English sentence synthesizer producing actionable executive summaries.
* **Testing & Verification:**
  * Unit test: `pytest tests/test_risk_engine.py`.
* **Review Checkpoint 5:** You review the risk scoring logic.

---

### Phase 6: Dual-Surface Formatters (Rich Terminal, PR Markdown, HTML)
* **Concept Taught:** CLI user experience. How `rich` builds terminal trees and ANSI tables, and how GitHub markdown `<details>` tags create clean PR comments.
* **Files to Create:**
  * `parallax/cli/formatters/terminal.py`.
  * `parallax/cli/formatters/markdown.py`.
  * `parallax/cli/formatters/html.py`.
  * `tests/test_formatters.py`.
* **Features Implemented:**
  * Rich terminal UI: Colored tree graphs, diff tables, execution duration metrics.
  * GitHub PR markdown: Status shield badge, executive callout, metrics grid, collapsible details.
  * Standalone static HTML report.
* **Testing & Verification:**
  * Unit test: `pytest tests/test_formatters.py`.
* **Review Checkpoint 6:** You review the visual terminal and PR markdown formatting.

---

### Phase 7: CLI Commands & Configuration (`cli/main.py` & `.parallax.yml`)
* **Concept Taught:** Building clean, standard Unix CLI tools using Click, handling flags, exit codes, and config files.
* **Files to Create:**
  * `parallax/cli/main.py`.
  * `tests/test_cli.py`.
* **Features Implemented:**
  * `parallax check`: `--manifest`, `--base`, `--head`, `--dialect`, `--fail-on`, `--format`, `--output`.
  * `parallax report`: HTML generator.
  * Configuration loader for `.parallax.yml`.
  * CI gating (exit code 1 on risk $\ge$ `--fail-on`).
* **Testing & Verification:**
  * Unit & Integration test: `pytest tests/test_cli.py`.
* **Review Checkpoint 7:** You test running `parallax check --help` and review the CLI options.

---

### Phase 8: Packaged Demo Experience (The $3.8M Silent Revenue Bug)
* **Concept Taught:** Developer onboarding and the "Aha!" moment. How shipping a built-in interactive scenario makes an open-source tool go viral.
* **Files to Create:**
  * `parallax/demo/scenario.py`.
  * `parallax/demo/sample_project/manifest.json`.
  * `parallax/demo/sample_project/stg_orders_base.sql`.
  * `parallax/demo/sample_project/stg_orders_head.sql`.
  * `tests/test_demo.py`.
* **Features Implemented:**
  * `parallax demo`: loads an enterprise retail dbt project with 35 models and 3 Looker exposures in-memory, executes in ~0.2s, and displays the complete terminal graph and diff.
* **Testing & Verification:**
  * Execution: Run `parallax demo` and verify output and speed.
* **Review Checkpoint 8:** You run `parallax demo` on your machine and experience the tool firsthand.

---

### Phase 9: GitHub Action Integration (`action.yml` & `github/action.py`)
* **Concept Taught:** GitHub Actions architecture, `$GITHUB_STEP_SUMMARY`, and the GitHub REST API for in-place comment updates.
* **Files to Create:**
  * `action.yml` (Marketplace composite action).
  * `parallax/github/action.py`.
  * `tests/test_github_action.py`.
* **Features Implemented:**
  * Native composite GitHub Action.
  * In-place comment updater (prevents PR comment spam).
  * `$GITHUB_STEP_SUMMARY` integration.
* **Testing & Verification:**
  * Unit test: `pytest tests/test_github_action.py` with mocked GitHub API responses.
* **Review Checkpoint 9:** You review the GitHub Action configuration.

---

### Phase 10: Final Quality Gates, Documentation & Git Release Setup
* **Concept Taught:** Open-source release readiness, documentation polish, and publishing to GitHub and PyPI.
* **Files to Create:**
  * `README.md` (high-polish documentation with diagrams and copy-paste configs).
  * `data-engineering/Parallax/blog_post.md` (flagship blog post draft for Hacker News).
  * Git initialization and clean first commit in `F:\projects\Parallax`.
* **Testing & Verification:**
  * Full test suite: `pytest -v --cov=parallax` (100% pass, target >90% coverage).
  * Static code check: `ruff check parallax tests` and `mypy parallax`.
* **Review Checkpoint 10:** Final review of the complete production-grade repository.

---

## 5. Verification Plan Summary

| Verification Level | Tool / Command | Target Criteria |
| :--- | :--- | :--- |
| **Unit Testing** | `pytest tests/test_*.py -v` | 100% pass, zero network calls, sub-second execution |
| **Integration Testing** | `pytest tests/test_cli.py tests/test_demo.py` | Full CLI and demo flows verified |
| **Static Code Analysis**| `ruff check parallax tests` | 0 lint or formatting errors |
| **Type Checking** | `mypy parallax` | Strict type safety across all core modules |
| **Security Audit** | Static scan of code | Zero `eval`/`exec`, `shell=False`, zero secrets |
| **Performance Gate** | Benchmark test | Full 2,000-model analysis < 1.5s (PRD target < 10s) |
