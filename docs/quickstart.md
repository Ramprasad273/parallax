# Quickstart

Get started with Parallax in under 60 seconds.

---

## Installation

### Option 1: Using `uv` (Recommended)
```bash
uv pip install parallax-ci

# Or run directly without installing:
uvx parallax-ci demo
```

### Option 2: Using standard `pip`
```bash
pip install parallax-ci
```

### Option 3: From Source (Developers)
```bash
git clone https://github.com/Ramprasad273/parallax.git
cd parallax
uv pip install -e ".[dev]"
```

---

## 1. Run the Built-In Simulation

You can experience the complete Parallax analysis without configuring any repository or manifest:

```bash
# If your virtual environment is active, or installed globally:
parallax demo

# Or with uv:
uv run parallax demo

# Or without installing anything using uvx:
uvx parallax-ci demo
```

This simulates an upstream SQL filter tightening on `stg_orders.sql` and visualizes:
- **Semantic AST Diff:** Detection of negative filter exclusion to strict status filter.
- **Downstream Lineage:** 18 downstream models traversed across Intermediate, Marts, and Reporting layers.
- **Impacted BI Exposures:** Identification of affected executive dashboards (`Board Financials Summary`, `Executive ARR Dashboard`, `Sales Commission Sync`).
- **Remediation Advice:** Step-by-step guidance for analytics engineers.
- **CI Gate Status:** Unambiguous `BLOCK` or `PASS` indicator.

See the [Sample Report & Interpretation Guide](sample-report.md) for a detailed breakdown of how to read this output.

---

## 2. Run on Your dbt Project

### Step 1: Compile your dbt project
Ensure your `target/manifest.json` exists by compiling your dbt models:

```bash
dbt compile
```

### Step 2: Compare against your base branch
Run Parallax against your base branch (e.g. `main` or `origin/main`):

```bash
parallax check --manifest target/manifest.json --base origin/main
```

Or with `uv`:
```bash
uv run parallax check --manifest target/manifest.json --base origin/main
```

---

## Common CLI Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--manifest` | `target/manifest.json` | Path to dbt compile artifact |
| `--base` | `origin/main` | Base Git branch or commit to diff against |
| `--dialect` | `snowflake` | SQL dialect (`snowflake`, `bigquery`, `postgres`, `duckdb`, `databricks`) |
| `--fail-on` | `CRITICAL` | Minimum risk severity to exit with code `1` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `NEVER`) |
| `--format` | `terminal` | Output format (`terminal`, `markdown`, `json`) |
| `--output` | `stdout` | File path to write the formatted report |

---

## Generating Offline HTML Reports

### Preview with Built-In Simulation Data
To generate a complete, populated HTML report with simulated models, executive exposures, and AST diffs:

```bash
uv run parallax report --demo --out blast_radius_report.html
```
Or:
```bash
uv run parallax demo --format html --out blast_radius_report.html
```

### Run on Your dbt Project
When running inside your actual dbt repository with modified `.sql` files and a compiled `target/manifest.json`:

```bash
uv run parallax report --manifest target/manifest.json --base origin/main --out blast_radius_report.html
```

Open `blast_radius_report.html` in any browser to inspect the visual dashboard.

---

## Troubleshooting: Command Not Found

If PowerShell or your terminal reports:
```text
parallax : The term 'parallax' is not recognized as the name of a cmdlet, function...
```

This happens when your shell does not have the virtual environment activated in the current session. You can resolve this in three ways:

1. **Use `uv run` (Easiest):**
   ```powershell
   uv run parallax demo
   ```
2. **Activate your virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     parallax demo
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     parallax demo
     ```
3. **Use the full executable path:**
   - **Windows:**
     ```powershell
     & ".\.venv\Scripts\parallax.exe" demo
     ```
   - **macOS / Linux:**
     ```bash
     ./.venv/bin/parallax demo
     ```
