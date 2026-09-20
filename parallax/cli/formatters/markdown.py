"""GitHub PR Comment Markdown Formatter for Parallax."""

from parallax.core.models import BlastRadiusReport, RiskSeverity


class MarkdownFormatter:
    """Generates structured GitHub PR comment markdown with collapsible sections."""

    COMMENT_MARKER = "<!-- parallax-ci-comment -->"

    @classmethod
    def render(cls, report: BlastRadiusReport) -> str:
        """Render complete PR comment markdown."""
        badge_color = {
            RiskSeverity.CRITICAL: "red",
            RiskSeverity.HIGH: "orange",
            RiskSeverity.MEDIUM: "yellow",
            RiskSeverity.LOW: "brightgreen",
            RiskSeverity.NEVER: "lightgrey",
        }.get(report.risk_severity, "red")

        badge_url = f"https://img.shields.io/badge/Parallax_CI-{report.risk_severity.value}_RISK-{badge_color}?style=for-the-badge"

        broken_count = sum(len(m.broken_columns) for m in report.downstream_models)
        ci_gate = "**BLOCK**" if report.risk_severity.value in ("CRITICAL", "HIGH") else "**PASS**"

        lines: list[str] = [
            cls.COMMENT_MARKER,
            f"![Parallax CI Status]({badge_url})",
            "",
            f"> {report.plain_english_summary.replace('**', '**')}",
            "",
            "### Blast Radius Overview",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| **Modified Models** | `{len(report.modified_models)}` |",
            f"| **Impacted Downstream Models** | `{len(report.downstream_models)}` |",
            f"| **Impacted BI Exposures** | `{len(report.impacted_exposures)}` |",
            f"| **Max Lineage Depth** | `{report.max_dag_depth} hops` |",
            f"| **CI Gate** | {ci_gate} |",
        ]

        if broken_count > 0:
            broken_cols = [
                f"`{col}` in `{m.name}`"
                for m in report.downstream_models
                for col in m.broken_columns
            ]
            lines.append(f"| **Broken Column References** | {', '.join(broken_cols)} |")

        # AST Semantic Diffs (Collapsible)
        lines.extend(
            [
                "",
                "<details>",
                "<summary><strong>View AST Semantic Diffs</strong></summary>",
                "",
                "| Model | Clause / Type | Before | After | Explanation |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )

        for d in report.ast_diffs:
            for p in d.predicates:
                old = f"`{p.old_expression}`" if p.old_expression else "*None*"
                new = f"`{p.new_expression}`" if p.new_expression else "*None*"
                expl = p.explanation.replace("|", "\\|") if p.explanation else ""
                lines.append(
                    f"| `{d.model_name}` | {p.clause.value} ({p.diff_type.value}) | {old} | {new} | {expl} |"
                )
            for c in d.columns:
                old = f"`{c.old_expression}`" if c.old_expression else "*was present*"
                new = f"`{c.new_expression or c.column_name}`"
                expl = c.explanation.replace("|", "\\|") if c.explanation else ""
                lines.append(
                    f"| `{d.model_name}` | COLUMN ({c.diff_type.value}) | {old} | {new} | {expl} |"
                )
            for j in d.structural.join_diffs:
                expl = j.explanation.replace("|", "\\|") if j.explanation else ""
                lines.append(
                    f"| `{d.model_name}` | JOIN ({j.diff_type.value}) | `{j.old_join_type}` | `{j.new_join_type}` on `{j.table_name}` | {expl} |"
                )

        lines.extend(
            [
                "",
                "</details>",
                "",
            ]
        )

        # Downstream Lineage & Exposures (Collapsible)
        if report.downstream_models or report.impacted_exposures:
            lines.extend(
                [
                    "<details>",
                    "<summary><strong>View Downstream Lineage & Impacted Exposures</strong></summary>",
                    "",
                ]
            )
            if report.impacted_exposures:
                lines.extend(
                    [
                        "#### Impacted Exposures (Dashboards & Reverse ETL)",
                        "",
                    ]
                )
                for exp in report.impacted_exposures:
                    owner = f" *(Owner: {exp.owner_name})*" if exp.owner_name else ""
                    lines.append(
                        f"* **{exp.label or exp.name}** ({exp.exposure_type.value}){owner}"
                    )
                lines.append("")

            if report.downstream_models:
                lines.extend(
                    [
                        "#### Downstream Models",
                        "",
                        "| Model | Layer | Hop | Broken Columns |",
                        "| :--- | :--- | :--- | :--- |",
                    ]
                )
                for m in report.downstream_models:
                    broken = f"`{', '.join(m.broken_columns)}`" if m.broken_columns else "–"
                    lines.append(
                        f"| `{m.name}` | {m.layer.value} | {m.distance_from_source} | {broken} |"
                    )
                lines.append("")

            # Column-Level Lineage Traces — sourced from DownstreamNode.column_impacts
            # (the authoritative source; report.column_lineage_paths is also populated
            # but this guarantees we show per-model broken traces even if the top-level
            # field is not populated by older versions of the risk engine)
            all_impacts = [
                ci for m in report.downstream_models for ci in m.column_impacts if ci.is_broken
            ]
            if not all_impacts:
                # Fallback: use top-level column_lineage_paths (broken only)
                all_impacts = [ci for ci in report.column_lineage_paths if ci.is_broken]

            if all_impacts:
                lines.extend(
                    [
                        "#### Column-Level Lineage Traces (Broken)",
                        "",
                        "| Downstream Column | Model | Upstream Origin | Derivation Trail | Status |",
                        "| :--- | :--- | :--- | :--- | :--- |",
                    ]
                )
                seen = set()
                for ci in all_impacts:
                    key = (ci.model_name, ci.column_name, ci.upstream_column)
                    if key in seen:
                        continue
                    seen.add(key)
                    trail = (
                        " &rarr; ".join(f"`{s}`" for s in ci.lineage_path)
                        if ci.lineage_path
                        else f"`{ci.upstream_model}.{ci.upstream_column}`"
                    )
                    status = "**BROKEN**"
                    lines.append(
                        f"| `{ci.column_name}` | `{ci.model_name}` | `{ci.upstream_model}.{ci.upstream_column}` | {trail} | {status} |"
                    )
                lines.append("")

            lines.extend(["</details>", ""])

        # Remediation Advice
        if report.remediation_advice:
            lines.extend(
                [
                    "### Remediation Checklist",
                    "",
                ]
            )
            for advice in report.remediation_advice:
                lines.append(f"- [ ] {advice}")
            lines.append("")

        lines.extend(
            [
                "---",
                "*Generated by [Parallax](https://github.com/Ramprasad273/parallax) • Zero-Config Blast Radius CI for SQL & dbt*",
            ]
        )

        return "\n".join(lines)
