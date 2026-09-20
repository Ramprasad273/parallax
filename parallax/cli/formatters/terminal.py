"""Rich terminal UI formatter for Parallax CLI."""

import io
import shutil
from datetime import datetime, timezone

from rich import box
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from parallax.core.models import BlastRadiusReport, ColumnImpact, ModelLayer, RiskSeverity

# Hard cap so the report never stretches beyond a readable line length.
_MAX_WIDTH = 100


def _capped_width() -> int:
    """Return the lesser of the real terminal width and _MAX_WIDTH."""
    return min(shutil.get_terminal_size((80, 24)).columns, _MAX_WIDTH)


# ---------------------------------------------------------------------------
# Design tokens — single source of truth for colours/labels
# ---------------------------------------------------------------------------

_SEVERITY_CONFIG: dict[RiskSeverity, dict[str, str]] = {
    RiskSeverity.CRITICAL: {
        "bar_style": "bold white on red",
        "label": "CRITICAL",
        "rule_style": "red",
        "summary_style": "bold red",
    },
    RiskSeverity.HIGH: {
        "bar_style": "bold black on yellow",
        "label": "HIGH",
        "rule_style": "yellow",
        "summary_style": "bold yellow",
    },
    RiskSeverity.MEDIUM: {
        "bar_style": "bold white on bright_blue",
        "label": "MEDIUM",
        "rule_style": "bright_blue",
        "summary_style": "bold bright_blue",
    },
    RiskSeverity.LOW: {
        "bar_style": "bold white on green",
        "label": "LOW",
        "rule_style": "green",
        "summary_style": "bold green",
    },
    RiskSeverity.NEVER: {
        "bar_style": "dim white on grey30",
        "label": "NONE",
        "rule_style": "grey50",
        "summary_style": "dim white",
    },
}

_LAYER_STYLE: dict[ModelLayer, str] = {
    ModelLayer.STAGING: "cyan",
    ModelLayer.INTERMEDIATE: "yellow",
    ModelLayer.MARTS: "magenta",
    ModelLayer.REPORTING: "blue",
    ModelLayer.OTHER: "white",
}

# Order in which layers are displayed in the downstream table
_LAYER_ORDER = [
    ModelLayer.STAGING,
    ModelLayer.INTERMEDIATE,
    ModelLayer.MARTS,
    ModelLayer.REPORTING,
    ModelLayer.OTHER,
]

# Change-type colour coding — red = data loss, yellow = mutation, green = addition
_CHANGE_STYLES: dict[str, str] = {
    "DROPPED": "bold red",
    "TIGHTENED": "bold yellow",
    "LOOSENED": "bold magenta",
    "MUTATED_OPERATOR": "bold yellow",
    "ADDED": "bold green",
    "RENAMED": "bold cyan",
    "EXPRESSION_ALTERED": "bold yellow",
    "TYPE_CHANGED": "bold yellow",
    "CONDITION_CHANGED": "yellow",
    "JOIN_ADDED": "bold green",
    "JOIN_REMOVED": "bold red",
}


