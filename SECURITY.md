# Security Policy

The Parallax team and contributors take the security and integrity of Parallax seriously. We welcome responsible security reports and appreciate the community's efforts to improve the security of this project.

---

## Supported Versions

Only the latest minor release is actively supported with security patches and bug fixes:

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |
| < 0.1.0 | No        |

---

## Reporting a Vulnerability

If you discover a potential security vulnerability in Parallax, please **do not open a public issue or pull request**. Public disclosure can compromise user environments before a fix is available.

Instead, please report the vulnerability confidentially via email:

**Email:** [security@parallax-ci.dev](mailto:security@parallax-ci.dev)

Please include the following details in your report:
- **Description:** A clear description of the vulnerability and its potential impact.
- **Reproduction Steps:** Minimal reproducible example (SQL scripts, dbt manifest snippets, or CLI invocation).
- **Environment:** OS, Python version, Parallax version, and relevant dependencies.
- **Remediation:** Any proposed patches, fixes, or workarounds if available.

### Response Timelines

- **Initial Acknowledgment:** Within 48 hours of receiving your email.
- **Assessment & Triage:** Within 5 business days, including confirmation of severity and impact.
- **Remediation & Advisory:** A patch and corresponding release will be prioritized and published alongside a security advisory.

---

## Privacy & Zero Data Collection

Parallax is architected from the ground up to respect user privacy and adhere to strict enterprise data boundaries:

- **Zero Telemetry:** Parallax collects absolutely zero telemetry, tracking events, user metrics, or usage statistics.
- **No Third-Party Analytics:** Parallax contains no embedded analytics engines, pingbacks, or third-party monitoring SDKs.
- **Strict Network Boundary:** When running in CLI or local mode, Parallax makes zero outbound network requests. When running as a GitHub Action, the sole outbound network connection is to `api.github.com` strictly using the caller's repository-scoped `GITHUB_TOKEN` to post pull request review comments.
- **No Data Retention:** Parallax processes your SQL models and dbt manifests purely in memory; no code or metadata is ever transmitted or stored outside your CI/CD runner.

---

## GitHub Security Advisories

We also support private vulnerability reporting directly through GitHub Security Advisories on the [Ramprasad273/parallax repository](https://github.com/Ramprasad273/parallax/security/advisories/new).

Thank you for helping keep Parallax and the data engineering community secure.
