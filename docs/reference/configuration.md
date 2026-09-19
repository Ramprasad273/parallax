# Configuration Reference

Parallax works with zero configuration by default. You can customize runtime behaviors and governance rules by placing a `.parallax.yml` file in your repository root.

---

## Example `.parallax.yml`

```yaml
version: 1

# SQL dialect used for AST parsing (snowflake, bigquery, postgres, duckdb, databricks)
dialect: snowflake

# Path to the compiled dbt manifest artifact
manifest_path: target/manifest.json

# Default Git comparison references
base_ref: origin/main
head_ref: HEAD

# Minimum risk severity required to fail CI (CRITICAL, HIGH, MEDIUM, LOW, NEVER)
fail_on: CRITICAL

# Model and exposure tags treated as high-priority tier-1 assets
tier_tags:
  - tier_1
  - finance
  - executive
  - board
  - p0

# Glob patterns for SQL files to ignore from blast radius analysis
ignore_patterns:
  - "models/sandbox/**"
  - "models/dev_*"

# Whether GitHub PR comments should update in-place rather than posting duplicates
update_existing_comment: true
```

---

## Configuration Properties

### `version`
- **Type:** `integer`
- **Default:** `1`
- The configuration schema version.

### `dialect`
- **Type:** `string`
- **Default:** `snowflake`
- Options: `snowflake`, `bigquery`, `postgres`, `duckdb`, `databricks`.
- Specifies the SQL parser dialect for SQLGlot.

### `manifest_path`
- **Type:** `string` (path)
- **Default:** `target/manifest.json`
- The relative or absolute path to the dbt compilation manifest.

### `base_ref`
- **Type:** `string`
- **Default:** `origin/main`
- The base branch or git reference used to compute incoming SQL modifications.

### `head_ref`
- **Type:** `string`
- **Default:** `HEAD`
- The target branch or working tree reference.

### `fail_on`
- **Type:** `string`
- **Default:** `CRITICAL`
- Options: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NEVER`.
- If the computed blast radius risk is equal to or higher than this threshold, the command exits with code `1`.

### `tier_tags`
- **Type:** `list[string]`
- **Default:** `["tier_1", "finance", "executive", "board", "p0"]`
- Tags from dbt exposures and models that trigger elevated risk severity when impacted.

### `ignore_patterns`
- **Type:** `list[string]`
- **Default:** `["models/sandbox/**", "models/dev_*"]`
- Glob expressions for files or directories that should be skipped during analysis.

### `update_existing_comment`
- **Type:** `boolean`
- **Default:** `true`
- When set to true, Parallax reuses and updates the existing PR comment thread.
