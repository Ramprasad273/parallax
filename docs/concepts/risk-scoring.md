# Risk Scoring Engine

Parallax synthesizes AST diffs, lineage depth, downstream volume, and exposure metadata into a deterministic **Risk Severity Score**.

---

## Risk Severity Levels

| Severity | Color | Criteria | Recommended Action |
| :--- | :--- | :--- | :--- |
| **CRITICAL** | Red | Broken columns referenced downstream, dropped columns with downstream consumers, or predicate/join mutations upstream of BI exposures or tier-tagged models. | **Block PR.** Requires mandatory sign-off from model owner or data lead. |
| **HIGH** | Yellow | Join mutations without exposures, predicate alterations affecting > 5 downstream models or marts layer, or dropped columns without confirmed consumers. | **Review with care.** Ensure downstream stakeholders are notified. |
| **MEDIUM** | Blue | Column calculation/expression alterations, isolated filter changes, or non-breaking column additions. | Standard peer review. |
| **LOW** | Cyan | Minor additions or changes with zero downstream risk or blast radius. | Safe to merge after review. |
| **NONE** | Gray | Pure formatting, comments, or non-semantic changes. | Instant pass; zero CI comment spam. |

---

## Scoring Factors

The scoring algorithm deterministically evaluates 8 cascading priority rules:

1. **Rule 1 — Broken Columns:**
   - Downstream models referencing a dropped column via regex word-boundary immediately trigger **CRITICAL**.
   - Any dropped column in a model with downstream consumers triggers **CRITICAL**.
2. **Rule 2 & 3 — Critical Path Mutations:**
   - Any predicate tightening/mutation or join type modification upstream of a declared `EXPOSURE` or model matching `tier_tags` (e.g. `tier_1`, `finance`, `executive`, `board`, `p0`) triggers **CRITICAL**.
3. **Rule 4, 5 & 6 — High-Impact Mutations:**
   - Join mutations (e.g. `INNER` to `LEFT`) without direct exposure impact trigger **HIGH**.
   - Predicate changes cascading to `> 5` downstream models or any `marts` model trigger **HIGH**.
   - Dropped columns in models without known downstream consumers trigger **HIGH**.
4. **Rule 7 & 8 — Moderate & Localized Changes:**
   - Calculation/expression modifications or isolated predicate changes evaluate to **MEDIUM**.
   - Non-breaking column additions evaluate to **MEDIUM**.
   - Pure cosmetic/comment diffs evaluate to **LOW** (or pass).

---

## Actionable Remediation Guidance

Along with the severity assessment, Parallax automatically generates concrete remediation items, such as:

- Verifying impacted filter expressions against stakeholder requirements.
- Auditing dropped records with a sample warehouse query.
- Updating downstream model references or adding deprecation aliases.
- Notifying listed owners of impacted BI dashboards.
