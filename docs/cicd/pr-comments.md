# PR Comments & Reports

Parallax is designed for maximum clarity in code review without cluttering PR threads.

---

## Pinned In-Place Updates

When engineers push subsequent commits to a pull request, many CI tools spam the conversation thread with repeated comments.

Parallax uses a hidden marker:

```html
<!-- parallax-blast-radius-report -->
```

On every commit, Parallax checks whether a previous comment exists. If found, it **updates the comment in-place**, keeping your PR review history clean and single-threaded.

---

## Zero-Noise Policy

If a pull request contains:
- Code reformatting (whitespace, linebreaks, casing)
- Comment alterations
- Documentation edits
- Renaming internal variables without altering output semantics

Parallax reports **NO RISK** and will **not post unnecessary warnings** or block the PR. Reviewers only get alerted when real business metrics or downstream models are at risk.

---

## GitHub Step Summary Integration

In addition to PR comments, Parallax writes its full report to GitHub Actions' native **Job Summary**:

```bash
parallax check --format markdown >> $GITHUB_STEP_SUMMARY
```

Engineers can inspect the full blast radius directly inside the GitHub Actions run tab without leaving their browser.

---

## Interactive Collapsible Sections

To keep comments concise:
- High-level executive summaries and risk badges appear at the top.
- Detailed AST comparisons and full multi-hop lineage paths are enclosed in collapsible `<details>` tags.
- Reviewers can expand exactly what they need without scrolling past hundreds of lines.
