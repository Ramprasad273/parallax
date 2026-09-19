---
name: Bug Report
about: Create a report to help us improve Parallax
title: "[BUG] "
labels: ["bug"]
assignees: ""
---

## Bug Description
A clear and concise description of what the bug is.

## Environment
- **Parallax Version**: (e.g. `0.1.0` or run `parallax --version`)
- **dbt Version**: (e.g. `1.8.0`)
- **SQL Dialect**: (e.g. `snowflake`, `bigquery`, `postgres`, `duckdb`)
- **OS / CI Environment**: (e.g. `Ubuntu 22.04` / `GitHub Actions` / `macOS 14` / `Windows 11`)
- **Python Version**: (e.g. `3.11.4`)

## Reproducing SQL Snippet

### Base SQL (`main`):
```sql
-- Paste original SQL here
```

### Head SQL (PR branch):
```sql
-- Paste modified SQL here
```

### Manifest / Lineage Context (if applicable):
```yaml
# Relevant model references or downstream exposure definitions
```

## Expected vs. Actual Behavior
- **Expected Behavior**: (e.g. "Expected risk to be categorized as MEDIUM because only a non-breaking filter changed")
- **Actual Behavior**: (e.g. "Scored as CRITICAL with downstream column false positive")

## CLI Output / Error Traceback
```text
# Paste the terminal output or stack trace here
```

## Additional Context
Add any other context about the problem here (e.g. custom macros, unusual Jinja tags).
