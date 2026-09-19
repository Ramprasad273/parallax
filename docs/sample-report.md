# Sample Report & Interpretation

This guide walks through a realistic Parallax terminal report and explains how to interpret each section during local development or pull request review.

---

## The Scenario

Suppose an engineer opens a pull request that modifies `models/staging/stg_orders.sql`:

```diff
-- models/staging/stg_orders.sql
- WHERE status NOT IN ('returned', 'cancelled')
+ WHERE status = 'delivered'
```

When running `parallax demo` or inspecting a pull request check, Parallax generates the following report:

```text
────────────────────────────  PARALLAX  Blast Radius & Semantic Drift  ─────────────────────────────
  main  >  pr/clean-order-filter    2026-09-12 15:26 UTC    11.4 ms

╭─  RISK: CRITICAL  ───────────────────────────────────────────────────────────────────────────────╮
│  CRITICAL RISK: PR tightened filter `NOT status IN ('returned', 'cancelled')` -> `status =       │
│  'delivered'` on `stg_orders`. This cascades across 18 downstream models and impacts 3           │
│  Executive Exposures (`Board Financials Summary`, `Executive ARR Dashboard`, `Sales Commission   │
│  Sync`).                                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

╭─ Overview ───────────────────────────────────────────────────────────────────────────────────────╮
│   Modified models                           1                                                    │
│   Downstream models impacted               18                                                    │
│   BI exposures affected                     3                                                    │
│   Longest lineage path (hops)               4                                                    │
│   Breaking column references             none                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

────────────────────────────────────────  Semantic Changes  ────────────────────────────────────────

╭──────────────────────────────────────────────────────────────────────────────────────────────────╮
│  Model    stg_orders                                                                             │
│  Scope    WHERE                                                                                  │
│  Change   TIGHTENED                                                                              │
│  Before   NOT status IN ('returned', 'cancelled')                                                │
│  After    status = 'delivered'                                                                   │
│  Note     Filter tightened from negative exclusion (NOT status IN ('returned', 'cancelled')) to  │
│           strict match (status = 'delivered'), omitting unhandled categories.                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

────────────────────────────────────  Downstream Blast Radius  ─────────────────────────────────────

  Downstream Models

  INTERMEDIATE  4 models  (hop 1)
    int_customer_orders
    int_net_payments
    int_order_items
    int_subscription_periods

  MARTS  8 models  (hop 2)
    dim_customers
    dim_products
    dim_sales_reps
    dim_subscriptions
    fct_churn_daily
    fct_customer_transactions
    fct_mrr_monthly
    fct_orders

  REPORTING  6 models  (hop 3)
    rpt_cohort_retention
    rpt_daily_pipeline
    rpt_executive_kpis
    rpt_monthly_finance_board
    rpt_regional_performance
    rpt_sales_commission_sync

  Impacted BI Exposures
  Exposure                     Type              Owner                    
──────────────────────────────────────────────────────────────────────────
  Board Financials Summary     DASHBOARD         VP Finance               
  Executive ARR Dashboard      DASHBOARD         Chief Financial Officer  
  Sales Commission Sync        REVERSE_ETL       Sales Ops                

──────────────────────────────────────  Recommended Actions  ───────────────────────────────────────

   1.  Verify business metrics: Confirm that filter/calculation changes do not unintentionally
       alter executive metrics on: Board Financials Summary, Executive ARR Dashboard, Sales
       Commission Sync.
   2.  Audit dropped records: Confirm whether omitting non-matching statuses (e.g.
       pending/in-transit/disputed) was intended by business stakeholders.

─────────────────────────────────────────  CI gate: BLOCK  ─────────────────────────────────────────
  github.com/Ramprasad273/parallax
```

---

## Section-by-Section Interpretation

### 1. Metadata Header
```text
  main  >  pr/clean-order-filter    2026-09-12 15:26 UTC    11.4 ms
```
- **What you can infer:** Confirms the exact Git base and target references being diffed, the execution timestamp, and the analysis runtime (11.4 milliseconds). This validates that the check evaluated the current branch state almost instantaneously.

---

### 2. Risk Assessment Banner
```text
╭─  RISK: CRITICAL  ───────────────────────────────────────────────────────────────────────────────╮
│  CRITICAL RISK: PR tightened filter `NOT status IN ('returned', 'cancelled')` -> `status =       │
│  'delivered'` on `stg_orders`. This cascades across 18 downstream models and impacts 3           │
│  Executive Exposures (`Board Financials Summary`, `Executive ARR Dashboard`, `Sales Commission   │
│  Sync`).                                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```
- **What you can infer:** A rapid, high-level summary for reviewers. 
- **Key takeaways:**
  - **Severity:** `CRITICAL` (indicates potential business or financial metric disruption).
  - **Direct Cause:** A predicate alteration on `stg_orders`.
  - **Ripple Scale:** 18 models and 3 executive-facing exposures are directly downstream.

