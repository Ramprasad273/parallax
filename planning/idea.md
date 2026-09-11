Parallax — Zero-Config Blast Radius & Semantic Drift CI

> **One-Line Pitch:** A GitHub Action that catches silent data corruption and maps downstream dashboard breakage before SQL/dbt PRs are merged.

```
                    ┌──────────────────────────────┐
                    │      PR Modifies SQL/dbt     │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   Deterministic AST Engine                   Lineage Graph Engine
   (SQLGlot Diff Analysis)                   (dbt manifest.json)
              │                                         │
              ├─────────────────────────────────────────┤
              ▼                                         ▼
   Semantic Filter Drift:                    Downstream Blast Radius:
   "WHERE status != 'cancelled'"             "Alters 14 downstream models &
   → "status = 'active'"                     3 Looker Executive Dashboards.
   (Drops 12% edge cases)                    Column 'net_arr' removed on L42"
              │                                         │
              └────────────────────┬────────────────────┘
                                   ▼
                    Interactive GitHub PR Comment
```

### The Acute Pain Point
Linters (SQLFluff) only verify syntax and formatting. They cannot detect when a developer changes a `WHERE` filter or alters a column calculation that **passes all unit tests but silently corrupts downstream executive reporting**. By the time the CEO notices the revenue numbers are wrong on Monday morning, the bug has polluted 3 months of warehouse tables.

### Architecture & Technical Feasibility
* **Deterministic Core:**
  * Uses `sqlglot` to parse the Git diff between branches into ASTs.
  * Ingests `target/manifest.json` from dbt to construct a directed acyclic graph (DAG) via `networkx`.
  * Traces column-level lineage from the modified model down to every downstream table and BI exposure.
  * Compares logical filters: detects additions/deletions of predicates (`WHERE`, `HAVING`, `JOIN ON`) and flags semantic divergence.
* **AI Layer:** Analyzes the semantic intent of the PR description versus the actual AST changes and drafts an executive impact summary.
* **Build Time:** 7–10 days. Zero warehouse connection required in v1. Runs entirely in GitHub Actions.

### The Viral Blog & Hacker News Playbook
* **Headline:** *"The $3.8M SQL change that passed all unit tests: How a 1-line WHERE clause silently corrupted enterprise revenue reporting (and the 50-line CI script that stops it)"*
* **The Hook:** Walk through an actual anonymized horror story where `status = 'delivered'` was changed to `status = 'completed'`, breaking billing pipelines. Show the terminal output and the PR bot catching it in 15 seconds.

### The Hiring Signal & Commercial Path
* **Hiring Signal:** Proves mastery over compiler ASTs, static code analysis, and enterprise data lifecycle management.
* **Open Source Wedge:** Free GitHub Action that checks modified SQL against `manifest.json` and outputs terminal/PR comments for up to 50 models.
* **Commercial SaaS ($15k–$40k/yr):** Multi-repo dbt orchestration, historical table data diffs on ephemeral staging warehouses, Looker/Tableau API integrations to flag specific broken dashboard tiles, and PR merge blocking policies.
* **Exit Potential ($60M–$120M):** Acquired by **dbt Labs** (their ultimate missing CI/CD governance layer), **GitHub/Microsoft**, **GitLab**, or **Atlan**.

---