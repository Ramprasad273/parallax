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

## Legal & Compliance Notice

Parallax is distributed as open-source software under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

```text
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

Parallax provides static diagnostic analysis based on source code and compiled metadata. It does not provide legal, financial, or regulatory compliance verification. Organizations remain responsible for their own data governance policies, schema migrations, and metric validation.
