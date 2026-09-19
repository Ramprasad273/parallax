# Semantic Drift & AST Diffing

**Semantic Drift** occurs when a query's underlying business logic, row volume, or column contracts change silently without causing syntax errors or schema-level test failures.

---

## The Limitations of Text & Linter Checks

Traditional Git diffs and SQL linters operate on strings:
- Whitespace reformatting causes noisy diffs.
- Aliases and clause reordering confuse regex-based tools.
- Syntax validators only confirm the SQL is valid—not whether it produces the same business outcome.

Parallax compiles modified models before and after your PR branch into Abstract Syntax Trees (ASTs) using **SQLGlot**. By normalizing expressions, Parallax eliminates cosmetic formatting differences and isolates semantic logic changes.

---

## Semantic Diff Categories

Parallax detects four major categories of semantic drift:

### 1. Predicate Tightening (`TIGHTENED`)
Occurs when a `WHERE` or `HAVING` clause becomes more restrictive.

```sql
-- Before
WHERE status NOT IN ('returned', 'cancelled')

-- After
WHERE status = 'delivered'
```

- **Impact:** Rows previously included (e.g. `'in_transit'`, `'processing'`) are silently filtered out.
- **Risk:** High or Critical if downstream models rely on complete transaction counts.

### 2. Predicate Loosening (`LOOSENED`)
Occurs when a filter condition is dropped or made more permissive.

```sql
-- Before
WHERE region = 'US' AND is_active = TRUE

-- After
WHERE region = 'US'
```

- **Impact:** Deactivated records flood into marts and reports, inflating user counts or revenue numbers.

### 3. Column Mutations & Drops (`DROPPED`, `RENAMED`)
Detects when columns in a `SELECT` statement are removed, renamed without aliasing, or have their projection altered.

```sql
-- Before
SELECT order_id, customer_id, amount FROM orders

-- After
SELECT id AS order_id, customer_id FROM orders  -- 'amount' dropped
```

- **Impact:** Any downstream model selecting `amount` from this upstream reference will fail compilation or break during dbt run.

### 4. Join Mutations
Detects changes to join types (e.g. `INNER JOIN` $\to$ `LEFT JOIN`, or `LEFT JOIN` $\to$ `FULL OUTER JOIN`).

- **Impact:** Can introduce `NULL` values or cause fan-out / row multiplication in downstream metrics.

---

## Dialect Support

Parallax supports major cloud data warehouse dialects out of the box via SQLGlot:

- **Snowflake** (default)
- **BigQuery**
- **PostgreSQL**
- **DuckDB**
- **Databricks**

Specify your dialect via `--dialect` or in `.parallax.yml`:

```yaml
dialect: bigquery
```