class TerminalFormatter:
    """Renders rich ANSI terminal reports for local developer inspection."""

    def __init__(self, console: Console | None = None) -> None:
        # Always cap width, even when a console is passed in from outside (e.g. demo)
        width = _capped_width()
        if console is not None:
            console._width = width  # override the caller's console width
        self.console = console or Console(width=width)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self, report: BlastRadiusReport, base_ref: str = "main", head_ref: str = "HEAD"
    ) -> None:
        """Render the full structured report to the console."""
        cfg = _SEVERITY_CONFIG.get(report.risk_severity, _SEVERITY_CONFIG[RiskSeverity.CRITICAL])

        self._render_header(report, base_ref, head_ref, cfg)
        self._render_risk_banner(report, cfg)
        self._render_overview(report, cfg)

        self._render_ast_diffs(report)
        self._render_lineage(report)

        if report.remediation_advice:
            self._render_remediation(report)

        self._render_footer(report, cfg)

    def to_string(
        self, report: BlastRadiusReport, base_ref: str = "main", head_ref: str = "HEAD"
    ) -> str:
        """Render report to ANSI string buffer for testing or piping."""
        buf = io.StringIO()
        mem_console = Console(file=buf, force_terminal=True, width=_capped_width())
        old_console = self.console
        self.console = mem_console
        try:
            self.render(report, base_ref, head_ref)
            return buf.getvalue()  # type: ignore[return-value]
        finally:
            self.console = old_console

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    def _render_header(
        self,
        report: BlastRadiusReport,
        base_ref: str,
        head_ref: str,
        cfg: dict[str, str],
    ) -> None:
        """Opening rule with tool identity and run context."""
        self.console.print()
        self.console.print(
            Rule(" PARALLAX  Blast Radius & Semantic Drift ", style=cfg["rule_style"])
        )

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        # Single compact meta line instead of a multi-row grid
        meta_line = Text()
        meta_line.append(f"  {base_ref}", style="white")
        meta_line.append("  >  ", style="dim")
        meta_line.append(f"{head_ref}", style="white")
        meta_line.append(f"    {ts}", style="dim")
        meta_line.append(f"    {report.execution_duration_ms:.2f}ms", style="dim")
        self.console.print(meta_line)
        self.console.print()

    def _render_risk_banner(self, report: BlastRadiusReport, cfg: dict[str, str]) -> None:
        """Dominant panel — the first thing a reviewer reads."""
        label = cfg["label"]
        bar_style = cfg["bar_style"]
        border = cfg["rule_style"]

        # Title badge inside the panel title
        panel_title = Text(f"  {label} RISK  ", style=bar_style)

        # Summary body — strip markdown markers
        raw = report.plain_english_summary.replace("**", "")
        body = Text(raw, style=cfg["summary_style"])

        self.console.print(
            Panel(
                body,
                title=panel_title,
                title_align="left",
                border_style=border,
                padding=(0, 2),
            )
        )
        self.console.print()

    def _render_overview(self, report: BlastRadiusReport, cfg: dict[str, str]) -> None:
        """Key numbers — right-aligned values, dim labels, no clutter."""
        broken_count = sum(len(m.broken_columns) for m in report.downstream_models)
        col_impact_count = sum(len(m.column_impacts) for m in report.downstream_models)

        tbl = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
            show_edge=False,
        )
        tbl.add_column(style="dim", no_wrap=True, min_width=30)
        tbl.add_column(style="bold white", no_wrap=True, justify="right", min_width=8)

        tbl.add_row("Modified models", str(len(report.modified_models)))
        tbl.add_row("Downstream models impacted", str(len(report.downstream_models)))
        tbl.add_row("BI exposures affected", str(len(report.impacted_exposures)))
        tbl.add_row("Longest lineage path (hops)", str(report.max_dag_depth))

        if broken_count > 0:
            tbl.add_row(
                "Breaking column references",
                Text(str(broken_count), style="bold red"),
            )
        else:
            tbl.add_row(
                "Breaking column references",
                Text("none", style="dim green"),
            )

        if col_impact_count > 0:
            tbl.add_row(
                "Column-level lineage traces",
                Text(str(col_impact_count), style="bold cyan"),
            )

        self.console.print(
            Panel(
                tbl,
                title="[dim]Overview[/dim]",
                title_align="left",
                border_style="grey30",
                padding=(0, 1),
            )
        )
        self.console.print()

    def _render_ast_diffs(self, report: BlastRadiusReport) -> None:
        """
        Semantic changes — the most diagnostic section.
        Each change is a bordered panel so expressions never truncate.
        """
        all_rows = (
            [
                (
                    d.model_name,
                    p.clause.value,
                    p.diff_type.value,
                    p.old_expression or "-",
                    p.new_expression or "-",
                    p.explanation,
                )
                for d in report.ast_diffs
                for p in d.predicates
            ]
            + [
                (
                    d.model_name,
                    "COLUMN",
                    c.diff_type.value,
                    c.old_expression or "-",
                    c.new_expression or c.column_name,
                    c.explanation,
                )
                for d in report.ast_diffs
                for c in d.columns
            ]
            + [
                (
                    d.model_name,
                    "JOIN",
                    j.diff_type.value,
                    j.old_join_type or "-",
                    j.new_join_type or j.table_name,
                    j.explanation,
                )
                for d in report.ast_diffs
                for j in d.structural.join_diffs
            ]
        )

        if not all_rows:
            return

        self.console.print(Rule(" Semantic Changes ", style="grey50"))
        self.console.print()

        for model, category, change_type, before, after, explanation in all_rows:
            change_style = _CHANGE_STYLES.get(change_type.upper(), "white")

            grid = Table.grid(padding=(0, 1))
            grid.add_column(style="dim", no_wrap=True, min_width=8)
            grid.add_column()

            grid.add_row("Model", Text(model, style="cyan bold"))
            grid.add_row("Scope", Text(f"{category}", style="white"))
            grid.add_row("Change", Text(change_type, style=change_style))
            grid.add_row("Before", Text(before, style="red"))
            grid.add_row("After", Text(after, style="green bold"))
            if explanation:
                grid.add_row("Note", Text(explanation, style="dim"))

            self.console.print(
                Panel(
                    grid,
                    border_style="grey30",
                    padding=(0, 2),
                )
            )
            self.console.print()

    def _render_lineage(self, report: BlastRadiusReport) -> None:
        """
        Downstream blast radius — grouped by layer so the reader immediately
        sees how deep and wide the change propagates.
        """
        if not report.downstream_models and not report.impacted_exposures:
            return

        self.console.print(Rule(" Downstream Blast Radius ", style="grey50"))
        self.console.print()

        if report.downstream_models:
            self._render_downstream_models(report)

        if report.impacted_exposures:
            self._render_exposures(report)

    def _render_downstream_models(self, report: BlastRadiusReport) -> None:
        """Group downstream models by layer with inline column lineage traces for broken columns."""
        # Bucket models by layer
        by_layer: dict[ModelLayer, list] = {}
        for m in report.downstream_models:
            by_layer.setdefault(m.layer, []).append(m)

        # Does any model have a breaking column?
        any_broken = any(m.broken_columns for m in report.downstream_models)

        self.console.print(Padding(Text("Downstream Models", style="bold white"), (0, 2)))
        self.console.print()

        for layer in _LAYER_ORDER:
            models = by_layer.get(layer)
            if not models:
                continue

            color = _LAYER_STYLE.get(layer, "white")
            hop = models[0].distance_from_source
            layer_header = Text()
            layer_header.append(f"  {layer.value.upper()}", style=f"bold {color}")
            layer_header.append(
                f"  {len(models)} model{'s' if len(models) > 1 else ''}", style="dim"
            )
            layer_header.append(f"  (hop {hop})", style="dim")
            self.console.print(layer_header)

            for m in sorted(models, key=lambda x: x.name):
                line = Text()
                line.append("    ")
                line.append(m.name, style="white")
                if m.broken_columns:
                    line.append("  ")
                    line.append(
                        f"BREAKING: {', '.join(m.broken_columns)}",
                        style="bold red",
                    )
                elif any_broken:
                    # Only show OK marker when there ARE broken models elsewhere
                    line.append("  ")
                    line.append("ok", style="dim green")

                derived_cols = [
                    ci.column_name
                    for ci in m.column_impacts
                    if not ci.is_broken and ci.column_name not in m.broken_columns
                ]
                if derived_cols:
                    line.append(f"  [derived: {', '.join(derived_cols)}]", style="cyan dim")

                self.console.print(line)

                # --- Inline column-level lineage traces (only for broken columns) ---
                broken_impacts = [ci for ci in m.column_impacts if ci.is_broken]
                for ci in broken_impacts:
                    self._render_column_trace_line(ci)

            self.console.print()

    def _render_column_trace_line(self, ci: ColumnImpact) -> None:
        """Render a single inline column lineage trace under a broken model."""
        # Build the derivation chain string
        if ci.lineage_path and len(ci.lineage_path) >= 2:
            # Format path: a → b → c  (compact)
            chain_parts = ci.lineage_path
            if len(chain_parts) > 5:
                # Ellipsis for very long chains
                chain_parts = chain_parts[:2] + ["…"] + chain_parts[-2:]
            chain_str = " → ".join(chain_parts)
        else:
            chain_str = f"{ci.upstream_model}.{ci.upstream_column}"

        trace_line = Text()
        trace_line.append("         └─ ", style="dim red")
        trace_line.append(ci.column_name, style="bold red")
        trace_line.append("  ←  ", style="dim")
        trace_line.append(chain_str, style="dim")
        trace_line.append("  ", style="")
        trace_line.append("[BROKEN]", style="bold red on grey15")
        self.console.print(trace_line)

    def _render_exposures(self, report: BlastRadiusReport) -> None:
        """BI exposure table — only show URL column if at least one URL exists."""
        has_url = any(e.url for e in report.impacted_exposures)

        self.console.print(Padding(Text("Impacted BI Exposures", style="bold white"), (0, 2)))

        tbl = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold white on grey23",
            show_edge=False,
            padding=(0, 2),
        )
        tbl.add_column("Exposure", style="white", min_width=24)
        tbl.add_column("Type", no_wrap=True, min_width=12)
        tbl.add_column("Owner", style="dim")
        if has_url:
            tbl.add_column("URL", style="dim")

        for exp in report.impacted_exposures:
            row = [
                exp.label or exp.name,
                exp.exposure_type.value,
                exp.owner_name or "-",
            ]
            if has_url:
                row.append(exp.url or "-")
            tbl.add_row(*row)

        self.console.print(tbl)
        self.console.print()

    def _render_remediation(self, report: BlastRadiusReport) -> None:
        """Numbered action items inside a panel — consistent indent on wrap."""
        self.console.print(Rule(" Recommended Actions ", style="grey50"))
        self.console.print()

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold white", no_wrap=True, min_width=3, justify="right")
        grid.add_column()

        for i, advice in enumerate(report.remediation_advice, start=1):
            clean = advice.replace("**", "").replace("`", "")
            grid.add_row(str(i) + ".", Text(clean))

        self.console.print(Padding(grid, (0, 2)))
        self.console.print()

    def _render_footer(self, report: BlastRadiusReport, cfg: dict[str, str]) -> None:
        """Closing rule with unambiguous CI gate status."""
        is_blocking = report.risk_severity in (RiskSeverity.CRITICAL, RiskSeverity.HIGH)
        gate_label = "CI gate: BLOCK" if is_blocking else "CI gate: PASS"
        self.console.print(Rule(f" {gate_label} ", style=cfg["rule_style"]))
        self.console.print(
            Padding(
                Text("github.com/Ramprasad273/parallax", style="dim"),
                (0, 2),
            )
        )
        self.console.print()
