"""Rich terminal UI formatter for Parallax CLI."""

import io

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from parallax.core.models import BlastRadiusReport, ModelLayer, RiskSeverity


class TerminalFormatter:
    """Renders rich ANSI terminal reports for local developer inspection."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(
        self, report: BlastRadiusReport, base_ref: str = "main", head_ref: str = "HEAD"
    ) -> None:
        """Render the full visual report to the console."""
        # Header banner
        header_text = Text()
        header_text.append("PARALLAX ", style="bold cyan")
        header_text.append("• Blast Radius & Semantic Drift CI\n", style="dim")
        header_text.append(
            f"Comparing: {base_ref}...{head_ref}  |  Duration: {report.execution_duration_ms:.2f}ms",
            style="dim italic",
        )
        self.console.print(header_text)
        self.console.print()

        # Severity Badge & Summary Panel
        badge_style = {
            RiskSeverity.CRITICAL: "bold white on red",
            RiskSeverity.HIGH: "bold black on yellow",
            RiskSeverity.MEDIUM: "bold white on blue",
            RiskSeverity.LOW: "bold white on green",
            RiskSeverity.NEVER: "dim white",
        }.get(report.risk_severity, "bold white on red")

        badge = Text(f" {report.risk_severity.value} RISK ", style=badge_style)
        panel = Panel(
            Text.from_markup(f"{badge.markup}\n\n{report.plain_english_summary}"),
            title="[bold]Impact Assessment[/bold]",
            border_style="red" if report.risk_severity == RiskSeverity.CRITICAL else "cyan",
        )
        self.console.print(panel)
        self.console.print()

        # Metrics Summary Table
        metrics_table = Table(
            title="Blast Radius Metrics", show_header=True, header_style="bold magenta"
        )
        metrics_table.add_column("Metric", style="dim", width=28)
        metrics_table.add_column("Value", style="bold")

        metrics_table.add_row("Modified Models", str(len(report.modified_models)))
        metrics_table.add_row("Impacted Downstream Models", str(len(report.downstream_models)))
        metrics_table.add_row("Impacted BI Exposures", str(len(report.impacted_exposures)))
        metrics_table.add_row("Max Lineage DAG Depth", f"{report.max_dag_depth} layers")

        broken_count = sum(len(m.broken_columns) for m in report.downstream_models)
        broken_style = "bold red" if broken_count > 0 else "green"
        metrics_table.add_row(
            "Breaking Column Mutations", Text(str(broken_count), style=broken_style)
        )

        self.console.print(metrics_table)
        self.console.print()

        # AST Semantic Diffs Table
        all_predicates = [p for d in report.ast_diffs for p in d.predicates]
        all_columns = [c for d in report.ast_diffs for c in d.columns]
        all_joins = [j for d in report.ast_diffs for j in d.structural.join_diffs]

        if all_predicates or all_columns or all_joins:
            diff_table = Table(
                title="AST Semantic Diffs", show_header=True, header_style="bold cyan"
            )
            diff_table.add_column("Model", style="cyan")
            diff_table.add_column("Category", style="magenta")
            diff_table.add_column("Type", style="bold")
            diff_table.add_column("Original", style="red dim")
            diff_table.add_column("New / Altered", style="green bold")

            for d in report.ast_diffs:
                for p in d.predicates:
                    diff_table.add_row(
                        d.model_name,
                        p.clause.value,
                        p.diff_type.value,
                        p.old_expression or "-",
                        p.new_expression or "-",
                    )
                for c in d.columns:
                    diff_table.add_row(
                        d.model_name,
                        "COLUMN",
                        c.diff_type.value,
                        c.old_expression or "-",
                        c.new_expression or c.column_name,
                    )
                for j in d.structural.join_diffs:
                    diff_table.add_row(
                        d.model_name,
                        "JOIN",
                        j.diff_type.value,
                        j.old_join_type or "-",
                        j.new_join_type or j.table_name,
                    )

            self.console.print(diff_table)
            self.console.print()

        # Visual Downstream Lineage Tree
        if report.downstream_models or report.impacted_exposures:
            tree_root = Tree(
                f"[bold cyan]Modified Models: {', '.join(report.modified_models)}[/bold cyan]"
            )

            layer_colors = {
                ModelLayer.STAGING: "cyan",
                ModelLayer.INTERMEDIATE: "yellow",
                ModelLayer.MARTS: "magenta",
                ModelLayer.REPORTING: "blue",
                ModelLayer.OTHER: "white",
            }

            for model in report.downstream_models:
                color = layer_colors.get(model.layer, "white")
                branch_label = f"[{color}]{model.name}[/{color}] (layer: {model.layer.value}, depth: {model.distance_from_source})"
                if model.broken_columns:
                    branch_label += (
                        f" [bold red]⚠️ MISSING COLUMN: {', '.join(model.broken_columns)}[/bold red]"
                    )
                tree_root.add(branch_label)

            for exp in report.impacted_exposures:
                exp_label = f"[bold red on black] 📊 EXPOSURE: {exp.label or exp.name} [/bold red on black] ({exp.exposure_type.value})"
                tree_root.add(exp_label)

            self.console.print(
                Panel(tree_root, title="[bold]Downstream Lineage & Blast Radius[/bold]")
            )
            self.console.print()

        # Remediation Advice
        if report.remediation_advice:
            rem_table = Table(title="Recommended Next Steps", show_header=False, box=None)
            rem_table.add_column("Bullet", style="bold yellow", width=3)
            rem_table.add_column("Action")
            for advice in report.remediation_advice:
                rem_table.add_row("•", advice)
            self.console.print(rem_table)
            self.console.print()

    def to_string(
        self, report: BlastRadiusReport, base_ref: str = "main", head_ref: str = "HEAD"
    ) -> str:
        """Render report to ANSI string buffer for testing or piping."""
        buf = io.StringIO()
        mem_console = Console(file=buf, force_terminal=True, width=120)
        old_console = self.console
        self.console = mem_console
        try:
            self.render(report, base_ref, head_ref)
            return buf.getvalue()
        finally:
            self.console = old_console
