"""Standalone static HTML report generator for Parallax."""

import html

from parallax.core.models import BlastRadiusReport, RiskSeverity


class HTMLFormatter:
    """Generates a single self-contained HTML report with embedded styles."""

    @classmethod
    def render(cls, report: BlastRadiusReport) -> str:
        sev_color = {
            RiskSeverity.CRITICAL: "#ef4444",
            RiskSeverity.HIGH: "#f59e0b",
            RiskSeverity.MEDIUM: "#3b82f6",
            RiskSeverity.LOW: "#10b981",
            RiskSeverity.NEVER: "#6b7280",
        }.get(report.risk_severity, "#ef4444")

        diff_rows = []
        for d in report.ast_diffs:
            for p in d.predicates:
                diff_rows.append(f"""
                <tr>
                    <td><code>{html.escape(d.model_name)}</code></td>
                    <td>{p.clause.value}</td>
                    <td><span class="badge badge-warning">{p.diff_type.value}</span></td>
                    <td><code>{html.escape(p.old_expression or "-")}</code></td>
                    <td><code>{html.escape(p.new_expression or "-")}</code></td>
                </tr>
                """)
            for c in d.columns:
                diff_rows.append(f"""
                <tr>
                    <td><code>{html.escape(d.model_name)}</code></td>
                    <td>COLUMN</td>
                    <td><span class="badge badge-info">{c.diff_type.value}</span></td>
                    <td><code>{html.escape(c.old_expression or "-")}</code></td>
                    <td><code>{html.escape(c.new_expression or c.column_name)}</code></td>
                </tr>
                """)

        downstream_rows = []
        for m in report.downstream_models:
            broken_badge = (
                f'<span class="badge badge-danger">Broken: {", ".join(m.broken_columns)}</span>'
                if m.broken_columns
                else '<span class="badge badge-success">OK</span>'
            )
            downstream_rows.append(f"""
            <tr>
                <td><code>{html.escape(m.name)}</code></td>
                <td>{m.layer.value}</td>
                <td>{m.distance_from_source}</td>
                <td>{broken_badge}</td>
            </tr>
            """)

        exposure_list = []
        for e in report.impacted_exposures:
            exposure_list.append(f"""
            <li class="exposure-item">
                <strong>{html.escape(e.label or e.name)}</strong> ({e.exposure_type.value})
                {f'<span class="dim"> - Owner: {html.escape(e.owner_name)}</span>' if e.owner_name else ""}
            </li>
            """)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Parallax Blast Radius Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 30px;
        }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 20px; }}
        h1 {{ font-size: 24px; margin: 0; color: #38bdf8; }}
        .card {{ background-color: #1e293b; border-radius: 8px; padding: 24px; margin-top: 24px; border: 1px solid #334155; }}
        .severity-badge {{ background-color: {
            sev_color
        }; color: #ffffff; padding: 6px 14px; border-radius: 9999px; font-weight: bold; font-size: 14px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 20px; }}
        .metric-box {{ background-color: #0f172a; padding: 16px; border-radius: 6px; text-align: center; border: 1px solid #334155; }}
        .metric-value {{ font-size: 28px; font-weight: bold; color: #38bdf8; }}
        .metric-label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }}
        th {{ color: #94a3b8; text-transform: uppercase; font-size: 12px; }}
        code {{ background-color: #0f172a; padding: 2px 6px; border-radius: 4px; color: #f43f5e; font-size: 13px; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        .badge-danger {{ background-color: #ef4444; color: white; }}
        .badge-warning {{ background-color: #f59e0b; color: black; }}
        .badge-info {{ background-color: #3b82f6; color: white; }}
        .badge-success {{ background-color: #10b981; color: white; }}
        ul.exposure-list {{ list-style-type: none; padding-left: 0; }}
        li.exposure-item {{ padding: 8px 12px; background: #0f172a; margin-bottom: 8px; border-radius: 6px; border-left: 4px solid #ef4444; }}
        .dim {{ color: #94a3b8; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>PARALLAX</h1>
                <p class="dim" style="margin: 4px 0 0 0;">Zero-Config Blast Radius & Semantic Drift CI</p>
            </div>
            <div>
                <span class="severity-badge">{report.risk_severity.value} RISK</span>
            </div>
        </div>

        <div class="card">
            <h2>Executive Summary</h2>
            <p style="font-size: 16px; line-height: 1.5;">{
            html.escape(report.plain_english_summary)
        }</p>

            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-value">{len(report.modified_models)}</div>
                    <div class="metric-label">Modified Models</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{len(report.downstream_models)}</div>
                    <div class="metric-label">Downstream Models</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{len(report.impacted_exposures)}</div>
                    <div class="metric-label">Impacted Exposures</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{report.max_dag_depth}</div>
                    <div class="metric-label">DAG Depth</div>
                </div>
            </div>
        </div>

        {
            f'''<div class="card">
            <h2>Impacted Executive Exposures</h2>
            <ul class="exposure-list">
                {"".join(exposure_list)}
            </ul>
        </div>'''
            if exposure_list
            else ""
        }

        {
            f'''<div class="card">
            <h2>AST Semantic Diffs</h2>
            <table>
                <thead>
                    <tr><th>Model</th><th>Clause</th><th>Change Type</th><th>Original</th><th>New / Altered</th></tr>
                </thead>
                <tbody>
                    {"".join(diff_rows)}
                </tbody>
            </table>
        </div>'''
            if diff_rows
            else ""
        }

        {
            f'''<div class="card">
            <h2>Downstream Lineage Models</h2>
            <table>
                <thead>
                    <tr><th>Model</th><th>Layer</th><th>DAG Distance</th><th>Status</th></tr>
                </thead>
                <tbody>
                    {"".join(downstream_rows)}
                </tbody>
            </table>
        </div>'''
            if downstream_rows
            else ""
        }
    </div>
</body>
</html>
"""
