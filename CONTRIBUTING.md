# Contributing to Parallax

Thank you for your interest in contributing to **Parallax**!

Parallax is an open-source, zero-config blast radius and semantic drift CI tool for SQL and dbt. Our mission is to eliminate silent, expensive business logic regressions from data pipelines through compiler-grade static analysis without requiring warehouse credentials or heavy runtime compute.

---

## Core Architectural Principles

When contributing code to Parallax, keep these four principles in mind:

1. **Zero Warehouse Credentials**: Parallax never connects to live databases, warehouses, or orchestrators. Everything operates on Git diffs, SQL ASTs, and dbt metadata artifacts.
2. **Sub-Second Performance**: Static analysis and lineage traversals must complete in under 500ms even for projects with 2,000+ models. Avoid heavy I/O or quadratic algorithms.
3. **Zero False-Positive Noise**: If a PR contains cosmetic formatting or comment changes, Parallax must run silently without spamming PR comments.
4. **Deterministic Synthesis**: Plain-English impact summaries are generated algorithmically. Do not introduce dependencies on external LLMs or non-deterministic APIs.

---

## Development Setup

Parallax requires **Python 3.10+**.

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/parallax-ci/parallax.git
cd parallax

# Using standard venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Or using uv (recommended for ultra-fast setup)
uv venv
source .venv/bin/activate
```

### 2. Install Dependencies in Editable Mode

```bash
pip install -e ".[dev]"
```

Verify your setup by running the demo command:
```bash
parallax demo
```

---

## Testing & Code Quality

We enforce strict quality standards before any PR is merged. Every change must pass:

### 1. Run Unit & Integration Tests

```bash
pytest -v --cov=parallax --cov-report=term-missing
```

- All tests must pass.
- Maintain **>= 90% code coverage**.

### 2. Run Static Type Checking

We use `mypy` with strict configuration:

```bash
mypy parallax tests
```

- Zero type errors allowed (`warn_return_any = true`, `disallow_untyped_defs = true`).

### 3. Run Linter & Formatter

We use `ruff` for fast linting and formatting:

```bash
# Check code style & linting rules
ruff check parallax tests

# Verify formatting
ruff format --check parallax tests
```

To automatically fix formatting or autofixable lint errors:
```bash
ruff check --fix parallax tests
ruff format parallax tests
```

---

## How to Add a New SQL Dialect

Parallax uses [**SQLGlot**](https://github.com/tobymao/sqlglot) for multi-dialect SQL parsing.

Currently supported dialects include:
- `snowflake` (default)
- `bigquery`
- `postgres`
- `duckdb`
- `databricks`
- `ansi`

### To add or improve support for a dialect:
1. Ensure the dialect name corresponds to a valid SQLGlot dialect string.
2. Update the dialect fallback chain in [`parallax/core/ast_diff.py`](file:///f:/projects/Parallax/parallax/core/ast_diff.py) if dialect-specific normalization is needed.
3. Add a test in [`tests/test_ast_diff.py`](file:///f:/projects/Parallax/tests/test_ast_diff.py) with sample SQL in the new dialect verifying AST parsing and diff detection.
4. Update `action.yml` and `README.md` to list the new dialect.

---

## How to Add New Semantic Diff Rules

AST diffing logic lives in [`parallax/core/ast_diff.py`](file:///f:/projects/Parallax/parallax/core/ast_diff.py):
1. **WHERE / HAVING Predicates**: Parsed via `_diff_predicates()`. Boolean conjuncts (`AND`) are flattened into atomic conditions.
2. **SELECT Projections**: Parsed via `_diff_projections()`. Identifies dropped columns and expression modifications.
3. **JOIN Conditions**: Parsed via `_diff_joins()`. Flags altered join types (e.g. `INNER` -> `LEFT`).
4. **GROUP BY Dimensions**: Parsed via `_diff_group_by()`. Flags aggregation cardinality changes.

When adding a new diff rule:
- Ensure the diff categorization uses [`DiffType`](file:///f:/projects/Parallax/parallax/core/models.py) or an approved extension.
- Provide both `base_code` and `head_code` examples.
- Add comprehensive test cases in `tests/test_ast_diff.py` and ensure the risk scoring in `tests/test_risk_engine.py` handles the new classification.

---

## Pull Request Guidelines

1. **Branch Naming**:
   - `feat/feature-name`
   - `fix/bug-description`
   - `docs/documentation-update`
2. **Commit Messages**:
   - Use conventional commit style: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
3. **PR Description**:
   - Fill out our PR template completely.
   - Describe the business rationale and attach a minimal SQL test case.
4. **CI Verification**:
   - All GitHub Actions checks (`ci.yml`) must pass before review.

---

## Community & Questions

- Report bugs or request features via [GitHub Issues](https://github.com/parallax-ci/parallax/issues).
- For security vulnerabilities, please email `security@parallax-ci.dev` directly rather than opening a public issue.
