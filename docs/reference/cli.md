# CLI Reference

Parallax provides three primary commands: `check`, `report`, and `demo`.

> **Execution Note:** When working inside a virtual environment or using `uv`, you can prefix any command with `uv run` (e.g. `uv run parallax check ...`) or ensure your virtual environment is active in your current shell.

---

## `parallax check`

Inspects modified SQL models between Git branches or your working tree, performs AST semantic diffing, walks the dbt lineage graph, and produces formatted reports.

```bash
parallax check [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--manifest` | `-m` | Path | `target/manifest.json` | Path to compiled dbt manifest. |
| `--base` | `-b` | String | `origin/main` | Git base reference or branch name. |
| `--head` | `-h` | String | `HEAD` | Git head reference or commit. |
| `--dialect` | `-d` | Choice | `snowflake` | SQL dialect: `snowflake`, `bigquery`, `postgres`, `duckdb`, `databricks`. |
| `--fail-on` | | Choice | `CRITICAL` | Minimum severity level to exit with code `1`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NEVER`. |
| `--format` | `-f` | Choice | `terminal` | Output format: `terminal`, `markdown`, `json`. |
| `--output` | `-o` | Path | None | File path to write the formatted report (stdout if omitted). |
| `--config` | `-c` | Path | None | Path to custom `.parallax.yml` configuration file. |
| `--verbose` | `-v` | Flag | `false` | Enable verbose debug logging. |

### Exit Codes

- `0`: Scan passed or risk severity is below `--fail-on` threshold.
- `1`: Scan detected risk severity meeting or exceeding `--fail-on` threshold (blocks CI).

---

## `parallax report`

Generates an offline, interactive, single-file HTML audit report.

```bash
parallax report [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--manifest` | `-m` | Path | `target/manifest.json` | Path to compiled dbt manifest. |
| `--base` | `-b` | String | `origin/main` | Git base reference or branch name. |
| `--head` | `-h` | String | `HEAD` | Git head reference or commit. |
| `--dialect` | `-d` | Choice | `snowflake` | SQL dialect. |
| `--out` | `-o` | Path | `parallax-report.html` | Output HTML report file path. |
| `--demo` | | Flag | `false` | Generate report from built-in simulation scenario. |

---

## `parallax demo`

Runs an instant, in-memory simulation of silent filter tightening with full lineage traversal and executive exposure impact. Requires zero configuration or repository files.

```bash
parallax demo [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--format` | `-f` | Choice | `terminal` | Output format: `terminal`, `markdown`, `json`, `html`. |
| `--output`, `--out` | `-o` | Path | None | File path to write formatted report (stdout if omitted). |
