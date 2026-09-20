# Security, Compliance & Operating Model

This document outlines the security architecture, compliance posture, and operating boundaries of Parallax.

---

## Security Architecture

### Zero Warehouse Credentials
Parallax operates strictly via static analysis on your local machine or within your CI/CD runner. It:
- **Never requests database credentials:** No username, password, private key, or service account is needed.
- **Never connects to data warehouses:** It makes zero network connections to Snowflake, BigQuery, Postgres, Databricks, or other cloud storage systems.
- **Incurs zero query costs:** No compute warehouses are spun up or billed.

### Data Privacy & Code Confidentiality
- **100% In-Memory Local Execution:** SQL files and AST structures are parsed and analyzed purely within the running process memory.
- **No External Telemetry or Network Calls:** Parallax does not send queries, ASTs, file paths, model names, or analytics data to external servers or third-party APIs.
- **No LLM Dependencies:** Parallax uses deterministic, algorithmic logic synthesis. No source code or proprietary SQL is sent to third-party LLM providers.

---

## Scope & Limitations of Static Analysis

Parallax is designed as an automated safety layer during pull request review. Understanding what it does and does not do is critical for pipeline security and compliance:

### What Parallax Evaluates
- Structural changes in SQL Abstract Syntax Trees (predicates, projections, joins).
- Topological dependency graphs defined in dbt's compiled `manifest.json`.
- Mapping of modified upstream models to declared downstream consumers (intermediate models, marts, and BI exposures).

### What Parallax Does Not Evaluate
- **Runtime Data Contents:** Parallax does not inspect actual table rows or validate runtime data distributions in your warehouse.
- **Dynamic SQL:** Queries with dynamic macros or late-bound runtime string evaluation that cannot be parsed into a standard AST before compilation.
- **Live Warehouse Permissions:** It does not inspect database role-based access control (RBAC) or table grants.

---

## Defense-in-Depth Recommendation

Parallax is most effective when integrated into a layered quality assurance strategy:

1. **Syntax & Style:** Linters (e.g. SQLFluff) verify stylistic consistency.
2. **Semantic Drift & Blast Radius (Parallax):** Identifies logical shifts and downstream exposure impact in CI within milliseconds.
3. **Data Quality Tests:** dbt unit and integration tests (`unique`, `not_null`, custom tests) validate surviving warehouse data.
4. **Human Review:** Analytics engineers and business stakeholders review flagged PRs based on Parallax recommendations.

---

---

## Outbound Network Traffic Inventory

Parallax is strictly sandboxed by default:

| Execution Context | Permitted Network Calls | Destination | Purpose |
| :--- | :--- | :--- | :--- |
| **CLI / Local Run** | **None (0 requests)** | N/A | Strictly local execution in memory |
| **Pre-commit Hook** | **None (0 requests)** | N/A | Strictly local execution in memory |
| **GitHub Action** | **HTTPS (REST API)** | `api.github.com` | Posts PR comments using caller's `${{ secrets.GITHUB_TOKEN }}` |

Under no circumstances does Parallax phone home, ping telemetry aggregators, or contact any third-party domain.

---

## Dependency License Audit

All runtime dependencies of Parallax are distributed under permissive open-source licenses (MIT and BSD-3-Clause). There is zero copyleft (GPL/AGPL) risk:

| Dependency | License | Copyleft Risk | Primary Usage |
| :--- | :--- | :--- | :--- |
| `sqlglot` | MIT | None | SQL Abstract Syntax Tree parsing and semantic diffing |
| `networkx` | BSD-3-Clause | None | Directed Acyclic Graph (DAG) construction and BFS traversal |
| `rich` | MIT | None | Terminal output formatting and visual styling |
| `click` | BSD-3-Clause | None | Command-line interface definition and argument parsing |
| `pydantic` | MIT | None | Validated immutable data schemas (Pydantic v2) |
| `pyyaml` | MIT | None | Parallax configuration file (`.parallax.yml`) parsing |

---

## Trademark Notice

**dbt™** is a registered trademark of dbt Labs, Inc. 

Parallax is an independent open-source project and is not affiliated with, sponsored by, or endorsed by dbt Labs, Inc. Use of the mark "dbt" in this documentation and project is strictly nominative to describe compatibility with the dbt open-source framework and its artifact specifications.

---

## Legal Disclaimer & Limitation of Liability

Parallax is distributed as open-source software under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

In particular, attention is drawn to **Sections 7 and 8** of the Apache 2.0 License:

- **Section 7 (Disclaimer of Warranty):** Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
- **Section 8 (Limitation of Liability):** In no event and under no legal theory, whether in tort (including negligence), contract, or otherwise, shall any Contributor be liable to you for damages, including any direct, indirect, special, incidental, or consequential damages of any character arising as a result of this License or out of the use or inability to use the Work.

Parallax provides static diagnostic analysis based on source code and compiled metadata. It does not provide legal, financial, or regulatory compliance verification. Organizations remain responsible for their own data governance policies, schema migrations, and metric validation.
