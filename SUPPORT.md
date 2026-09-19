# Support for Parallax

Thank you for using Parallax! We want to ensure you have a seamless experience running Blast Radius & Semantic Drift CI in your data engineering workflows.

---

## 📖 Documentation

Before opening an issue or asking a question, please check our documentation:
- **README & Architecture Guide:** See the [README.md](README.md) for quickstart, CLI options, and YAML configuration.
- **Contributing Guide:** See [CONTRIBUTING.md](CONTRIBUTING.md) for local development, testing, and pull request guidelines.
- **Security Policy:** See [SECURITY.md](SECURITY.md) for vulnerability disclosure and credential handling.

---

## 💬 Getting Help

### 1. General Questions & Community Discussions
If you have questions about:
- Best practices for integrating Parallax with specific dbt or CI/CD pipelines
- Dialect nuances or AST parsing edge cases
- Sharing feedback or discussing proposed features

👉 Please use **[GitHub Discussions](https://github.com/parallax-ci/parallax/discussions)**.

### 2. Bug Reports & Defects
If you encounter a bug, broken parsing, or unexpected behavior:
1. Search **[Existing Issues](https://github.com/parallax-ci/parallax/issues)** to see if the issue has already been reported.
2. If not, open a **[New Issue](https://github.com/parallax-ci/parallax/issues/new)** and provide:
   - Parallax version (`parallax --version`)
   - SQL dialect in use (`snowflake`, `bigquery`, `duckdb`, etc.)
   - Minimal reproducible SQL before/after diff or `target/manifest.json` snippet
   - Expected behavior vs actual output

### 3. Feature Requests
Feature suggestions are welcome! Please open an issue with the `enhancement` label describing:
- The problem you are solving
- Proposed CLI flags, configuration schema, or reporting formats
- Why this benefits the broader data engineering community

---

## 🔒 Security Vulnerabilities

Please **do not** open public GitHub issues for security vulnerabilities. Review our [Security Policy](SECURITY.md) for instructions on confidential disclosure.

---

## ⏱️ Response Expectations

Parallax is open-source software maintained with care. Community issues and discussions are reviewed on a best-effort basis. For urgent production regressions or security advisories, maintainers prioritize reviews promptly.
