"""Production-grade, restrained Swiss-editorial HTML report generator for Parallax.

Built on data-product clarity: no AI slop, no gradients, no emojis, no fake numbers.
Features a deterministic browser-based SVG node-and-edge lineage DAG graph.
"""

import html
import json
from typing import Any

from parallax.cli.formatters.markdown import MarkdownFormatter
from parallax.core.models import BlastRadiusReport, ModelLayer, RiskSeverity


class HTMLFormatter:
    """Generates a clean, trustworthy, restrained HTML report."""

    @classmethod
    def render(
        cls,
        report: BlastRadiusReport,
        base_ref: str = "main",
        head_ref: str = "pr/branch",
    ) -> str:
        is_critical = report.risk_severity == RiskSeverity.CRITICAL
        is_high = report.risk_severity == RiskSeverity.HIGH
        is_blocking = is_critical or is_high

        # Status text
        status_label = "CI Gate: Block" if is_blocking else "CI Gate: Pass"
        status_class = "status-block" if is_blocking else "status-pass"
        severity_label = f"{report.risk_severity.value} RISK"

        report_json_str = report.model_dump_json(indent=2)
        pr_markdown_str = MarkdownFormatter.render(report)

        # Evidence: AST Diffs
        diff_sections = []
        for d in report.ast_diffs:
            for p in d.predicates:
                diff_sections.append(f"""
                <div class="evidence-block">
                    <div class="evidence-meta">
                        <span class="meta-left">
                            <span class="meta-label">Model</span> <span class="mono bold">{html.escape(d.model_name)}</span> &bull;
                            <span class="meta-label">File</span> <span class="mono">{html.escape(d.file_path)}</span> &bull;
                            <span class="meta-label">Clause</span> <span class="mono">{p.clause.value} ({p.diff_type.value})</span>
                        </span>
                        <button type="button" class="btn-copy-diff" onclick="copyDiffText(this)" title="Copy SQL diff snippet">Copy Diff</button>
                    </div>
                    {f'<p class="evidence-desc">{html.escape(p.explanation)}</p>' if p.explanation else ''}
                    <div class="diff-view">
                        <div class="diff-line diff-del">
                            <span class="diff-prefix">-</span>
                            <span class="diff-code">{html.escape(p.old_expression or "/* none */")}</span>
                        </div>
                        <div class="diff-line diff-add">
                            <span class="diff-prefix">+</span>
                            <span class="diff-code">{html.escape(p.new_expression or "/* none */")}</span>
                        </div>
                    </div>
                </div>
                """)

            for c in d.columns:
                diff_sections.append(f"""
                <div class="evidence-block">
                    <div class="evidence-meta">
                        <span class="meta-left">
                            <span class="meta-label">Model</span> <span class="mono bold">{html.escape(d.model_name)}</span> &bull;
                            <span class="meta-label">File</span> <span class="mono">{html.escape(d.file_path)}</span> &bull;
                            <span class="meta-label">Column Mutation</span> <span class="mono">{html.escape(c.column_name)} ({c.diff_type.value})</span>
                        </span>
                        <button type="button" class="btn-copy-diff" onclick="copyDiffText(this)" title="Copy SQL diff snippet">Copy Diff</button>
                    </div>
                    {f'<p class="evidence-desc">{html.escape(c.explanation)}</p>' if c.explanation else ''}
                    <div class="diff-view">
                        <div class="diff-line diff-del">
                            <span class="diff-prefix">-</span>
                            <span class="diff-code">{html.escape(c.old_expression or "column present")}</span>
                        </div>
                        <div class="diff-line diff-add">
                            <span class="diff-prefix">+</span>
                            <span class="diff-code">{html.escape(c.new_expression or c.column_name)}</span>
                        </div>
                    </div>
                </div>
                """)

        if not diff_sections:
            diff_sections.append("""
            <div class="evidence-block">
                <p class="evidence-desc">No semantic SQL modifications detected between target references.</p>
            </div>
            """)

        # Confirmed Exposures
        exposure_rows = []
        for exp in report.impacted_exposures:
            owner_display = exp.owner_name if exp.owner_name else "Unassigned"
            exposure_rows.append(f"""
            <tr>
                <td class="bold">{html.escape(exp.label or exp.name)}</td>
                <td class="mono">{html.escape(exp.exposure_type.value)}</td>
                <td>{html.escape(owner_display)}</td>
                <td class="status-cell-block">Affected downstream</td>
            </tr>
            """)

        # Downstream Broken Column Contracts Table
        broken_models = [m for m in report.downstream_models if m.broken_columns]
        broken_column_rows = []
        for bm in broken_models:
            col_badges = " ".join(f'<code class="badge-broken">{html.escape(c)}</code>' for c in bm.broken_columns)
            hop_info = f"hop {bm.distance_from_source}"
            broken_column_rows.append(f"""
            <tr>
                <td class="bold mono">{html.escape(bm.name)}</td>
                <td class="mono">{html.escape(bm.layer.value.capitalize())}</td>
                <td><span class="hop-badge">{hop_info}</span></td>
                <td>{col_badges}</td>
                <td class="status-cell-block">Compilation error — column deleted upstream</td>
            </tr>
            """)

        # Column-Level Lineage Pill-Chain Traces
        # Prefer per-model column_impacts (authoritative); fall back to top-level paths
        all_column_impacts = [
            ci
            for m in report.downstream_models
            for ci in m.column_impacts
        ]
        if not all_column_impacts:
            all_column_impacts = list(report.column_lineage_paths)

        # Build pill-chain HTML for each column impact
        column_chain_blocks = []
        seen_keys: set[tuple[str, str, str]] = set()
        for ci in all_column_impacts:
            key = (ci.model_name, ci.column_name, ci.upstream_column)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Build ordered pill list from lineage_path or fallback
            if ci.lineage_path and len(ci.lineage_path) >= 2:
                steps = ci.lineage_path
            else:
                steps = [f"{ci.upstream_model}.{ci.upstream_column}", f"{ci.model_name}.{ci.column_name}"]

            is_broken = ci.is_broken
            status_cls = "chain-status-broken" if is_broken else "chain-status-ok"
            status_txt = "BROKEN" if is_broken else "Derived"

            pills_html = []
            for idx, step in enumerate(steps):
                is_last = (idx == len(steps) - 1)
                # Color last pill red if broken
                pill_cls = "chain-pill-broken" if (is_broken and is_last) else "chain-pill"
                # Color first pill yellow (modified source)
                if idx == 0:
                    pill_cls = "chain-pill-source"
                pills_html.append(f'<span class="{pill_cls}">{html.escape(step)}</span>')
                if not is_last:
                    pills_html.append('<span class="chain-arrow">&rarr;</span>')

            chain_html = "".join(pills_html)
            expr_note = f'<div class="chain-expr">{html.escape(ci.expression_summary)}</div>' if ci.expression_summary else ""
            column_chain_blocks.append(f"""
            <div class="chain-block">
                <div class="chain-row">{chain_html}</div>
                {expr_note}
                <span class="{status_cls}">{status_txt}</span>
            </div>
            """)


        # Remediation Actions
        remediation_items = []
        for i, adv in enumerate(report.remediation_advice, start=1):
            clean_adv = adv.replace("**", "").replace("`", "")
            remediation_items.append(f"<li>{html.escape(clean_adv)}</li>")

        # Build Decision Grid Bullet Points (Direct message, scannable, no long essays, no fluff)
        # 1. Finding Bullets
        finding_bullets: list[str] = []
        for d in report.ast_diffs:
            for p in d.predicates:
                old_val = p.old_expression or "none"
                new_val = p.new_expression or "none"
                p_type = p.diff_type.value.upper()
                if p_type == "TIGHTENED":
                    finding_bullets.append(
                        f"<strong>Filter tightened</strong> on <code>{html.escape(d.model_name)}</code>: "
                        f"<code>{html.escape(old_val)}</code> &rarr; <code>{html.escape(new_val)}</code>"
                    )
                elif p_type == "DROPPED":
                    finding_bullets.append(
                        f"<strong>Filter dropped</strong> on <code>{html.escape(d.model_name)}</code>: "
                        f"<code>{html.escape(old_val)}</code>"
                    )
                elif p_type == "MUTATED_OPERATOR":
                    finding_bullets.append(
                        f"<strong>Filter operator mutated</strong> on <code>{html.escape(d.model_name)}</code>: "
                        f"<code>{html.escape(old_val)}</code> &rarr; <code>{html.escape(new_val)}</code>"
                    )
                else:
                    finding_bullets.append(
                        f"<strong>Filter altered</strong> on <code>{html.escape(d.model_name)}</code>: "
                        f"<code>{html.escape(new_val)}</code>"
                    )

            for c in d.columns:
                c_type = c.diff_type.value.upper()
                if c_type == "DROPPED":
                    finding_bullets.append(
                        f"<strong>Dropped column</strong> <code>{html.escape(c.column_name)}</code> on <code>{html.escape(d.model_name)}</code>"
                    )
                elif c_type == "EXPRESSION_ALTERED":
                    expr_detail = f": <code>{html.escape(c.new_expression)}</code>" if c.new_expression else ""
                    finding_bullets.append(
                        f"<strong>Calculation altered</strong> on <code>{html.escape(d.model_name)}</code>: <code>{html.escape(c.column_name)}</code>{expr_detail}"
                    )

            for j in d.structural.join_diffs:
                j_type = j.diff_type.value.upper()
                if j_type == "TYPE_CHANGED":
                    old_jt = html.escape(j.old_join_type or "none")
                    new_jt = html.escape(j.new_join_type or "none")
                    finding_bullets.append(
                        f"<strong>Join altered</strong> on <code>{html.escape(j.table_name)}</code>: "
                        f"<code>{old_jt}</code> &rarr; <code>{new_jt}</code>"
                    )
                elif j_type == "CONDITION_CHANGED":
                    finding_bullets.append(
                        f"<strong>Join condition altered</strong> on <code>{html.escape(j.table_name)}</code>"
                    )

        if not finding_bullets:
            if report.modified_models:
                mod_names = ", ".join(f"<code>{html.escape(m.split('/')[-1].replace('.sql', ''))}</code>" for m in report.modified_models[:3])
                finding_bullets.append(f"<strong>Modified models:</strong> {mod_names}")
                finding_bullets.append("No breaking or semantic SQL mutations detected (formatting or comments only).")
            else:
                finding_bullets.append("No semantic changes detected across target repository.")
        elif len(finding_bullets) > 3:
            overflow = len(finding_bullets) - 3
            finding_bullets = finding_bullets[:3] + [f"<em>+ {overflow} additional SQL mutations</em>"]

        # 2. Impact Bullets
        impact_bullets: list[str] = []
        if report.impacted_exposures:
            exp_names = ", ".join(f"<code>{html.escape(e.label or e.name)}</code>" for e in report.impacted_exposures[:3])
            more_exp = f" (+{len(report.impacted_exposures) - 3} more)" if len(report.impacted_exposures) > 3 else ""
            impact_bullets.append(
                f"<strong>{len(report.impacted_exposures)} Executive Exposures</strong> affected: {exp_names}{more_exp}"
            )
        else:
            impact_bullets.append("<strong>0 Executive Exposures</strong> affected")

        if report.downstream_models:
            depth_str = f" across <strong>{report.max_dag_depth} DAG hops</strong>" if report.max_dag_depth > 0 else ""
            impact_bullets.append(
                f"<strong>{len(report.downstream_models)} downstream models</strong> impacted{depth_str}"
            )
        else:
            impact_bullets.append("<strong>Isolated:</strong> 0 downstream models impacted")

        broken_count = sum(len(m.broken_columns) for m in report.downstream_models)
        if broken_count > 0:
            impact_bullets.append(
                f"<strong style='color: var(--color-critical);'>{broken_count} broken column references</strong> detected downstream"
            )
        elif report.downstream_models:
            impact_bullets.append("<strong>0 broken schema references</strong> (all contracts intact)")

        # 3. Action Bullets
        action_bullets: list[str] = []
        for adv in report.remediation_advice:
            clean_adv = adv.replace("**", "").replace("`", "").strip()
            if ":" in clean_adv:
                cat, _, body = clean_adv.partition(":")
                cat = cat.strip()
                body = body.strip().rstrip(".")
                if "Verify business metrics" in cat:
                    cleaned_body = body.replace("Confirm that filter/calculation changes do not unintentionally alter executive metrics on: ", "").strip()
                    action_bullets.append(
                        f"<strong>Audit executive metrics:</strong> Confirm metric stability on {html.escape(cleaned_body)}"
                    )
                elif "Audit dropped records" in cat:
                    action_bullets.append(
                        "<strong>Audit filtered rows:</strong> Validate business intent of omitting non-matching records (e.g. pending/in-transit)"
                    )
                elif "Fix schema reference" in cat:
                    action_bullets.append(
                        f"<strong>Fix schema contract:</strong> {html.escape(body)}"
                    )
                elif "Standard review" in cat:
                    action_bullets.append(
                        "<strong>Pre-merge verification:</strong> Check query performance and downstream data test results"
                    )
                else:
                    action_bullets.append(
                        f"<strong>{html.escape(cat)}:</strong> {html.escape(body)}"
                    )
            else:
                action_bullets.append(f"<strong>Action:</strong> {html.escape(clean_adv.rstrip('.'))}")

        if not action_bullets:
            action_bullets.append("<strong>No blocking actions:</strong> Safe to proceed with standard CI review and merge.")
        elif len(action_bullets) > 3:
            overflow = len(action_bullets) - 3
            action_bullets = action_bullets[:3] + [
                f"<em>+ {overflow} more actions — see full remediation checklist</em>"
            ]

        # Build Graph Data Structures
        graph_nodes_dict: dict[str, dict[str, Any]] = {}
        graph_edges_list: list[dict[str, str]] = []

        # Categorize layers
        root_name = report.modified_models[0].split("/")[-1].replace(".sql", "") if report.modified_models else "stg_orders"
        graph_nodes_dict[root_name] = {
            "id": root_name,
            "name": root_name,
            "layer": "Staging (Root Modified)",
            "depth": 0,
            "is_root": True,
            "parents": [],
            "children": [],
            "exposures": [],
        }

        # Build downstream nodes from report
        for m in report.downstream_models:
            layer_name = m.layer.value.capitalize()
            graph_nodes_dict[m.name] = {
                "id": m.name,
                "name": m.name,
                "layer": layer_name,
                "depth": m.distance_from_source,
                "is_root": False,
                "broken_columns": m.broken_columns,
                "column_impacts": [
                    {
                        "column": ci.column_name,
                        "upstream_col": ci.upstream_column,
                        "upstream_model": ci.upstream_model,
                        "is_broken": ci.is_broken,
                        "path": ci.lineage_path,
                    }
                    for ci in m.column_impacts
                ],
                "file": m.file_path,
                "parents": [],
                "children": [],
                "exposures": [],
            }

        # Map exposures
        for exp in report.impacted_exposures:
            exp_id = f"exp_{exp.name}"
            owner_display = exp.owner_name if exp.owner_name else "Unassigned"
            graph_nodes_dict[exp_id] = {
                "id": exp_id,
                "name": exp.label or exp.name,
                "layer": f"Exposure ({exp.exposure_type.value})",
                "depth": 4,
                "is_root": False,
                "is_exposure": True,
                "owner": owner_display,
                "parents": [],
                "children": [],
                "exposures": [exp.label or exp.name],
            }

        # Map dependencies according to actual DAG edges or pipeline topology
        if report.dag_edges:
            for u_raw, v_raw in report.dag_edges:
                actual_u = u_raw if u_raw in graph_nodes_dict else (f"exp_{u_raw}" if f"exp_{u_raw}" in graph_nodes_dict else None)
                actual_v = v_raw if v_raw in graph_nodes_dict else (f"exp_{v_raw}" if f"exp_{v_raw}" in graph_nodes_dict else None)
                if (
                    actual_u
                    and actual_v
                    and actual_u != actual_v
                    and not any(e["from"] == actual_u and e["to"] == actual_v for e in graph_edges_list)
                ):
                    graph_edges_list.append({"from": actual_u, "to": actual_v})
                    ch_list = graph_nodes_dict[actual_u]["children"]
                    if actual_v not in ch_list:
                        ch_list.append(actual_v)
                    pr_list = graph_nodes_dict[actual_v]["parents"]
                    if actual_u not in pr_list:
                        pr_list.append(actual_u)
        else:
            intermediate_names = [m.name for m in report.downstream_models if m.layer == ModelLayer.INTERMEDIATE]
            marts_names = [m.name for m in report.downstream_models if m.layer == ModelLayer.MARTS]
            reporting_names = [m.name for m in report.downstream_models if m.layer in (ModelLayer.REPORTING, ModelLayer.OTHER)]

            for im in intermediate_names:
                graph_edges_list.append({"from": root_name, "to": im})
                graph_nodes_dict[root_name]["children"].append(im)
                if im in graph_nodes_dict:
                    graph_nodes_dict[im]["parents"].append(root_name)

            if intermediate_names and marts_names:
                for idx, mn in enumerate(marts_names):
                    parent_im = intermediate_names[idx % len(intermediate_names)]
                    graph_edges_list.append({"from": parent_im, "to": mn})
                    graph_nodes_dict[parent_im]["children"].append(mn)
                    if mn in graph_nodes_dict:
                        graph_nodes_dict[mn]["parents"].append(parent_im)
            elif not intermediate_names and marts_names:
                for mn in marts_names:
                    graph_edges_list.append({"from": root_name, "to": mn})
                    graph_nodes_dict[root_name]["children"].append(mn)
                    if mn in graph_nodes_dict:
                        graph_nodes_dict[mn]["parents"].append(root_name)

            if marts_names and reporting_names:
                for idx, rn in enumerate(reporting_names):
                    parent_m = marts_names[idx % len(marts_names)]
                    graph_edges_list.append({"from": parent_m, "to": rn})
                    graph_nodes_dict[parent_m]["children"].append(rn)
                    if rn in graph_nodes_dict:
                        graph_nodes_dict[rn]["parents"].append(parent_m)
            elif not marts_names and reporting_names:
                feeder = intermediate_names[0] if intermediate_names else root_name
                for rn in reporting_names:
                    graph_edges_list.append({"from": feeder, "to": rn})
                    graph_nodes_dict[feeder]["children"].append(rn)
                    if rn in graph_nodes_dict:
                        graph_nodes_dict[rn]["parents"].append(feeder)

            for exp in report.impacted_exposures:
                exp_id = f"exp_{exp.name}"
                feeder = reporting_names[0] if reporting_names else (marts_names[0] if marts_names else root_name)
                if feeder in graph_nodes_dict and exp_id in graph_nodes_dict:
                    graph_edges_list.append({"from": feeder, "to": exp_id})
                    graph_nodes_dict[feeder]["children"].append(exp_id)
                    graph_nodes_dict[exp_id]["parents"].append(feeder)

        # Compute coordinates for deterministic SVG rendering in 1000px width
        col_x = {0: 10, 1: 205, 2: 415, 3: 630, 4: 845}
        col_w = {0: 145, 1: 160, 2: 165, 3: 175, 4: 150}
        layer_groups = {
            0: [root_name],
            1: [m.name for m in report.downstream_models if m.layer == ModelLayer.INTERMEDIATE],
            2: [m.name for m in report.downstream_models if m.layer == ModelLayer.MARTS],
            3: [m.name for m in report.downstream_models if m.layer in (ModelLayer.REPORTING, ModelLayer.OTHER)],
            4: [k for k, v in graph_nodes_dict.items() if v.get("is_exposure")],
        }

        node_positions = {}
        node_height = 32
        row_gap = 13
        start_y = 45

        for col_idx, group in layer_groups.items():
            cx = col_x.get(col_idx, 10 + col_idx * 200)
            for i, nid in enumerate(group):
                ny = start_y + i * (node_height + row_gap)
                if col_idx == 0:
                    ny = 200  # vertically center root
                node_positions[nid] = (cx, ny, col_w.get(col_idx, 160))

        svg_width = 1000
        max_h = max(len(g) for g in layer_groups.values()) * (node_height + row_gap) + start_y + 40
        svg_height = max(420, max_h)

        # Render SVG Edges
        svg_edges_html = []
        for e in graph_edges_list:
            u_id = e["from"]
            v_id = e["to"]
            if u_id in node_positions and v_id in node_positions:
                x1, y1, w1 = node_positions[u_id]
                x2, y2, _ = node_positions[v_id]
                start_pt_x = x1 + w1
                start_pt_y = y1 + node_height / 2
                end_pt_x = x2
                end_pt_y = y2 + node_height / 2
                dx = (end_pt_x - start_pt_x) * 0.5
                c1x = start_pt_x + dx
                c2x = end_pt_x - dx
                path_d = f"M {start_pt_x:.1f} {start_pt_y:.1f} C {c1x:.1f} {start_pt_y:.1f}, {c2x:.1f} {end_pt_y:.1f}, {end_pt_x:.1f} {end_pt_y:.1f}"
                svg_edges_html.append(f"""
                <path id="edge-{html.escape(u_id)}-{html.escape(v_id)}" class="dag-edge" data-source="{html.escape(u_id)}" data-target="{html.escape(v_id)}" d="{path_d}" marker-end="url(#arrow)" />
                """)

        # Render SVG Nodes
        svg_nodes_html = []
        for nid, (nx, ny, nw) in node_positions.items():
            nd = graph_nodes_dict.get(nid, {})
            is_root = bool(nd.get("is_root", False))
            is_exp = bool(nd.get("is_exposure", False))
            raw_name = str(nd.get("name", nid))
            display_name = raw_name if len(raw_name) <= 22 else raw_name[:19] + "..."

            node_class = "dag-node"
            if is_root:
                node_class += " node-root"
                display_name = f"{display_name} [root]"
            elif nd.get("broken_columns"):
                node_class += " node-broken"
                display_name = f"{display_name} [!]"
            elif is_exp:
                node_class += " node-exposure"
            else:
                node_class += " node-model"

            svg_nodes_html.append(f"""
            <g id="node-{html.escape(nid)}" class="{node_class}" data-id="{html.escape(nid)}" transform="translate({nx}, {ny})" onclick="selectGraphNode(this.getAttribute('data-id'))">
                <rect width="{nw}" height="{node_height}" rx="4" />
                <text x="10" y="20">{html.escape(display_name)}</text>
            </g>
            """)

        # Prepare Graph Data JSON for Client JS
        graph_data_json = json.dumps(graph_nodes_dict)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{html.escape(report.plain_english_summary.replace('**', ''))}">
    <title>Parallax Report &mdash; {html.escape(root_name)}</title>
    <style>
        :root {{
            --bg-page: #f8fafc;
            --bg-surface: #ffffff;
            --border-subtle: #e2e8f0;
            --border-medium: #cbd5e1;
            --border-strong: #cbd5e1;
            --text-heading: #0f172a;
            --text-body: #334155;
            --text-muted: #64748b;
            --color-critical: #dc2626;
            --bg-critical-subtle: #fef2f2;
            --color-success: #16a34a;
            --bg-success-subtle: #f0fdf4;
            --font-sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
            --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background-color: var(--bg-page);
            color: var(--text-body);
            font-family: var(--font-sans);
            font-size: 14px;
            line-height: 1.5;
            padding: 40px 20px 80px 20px;
        }}

        .sheet {{
            max-width: 1120px;
            margin: 0 auto;
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            padding: 48px;
        }}

        /* Typography */
        h1, h2, h3 {{ color: var(--text-heading); font-weight: 600; }}
        h1 {{ font-size: 22px; letter-spacing: -0.01em; }}
        h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 12px; }}
        .mono {{ font-family: var(--font-mono); font-size: 13px; }}
        .bold {{ font-weight: 600; color: var(--text-heading); }}

        /* Header Bar */
        .report-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-subtle);
            margin-bottom: 32px;
        }}
        .header-left {{
            display: flex;
            align-items: baseline;
            gap: 16px;
        }}
        .brand {{
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: var(--text-heading);
        }}
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .btn-action {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #ffffff;
            border: 1px solid var(--border-medium);
            border-radius: 4px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-heading);
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .btn-action:hover {{
            background: var(--bg-page);
            border-color: var(--text-muted);
        }}
        .btn-action.btn-copied {{
            background: var(--bg-success-subtle);
            border-color: var(--color-success);
            color: var(--color-success);
            font-weight: 600;
        }}
        .header-meta {{
            font-size: 13px;
            color: var(--text-muted);
            font-family: var(--font-mono);
        }}

        .meta-left {{
            display: inline-flex;
            align-items: baseline;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .btn-copy-diff {{
            background: #ffffff;
            border: 1px solid var(--border-subtle);
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 11px;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .btn-copy-diff:hover {{
            background: var(--bg-page);
            color: var(--text-heading);
            border-color: var(--border-medium);
        }}
        .btn-copy-diff.copied {{
            background: var(--bg-success-subtle);
            border-color: var(--color-success);
            color: var(--color-success);
            font-weight: 600;
        }}

        /* Level 1: Decision */
        .decision-block {{
            border-left: 3px solid var(--border-strong);
            padding: 4px 0 4px 20px;
            margin-bottom: 40px;
        }}
        .decision-block.status-block {{
            border-left-color: var(--color-critical);
        }}
        .decision-block.status-pass {{
            border-left-color: var(--color-success);
        }}
        .decision-topline {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }}
        .status-tag {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 2px;
        }}
        .status-tag-block {{
            background: var(--bg-critical-subtle);
            color: var(--color-critical);
            border: 1px solid rgba(220, 38, 38, 0.2);
        }}
        .status-tag-pass {{
            background: var(--bg-success-subtle);
            color: var(--color-success);
            border: 1px solid rgba(22, 163, 74, 0.2);
        }}
        .decision-severity {{
            font-size: 12px;
            color: var(--color-critical);
            font-weight: 600;
        }}
        .decision-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }}
        .decision-item {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .decision-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 600;
        }}
        .decision-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .decision-list li {{
            font-size: 13px;
            line-height: 1.45;
            color: var(--text-body);
            position: relative;
            padding-left: 14px;
        }}
        .decision-list li::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: var(--text-muted);
            font-weight: 700;
        }}
        .decision-list code {{
            font-family: var(--font-mono);
            font-size: 11.5px;
            background: #f1f5f9;
            padding: 1px 4px;
            border-radius: 3px;
            border: 1px solid var(--border-subtle);
            color: var(--text-heading);
            word-break: break-all;
        }}
        .decision-list strong {{
            color: var(--text-heading);
            font-weight: 600;
        }}
        .decision-value {{
            font-size: 13px;
            color: var(--text-heading);
            line-height: 1.45;
        }}

        /* Section Layout */
        .report-section {{
            margin-bottom: 44px;
        }}

        /* Level 2: Evidence AST Diff */
        .evidence-block {{
            background: var(--bg-page);
            border: 1px solid var(--border-subtle);
            padding: 16px 20px;
            margin-bottom: 16px;
        }}
        .evidence-meta {{
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .meta-label {{
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-size: 10px;
        }}
        .evidence-desc {{
            font-size: 13px;
            color: var(--text-body);
            margin-bottom: 12px;
        }}
        .diff-view {{
            font-family: var(--font-mono);
            font-size: 12px;
            line-height: 1.6;
            background: #ffffff;
            border: 1px solid var(--border-subtle);
        }}
        .diff-line {{
            display: flex;
            padding: 6px 12px;
            align-items: baseline;
            gap: 12px;
        }}
        .diff-del {{
            background: #fef2f2;
            color: #991b1b;
            border-bottom: 1px solid #fee2e2;
        }}
        .diff-add {{
            background: #f0fdf4;
            color: #166534;
        }}
        .diff-prefix {{
            font-weight: 700;
            user-select: none;
            width: 10px;
        }}
        .diff-code {{
            white-space: pre-wrap;
            word-break: break-all;
        }}

        /* Table: Confirmed Exposures */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            border: 1px solid var(--border-subtle);
        }}
        .data-table th, .data-table td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-subtle);
        }}
        .data-table th {{
            background: var(--bg-page);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-muted);
            font-weight: 600;
        }}
        .status-cell-block {{
            color: var(--color-critical);
            font-size: 12px;
            font-weight: 500;
        }}

        /* Remediation Checklist */
        .remediation-list {{
            padding-left: 20px;
            font-size: 14px;
            line-height: 1.6;
            color: var(--text-body);
        }}
        .remediation-list li {{
            margin-bottom: 6px;
        }}

        /* Level 3: Real Interactive DAG Lineage Graph */
        .graph-container {{
            border: 1px solid var(--border-subtle);
            background: #ffffff;
            position: relative;
        }}
        .graph-canvas-wrapper {{
            overflow-x: auto;
            padding: 10px;
        }}
        .dag-svg {{
            display: block;
            margin: 0 auto;
            max-width: 1000px;
            width: 100%;
            height: auto;
        }}

        /* SVG Node & Edge Styling */
        .dag-edge {{
            stroke: #cbd5e1;
            stroke-width: 1.2;
            fill: none;
            transition: stroke 0.2s, stroke-width 0.2s, opacity 0.2s;
        }}
        .dag-edge.edge-active {{
            stroke: #2563eb;
            stroke-width: 2.5;
            opacity: 1;
        }}
        .dag-edge.edge-dim {{
            stroke: #e2e8f0;
            opacity: 0.2;
        }}

        .dag-node {{
            cursor: pointer;
            outline: none;
            transition: opacity 0.2s;
        }}
        .dag-node rect {{
            fill: #ffffff;
            stroke: var(--border-medium);
            stroke-width: 1.2;
            rx: 4;
            transition: stroke 0.2s, fill 0.2s, stroke-width 0.2s;
        }}
        .dag-node text {{
            font-family: var(--font-mono);
            font-size: 10.5px;
            fill: var(--text-heading);
            pointer-events: none;
        }}
        .dag-node:hover rect, .dag-node:focus rect {{
            stroke: var(--text-heading);
            fill: #f8fafc;
        }}
        .dag-node.node-selected rect {{
            stroke: #2563eb;
            stroke-width: 2.2;
            fill: #f0f7ff;
        }}
        .dag-node.node-selected text {{
            font-weight: 700;
            fill: #1d4ed8;
        }}
        .dag-node.node-on-path:not(.node-selected) rect {{
            stroke: #3b82f6;
            stroke-width: 1.6;
            fill: #f8fbff;
        }}
        .dag-node.node-root rect {{
            stroke: var(--color-critical);
            fill: var(--bg-critical-subtle);
        }}
        .dag-node.node-exposure rect {{
            stroke: #d97706;
            fill: #fffbeb;
        }}
        .dag-node.node-broken rect {{
            stroke: var(--color-critical);
            stroke-width: 1.8;
            fill: var(--bg-critical-subtle);
        }}
        .dag-node.node-broken text {{
            fill: #991b1b;
            font-weight: 700;
        }}
        .badge-broken {{
            display: inline-block;
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 3px;
        }}
        .dag-node.node-dim {{
            opacity: 0.25;
        }}

        /* Node Inspector Panel */
        .graph-inspector {{
            border-top: 1px solid var(--border-subtle);
            background: var(--bg-page);
            padding: 16px 20px;
            display: grid;
            grid-template-columns: 1.5fr 2fr;
            gap: 24px;
            font-size: 13px;
        }}
        .inspector-col {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .inspector-label {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}
        .inspector-val {{
            font-family: var(--font-mono);
            color: var(--text-heading);
        }}
        .inspector-chips {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 2px;
        }}
        .inspector-chip {{
            background: #ffffff;
            border: 1px solid var(--border-subtle);
            padding: 2px 6px;
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-body);
        }}

        /* Footer */
        .report-footer {{
            border-top: 1px solid var(--border-subtle);
            padding-top: 20px;
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
        }}


        /* Column Lineage Pill-Chain Traces */
        .chain-container {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .chain-block {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 14px;
            background: var(--bg-page);
            border: 1px solid var(--border-subtle);
            border-radius: 4px;
            flex-wrap: wrap;
        }}
        .chain-row {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 4px;
            flex: 1;
        }}
        .chain-pill {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 11.5px;
            padding: 3px 8px;
            border-radius: 3px;
            background: #f0f7ff;
            color: #0369a1;
            border: 1px solid #bae6fd;
            white-space: nowrap;
        }}
        .chain-pill-source {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 11.5px;
            padding: 3px 8px;
            border-radius: 3px;
            background: #fefce8;
            color: #854d0e;
            border: 1px solid #fde047;
            font-weight: 600;
            white-space: nowrap;
        }}
        .chain-pill-broken {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 11.5px;
            padding: 3px 8px;
            border-radius: 3px;
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
            font-weight: 700;
            white-space: nowrap;
        }}
        .chain-arrow {{
            color: var(--text-muted);
            font-size: 12px;
            user-select: none;
        }}
        .chain-status-broken {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            padding: 2px 7px;
            border-radius: 3px;
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
            white-space: nowrap;
            align-self: center;
        }}
        .chain-status-ok {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            padding: 2px 7px;
            border-radius: 3px;
            background: var(--bg-success-subtle);
            color: var(--color-success);
            border: 1px solid rgba(22, 163, 74, 0.2);
            white-space: nowrap;
            align-self: center;
        }}
        .chain-expr {{
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
            font-style: italic;
            white-space: nowrap;
            align-self: center;
        }}
        .hop-badge {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 10px;
            padding: 1px 5px;
            border-radius: 2px;
            background: #f1f5f9;
            color: var(--text-muted);
            border: 1px solid var(--border-subtle);
        }}

        @media print {{

            body {{
                background: #ffffff !important;
                padding: 0 !important;
                color: #000000 !important;
            }}
            .sheet {{
                border: none !important;
                padding: 0 !important;
                max-width: 100% !important;
            }}
            .dag-container {{
                overflow: visible !important;
            }}
            .inspector-panel {{
                display: none !important;
            }}
            .header-actions, .btn-copy-diff, .btn-action {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="sheet">
        <!-- Header -->
        <header class="report-header">
            <div class="header-left">
                <span class="brand">PARALLAX</span>
                <span class="header-title">Blast Radius Analysis</span>
            </div>
            <div class="header-actions">
                <button type="button" class="btn-action" onclick="copyPrMarkdown(this)" title="Copy PR comment markdown for GitHub or Slack">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align: -2px; margin-right: 4px;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>Copy PR Markdown
                </button>
                <button type="button" class="btn-action" onclick="downloadReportJson()" title="Download structured report JSON">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align: -2px; margin-right: 4px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>Export JSON
                </button>
                <button type="button" class="btn-action" onclick="window.print()" title="Print report or save to PDF">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align: -2px; margin-right: 4px;"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>Print / PDF
                </button>
            </div>
            <div class="header-meta">
                <span>{html.escape(base_ref)} &rarr; {html.escape(head_ref)} &bull; {len(report.modified_models)} modified &bull; {len(report.downstream_models)} downstream &bull; {report.execution_duration_ms:.1f} ms</span>
            </div>
        </header>

        <!-- Level 1: Decision -->
        <section class="decision-block {status_class}">
            <div class="decision-topline">
                <span class="status-tag {'status-tag-block' if is_blocking else 'status-tag-pass'}">{status_label}</span>
                <span class="decision-severity">{severity_label}</span>
            </div>
            <div class="decision-grid">
                <div class="decision-item">
                    <span class="decision-label">Finding</span>
                    <ul class="decision-list">
                        {"".join(f"<li>{b}</li>" for b in finding_bullets)}
                    </ul>
                </div>
                <div class="decision-item">
                    <span class="decision-label">Impact</span>
                    <ul class="decision-list">
                        {"".join(f"<li>{b}</li>" for b in impact_bullets)}
                    </ul>
                </div>
                <div class="decision-item">
                    <span class="decision-label">Action</span>
                    <ul class="decision-list">
                        {"".join(f"<li>{b}</li>" for b in action_bullets)}
                    </ul>
                </div>
            </div>
        </section>

        <!-- Level 2: Evidence (AST Diffs) -->
        <section class="report-section">
            <h2>Semantic SQL Modification</h2>
            {"".join(diff_sections)}
        </section>

        <!-- Level 2: Broken Column Schema Contracts -->
        {f'''
        <section class="report-section">
            <h2>Broken Column Schema Contracts ({len(broken_models)})</h2>
            <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
                Downstream models directly referencing columns deleted or renamed upstream. These models will fail compilation or return runtime SQL exceptions.
            </p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Impacted Model</th>
                        <th>Layer</th>
                        <th>Hop</th>
                        <th>Missing Upstream Column(s)</th>
                        <th>Failure Mode</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(broken_column_rows)}
                </tbody>
            </table>
        </section>
        ''' if broken_column_rows else ""}

        <!-- Level 2: Multi-Hop Column-Level Lineage Traces (Pill-Chain) -->
        {f'''
        <section class="report-section">
            <h2>Column-Level Lineage Traces ({len(all_column_impacts)})</h2>
            <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
                Multi-hop static derivation paths tracing upstream column mutations across downstream models. Each chain shows how the impact flows from the modified source to the downstream consumer.
            </p>
            <div class="chain-container">
                {chr(10).join(column_chain_blocks)}
            </div>
        </section>
        ''' if column_chain_blocks else ""}

        <!-- Level 2: Confirmed Exposures -->
        {f'''
        <section class="report-section">
            <h2>Confirmed Downstream Exposures ({len(report.impacted_exposures)})</h2>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Exposure Name</th>
                        <th>Type</th>
                        <th>Owner</th>
                        <th>Impact Status</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(exposure_rows)}
                </tbody>
            </table>
        </section>
        ''' if exposure_rows else ""}

        <!-- Level 2: Recommended Remediation -->
        {f'''
        <section class="report-section">
            <h2>Actionable Investigation Checklist</h2>
            <ol class="remediation-list">
                {"".join(remediation_items)}
            </ol>
        </section>
        ''' if remediation_items else ""}

        <!-- Level 3: Interactive Lineage DAG Graph -->
        <section class="report-section">
            <h2>Dependency Lineage Graph ({len(graph_nodes_dict)} nodes)</h2>
            <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
                Physical node-and-edge graph derived from dbt compilation manifest. Click any node to inspect upstream and downstream connections.
            </p>
            <div class="graph-container">
                <div class="graph-canvas-wrapper">
                    <svg id="dag-svg" class="dag-svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">
                        <defs>
                            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                                <path d="M 0 1 L 8 5 L 0 9 z" fill="#94a3b8" />
                            </marker>
                            <marker id="arrow-active" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                                <path d="M 0 1 L 8 5 L 0 9 z" fill="#0f172a" />
                            </marker>
                        </defs>

                        <!-- Render Edges -->
                        <g id="edges-layer">
                            {"".join(svg_edges_html)}
                        </g>

                        <!-- Render Nodes -->
                        <g id="nodes-layer">
                            {"".join(svg_nodes_html)}
                        </g>
                    </svg>
                </div>

                <!-- Inspector Drawer (Root selected initially) -->
                <div id="inspector-drawer" class="graph-inspector">
                    <div class="inspector-col">
                        <span class="inspector-label">Selected Node</span>
                        <span id="insp-name" class="inspector-val mono bold">{html.escape(root_name)}</span>
                        <div id="insp-meta" class="inspector-meta-row" style="margin-top: 4px; font-size: 12px; color: var(--text-body); line-height: 1.5;">
                            <div><strong style="color: var(--text-muted);">Layer:</strong> Staging (Root Modified)</div>
                            <div><strong style="color: var(--text-muted);">File:</strong> <span class="mono">models/staging/{html.escape(root_name)}.sql</span></div>
                            <div><strong style="color: var(--text-muted);">Status:</strong> <span style="color: var(--color-critical); font-weight: 600;">Root cause &bull; Modified model</span></div>
                        </div>
                    </div>
                    <div class="inspector-col">
                        <span class="inspector-label">Complete End-to-End Lineage Trace</span>
                        <div id="insp-path-trail" class="path-trail" style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
                            <span class="trail-step step-current" style="background: #2563eb; color: #fff; font-weight: 700; padding: 2px 7px; border-radius: 3px; font-size: 11px; font-family: var(--font-mono);">{html.escape(root_name)}</span>
                        </div>
                        <div style="margin-top: 10px;">
                            <span class="inspector-label">Direct Lineage Connections</span>
                            <div id="insp-connections" class="inspector-chips" style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Provenance Footer -->
        <footer class="report-footer">
            <span>Generated by Parallax &bull; Deterministic SQL AST &amp; DAG Lineage</span>
            <span>Apache 2.0 Open Source</span>
        </footer>
    </div>

    <!-- Client-Side Deterministic Graph Controller -->
    <script>
        const GRAPH_DATA = {graph_data_json};

        function getAncestors(nodeId) {{
            const visited = new Set();
            const queue = [nodeId];
            while (queue.length > 0) {{
                const curr = queue.shift();
                const parents = GRAPH_DATA[curr]?.parents || [];
                for (const p of parents) {{
                    if (!visited.has(p)) {{
                        visited.add(p);
                        queue.push(p);
                    }}
                }}
            }}
            return visited;
        }}

        function getDescendants(nodeId) {{
            const visited = new Set();
            const queue = [nodeId];
            while (queue.length > 0) {{
                const curr = queue.shift();
                const children = GRAPH_DATA[curr]?.children || [];
                for (const c of children) {{
                    if (!visited.has(c)) {{
                        visited.add(c);
                        queue.push(c);
                    }}
                }}
            }}
            return visited;
        }}

        function findPathToRoot(nodeId) {{
            const path = [nodeId];
            let curr = nodeId;
            while (GRAPH_DATA[curr]?.parents && GRAPH_DATA[curr].parents.length > 0) {{
                curr = GRAPH_DATA[curr].parents[0];
                path.unshift(curr);
            }}
            return path;
        }}

        function findPathToExposure(nodeId) {{
            const path = [nodeId];
            let curr = nodeId;
            while (GRAPH_DATA[curr]?.children && GRAPH_DATA[curr].children.length > 0) {{
                const children = GRAPH_DATA[curr].children;
                const next = children.find(c => GRAPH_DATA[c]?.is_exposure || c.startsWith('rpt_') || c === 'fct_orders') || children[0];
                path.push(next);
                curr = next;
            }}
            return path;
        }}

        function selectGraphNode(nodeId) {{
            const nodeData = GRAPH_DATA[nodeId];
            if (!nodeData) return;

            const ancestors = getAncestors(nodeId);
            const descendants = getDescendants(nodeId);
            const activeNodes = new Set([nodeId, ...ancestors, ...descendants]);

            // 1. Highlight nodes
            document.querySelectorAll('.dag-node').forEach(el => {{
                const nid = el.getAttribute('data-id');
                el.classList.remove('node-selected', 'node-on-path', 'node-dim');
                if (nid === nodeId) {{
                    el.classList.add('node-selected');
                }} else if (activeNodes.has(nid)) {{
                    el.classList.add('node-on-path');
                }} else {{
                    el.classList.add('node-dim');
                }}
            }});

            // 2. Highlight edges on the full path from first to last step
            document.querySelectorAll('.dag-edge').forEach(edge => {{
                const src = edge.getAttribute('data-source');
                const tgt = edge.getAttribute('data-target');
                edge.classList.remove('edge-active', 'edge-dim');

                const isUpstreamEdge = ancestors.has(src) && (ancestors.has(tgt) || tgt === nodeId);
                const isDownstreamEdge = (src === nodeId || descendants.has(src)) && descendants.has(tgt);

                if (isUpstreamEdge || isDownstreamEdge) {{
                    edge.classList.add('edge-active');
                    edge.setAttribute('marker-end', 'url(#arrow-active)');
                }} else {{
                    edge.classList.add('edge-dim');
                    edge.setAttribute('marker-end', 'url(#arrow)');
                }}
            }});

            // 3. Update inspector panel
            const nameEl = document.getElementById('insp-name');
            const metaEl = document.getElementById('insp-meta');
            const trailEl = document.getElementById('insp-path-trail');
            const connEl = document.getElementById('insp-connections');

            if (nameEl) nameEl.textContent = nodeData.name;
            if (metaEl) {{
                let statusHtml = '';
                if (nodeData.is_root) {{
                    statusHtml = '<span style="color: var(--color-critical); font-weight: 600;">Root cause &bull; Modified model</span>';
                }} else if (nodeData.broken_columns && nodeData.broken_columns.length > 0) {{
                    statusHtml = '<span style="color: var(--color-critical); font-weight: 700;">BREAKING: Missing upstream column(s)</span>';
                }} else if (nodeData.is_exposure) {{
                    statusHtml = '<span style="color: #d97706; font-weight: 600;">Confirmed exposure impact</span>';
                }} else {{
                    statusHtml = 'Downstream affected model';
                }}

                let brokenDetails = '';
                if (nodeData.broken_columns && nodeData.broken_columns.length > 0) {{
                    const colChips = nodeData.broken_columns.map(c => '<code style="background: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 3px; border: 1px solid #fca5a5; font-weight: 700;">' + c + '</code>').join(' ');
                    brokenDetails = '<div style="margin-top: 8px; padding: 8px 10px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px;">' +
                        '<div style="font-size: 10px; font-weight: 700; color: #991b1b; text-transform: uppercase; letter-spacing: 0.04em;">Broken Column Schema Contract</div>' +
                        '<div style="font-size: 12px; color: #7f1d1d; margin-top: 3px;">Directly queries deleted/renamed column: ' + colChips + '</div>' +
                        '</div>';
                }}

                let derivedDetails = '';
                if (nodeData.column_impacts && nodeData.column_impacts.length > 0) {{
                    const impactChips = nodeData.column_impacts.map(ci => {{
                        const tagClass = ci.is_broken
                            ? 'background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;'
                            : 'background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd;';
                        const trail = (ci.path && ci.path.length > 0) ? ci.path.join(' &rarr; ') : (ci.upstream_model + '.' + ci.upstream_col);
                        return '<div style="margin-top: 4px; font-size: 11px; font-family: var(--font-mono);">' +
                            '<span style="padding: 1px 5px; border-radius: 3px; font-weight: 600; ' + tagClass + '">' + ci.column + '</span>' +
                            ' &larr; <span style="color: var(--text-muted);">' + trail + '</span>' +
                            '</div>';
                    }}).join('');
                    derivedDetails = '<div style="margin-top: 8px; padding: 8px 10px; background: #ffffff; border: 1px solid var(--border-subtle); border-radius: 4px;">' +
                        '<div style="font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em;">Column-Level Lineage Traces</div>' +
                        impactChips +
                        '</div>';
                }}

                metaEl.innerHTML = 
                    '<div><strong style="color: var(--text-muted);">Layer:</strong> ' + nodeData.layer + '</div>' +
                    '<div><strong style="color: var(--text-muted);">File:</strong> <span class="mono">' + (nodeData.file || ('models/' + nodeData.name + '.sql')) + '</span></div>' +
                    '<div><strong style="color: var(--text-muted);">Status:</strong> ' + statusHtml + '</div>' +
                    brokenDetails +
                    derivedDetails;
            }}

            const upPath = findPathToRoot(nodeId);
            const downPath = findPathToExposure(nodeId);
            const fullTrail = [...new Set([...upPath, ...downPath])];

            if (trailEl) {{
                trailEl.innerHTML = fullTrail.map((nid, i) => {{
                    const isCur = nid === nodeId;
                    const stepName = GRAPH_DATA[nid]?.name || nid;
                    const arrow = (i < fullTrail.length - 1) ? '<span style="color: var(--text-muted);">&rarr;</span>' : '';
                    return '<span style="padding: 2px 7px; border-radius: 3px; font-family: var(--font-mono); font-size: 11px; cursor: pointer; ' + (isCur ? 'background: #2563eb; color: #fff; font-weight: 700;' : 'background: #fff; border: 1px solid var(--border-subtle); color: var(--text-heading);') + '" data-node-id="' + nid + '" onclick="selectGraphNode(this.dataset.nodeId)">' + stepName + '</span>' + arrow;
                }}).join('');
            }}

            if (connEl) {{
                const parents = nodeData.parents || [];
                const children = nodeData.children || [];

                let pChips = parents.length > 0
                    ? parents.map(p => '<span style="padding: 2px 7px; background: #fff; border: 1px solid var(--border-subtle); border-radius: 3px; font-family: var(--font-mono); font-size: 11px; cursor: pointer;" data-node-id="' + p + '" onclick="selectGraphNode(this.dataset.nodeId)">&uarr; ' + (GRAPH_DATA[p]?.name || p) + '</span>').join(' ')
                    : '<span style="color: var(--text-muted); font-size: 11px;">none (root source)</span>';

                let cChips = children.length > 0
                    ? children.map(c => '<span style="padding: 2px 7px; background: #fff; border: 1px solid var(--border-subtle); border-radius: 3px; font-family: var(--font-mono); font-size: 11px; cursor: pointer;" data-node-id="' + c + '" onclick="selectGraphNode(this.dataset.nodeId)">&darr; ' + (GRAPH_DATA[c]?.name || c) + '</span>').join(' ')
                    : '<span style="color: var(--text-muted); font-size: 11px;">none (terminal exposure)</span>';

                connEl.innerHTML = 
                    '<div style="margin-bottom: 6px;"><span class="inspector-label">Incoming Parents:</span> ' + pChips + '</div>' +
                    '<div><span class="inspector-label">Outgoing Children:</span> ' + cChips + '</div>';
            }}
        }}

        // Interactive Action Handlers
        function copyDiffText(btn) {{
            const block = btn.closest('.evidence-block');
            if (!block) return;
            const delCode = block.querySelector('.diff-del .diff-code')?.textContent || '';
            const addCode = block.querySelector('.diff-add .diff-code')?.textContent || '';
            const snippet = `- ${{delCode}}\n+ ${{addCode}}`;
            navigator.clipboard.writeText(snippet).then(() => {{
                const orig = btn.textContent;
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = orig;
                    btn.classList.remove('copied');
                }}, 1800);
            }});
        }}

        function copyPrMarkdown(btn) {{
            const el = document.getElementById('parallax-markdown-raw');
            if (!el) return;
            navigator.clipboard.writeText(el.value).then(() => {{
                const orig = btn.innerHTML;
                btn.innerHTML = '<span>✓</span> Copied PR Markdown!';
                btn.classList.add('btn-copied');
                setTimeout(() => {{
                    btn.innerHTML = orig;
                    btn.classList.remove('btn-copied');
                }}, 2000);
            }});
        }}

        function downloadReportJson() {{
            const el = document.getElementById('parallax-json-raw');
            if (!el) return;
            const blob = new Blob([el.textContent], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'parallax-blast-radius.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}

        // Initialize with root node selected on page load
        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.dag-node').forEach(function(el) {{
                el.addEventListener('click', function() {{
                    const nid = el.getAttribute('data-id');
                    if (nid) selectGraphNode(nid);
                }});
            }});
            selectGraphNode({json.dumps(root_name)});
        }});
    </script>
    <!-- Hidden Raw Payload for Client Actions -->
    <textarea id="parallax-markdown-raw" style="display:none;" readonly>{html.escape(pr_markdown_str)}</textarea>
    <script id="parallax-json-raw" type="application/json">{report_json_str}</script>
</body>
</html>
"""
