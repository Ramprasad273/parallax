# GitHub Actions Workflow

Integrate Parallax directly into your GitHub pull request checks to prevent breaking SQL changes from reaching production.

---

## Quick Setup

Add this job to your `.github/workflows/dbt_ci.yml`:

```yaml
name: "dbt CI"

on:
  pull_request:
    paths:
      - "models/**"
      - "seeds/**"

jobs:
  blast_radius:
    name: "Parallax Blast Radius CI"
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read

    steps:
      - name: Checkout PR Branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Full git history required for diffing against base

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Dependencies
        run: |
          pip install dbt-snowflake git+https://github.com/Ramprasad273/parallax.git

      - name: Compile dbt Manifest
        run: dbt compile

      - name: Run Parallax Check
        run: |
          parallax check \
            --manifest target/manifest.json \
            --base origin/${{ github.base_ref }} \
            --fail-on CRITICAL \
            --format markdown \
            --output pr_comment.md

      - name: Post PR Comment
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            if (fs.existsSync('pr_comment.md')) {
              const body = fs.readFileSync('pr_comment.md', 'utf8');
              const commentMarker = '<!-- parallax-ci-comment -->';
              
              // Find existing comment to update in-place
              const { data: comments } = await github.rest.issues.listComments({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
              });
              
              const botComment = comments.find(c => c.body.includes(commentMarker));
              
              if (botComment) {
                await github.rest.issues.updateComment({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  comment_id: botComment.id,
                  body: body,
                });
              } else {
                await github.rest.issues.createComment({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  issue_number: context.issue.number,
                  body: body,
                });
              }
            }
```

---

## Required Permissions

To post and update PR comments, ensure your workflow defines:

```yaml
permissions:
  pull-requests: write
  contents: read
```

---

## Git Fetch Depth

!!! warning "Important: Set fetch-depth to 0"
    Parallax needs to compare your PR branch against the target base branch (e.g. `origin/main`). Ensure `actions/checkout` specifies `fetch-depth: 0` so Git has the full commit tree.