---

### 3. Overview Metrics Table
```text
╭─ Overview ───────────────────────────────────────────────────────────────────────────────────────╮
│   Modified models                           1                                                    │
│   Downstream models impacted               18                                                    │
│   BI exposures affected                     3                                                    │
│   Longest lineage path (hops)               4                                                    │
│   Breaking column references             none                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```
- **What you can infer:** 
  - Even though only **1 SQL file** was edited, the blast radius is wide (18 downstream models across 4 hops).
  - **Breaking column references:** `none` means no column was deleted or renamed in a way that breaks SQL syntax downstream. However, the data content passing through those columns has shifted.

---

### 4. Semantic Changes (AST Diff)
```text
╭──────────────────────────────────────────────────────────────────────────────────────────────────╮
│  Model    stg_orders                                                                             │
│  Scope    WHERE                                                                                  │
│  Change   TIGHTENED                                                                              │
│  Before   NOT status IN ('returned', 'cancelled')                                                │
│  After    status = 'delivered'                                                                   │
│  Note     Filter tightened from negative exclusion (NOT status IN ('returned', 'cancelled')) to  │
│           strict match (status = 'delivered'), omitting unhandled categories.                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```
- **What you can infer:** 
  - **Scope:** The change occurred in a `WHERE` clause (filtering rows).
  - **Classification (`TIGHTENED`):** The new filter is strictly more restrictive than the original.
  - **Business Meaning:** Orders in status `'in_transit'`, `'processing'`, or `'pending'` were previously included in `stg_orders`, but will now be excluded. Reviewers should immediately question whether this was intentional.

---

### 5. Downstream Blast Radius & Exposure Lineage
```text
  Downstream Models

  INTERMEDIATE  4 models  (hop 1)
    ...
  MARTS  8 models  (hop 2)
    ...
  REPORTING  6 models  (hop 3)
    ...

  Impacted BI Exposures
  Exposure                     Type              Owner                    
──────────────────────────────────────────────────────────────────────────
  Board Financials Summary     DASHBOARD         VP Finance               
  Executive ARR Dashboard      DASHBOARD         Chief Financial Officer  
  Sales Commission Sync        REVERSE_ETL       Sales Ops                
```
- **What you can infer:**
  - **Layer Propagation:** The change ripples from staging through intermediate models (`int_customer_orders`), into core marts (`fct_orders`, `fct_mrr_monthly`), up to executive reporting tables.
  - **Stakeholder Ownership:** Crucially identifies that the **Chief Financial Officer**, **VP Finance**, and **Sales Ops** own assets directly affected by this PR.
  - **Action:** The PR author should request approval or notify these owners prior to merging.

---

### 6. Recommended Actions
```text
   1.  Verify business metrics: Confirm that filter/calculation changes do not unintentionally
       alter executive metrics on: Board Financials Summary, Executive ARR Dashboard, Sales
       Commission Sync.
   2.  Audit dropped records: Confirm whether omitting non-matching statuses (e.g.
       pending/in-transit/disputed) was intended by business stakeholders.
```
- **What you can infer:** Clear, actionable steps the developer can take before merging. Instead of vague warnings, it tells the engineer exactly what to audit and which stakeholders to coordinate with.

---

### 7. CI Gate Status
```text
─────────────────────────────────────────  CI gate: BLOCK  ─────────────────────────────────────────
```
- **What you can infer:** Under the configured threshold (`--fail-on CRITICAL`), this pull request will exit with status code `1` and block merge automation until resolved, justified, or signed off by an authorized maintainer.

---

## Visualizing via Interactive HTML & GitHub Actions

In addition to terminal output, Parallax outputs rich interactive standalone HTML artifacts and automated GitHub PR comments:

### Interactive Standalone HTML Report
Features deterministic SVG node-and-edge lineage graphs, column-level derivation pill chains, and schema contract audit tables:

[![Interactive Standalone HTML Report](assets/images/html-report.png)](assets/images/html-report.png)

### Automated GitHub PR Audit Comment & CI Gate
Posts structured AST diffs, affected business exposures, and blocks merges automatically on risk breaches:

[![GitHub Actions CI PR Gate](assets/images/github-ci-pr.png)](assets/images/github-ci-pr.png)

