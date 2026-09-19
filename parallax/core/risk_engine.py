"""Risk scoring matrix and deterministic plain-English explainer engine."""

from parallax.core.models import (
    BlastRadiusReport,
    ColumnDiffType,
    ColumnImpact,
    DownstreamNode,
    ExposureNode,
    JoinDiffType,
    ModelASTDiff,
    ModelLayer,
    PredicateDiffType,
    RiskSeverity,
)


class RiskEngine:
    """
    Synthesizes AST diffs, lineage blast radius, and critical path tags into
    an unambiguous Risk Grade (CRITICAL, HIGH, MEDIUM, LOW) and plain-English summary.
    """

    def __init__(self, tier_tags: list[str] | None = None) -> None:
        self.tier_tags = set(tier_tags or ["tier_1", "finance", "executive", "board", "p0"])

    def evaluate(
        self,
        modified_models: list[str],
        ast_diffs: list[ModelASTDiff],
        downstream_models: list[DownstreamNode],
        impacted_exposures: list[ExposureNode],
        max_dag_depth: int,
        execution_duration_ms: float = 0.0,
        dag_edges: list[tuple[str, str]] | None = None,
    ) -> BlastRadiusReport:
        """Generate a full BlastRadiusReport with severity and explanation."""
        edges = dag_edges or []
        has_semantic_changes = any(d.has_semantic_changes for d in ast_diffs)
        if not has_semantic_changes and not downstream_models:
            return BlastRadiusReport(
                modified_models=modified_models,
                ast_diffs=ast_diffs,
                downstream_models=[],
                impacted_exposures=[],
                max_dag_depth=0,
                risk_severity=RiskSeverity.LOW,
                plain_english_summary="**NO RISK:** Purely cosmetic, comments, or non-semantic formatting changes.",
                remediation_advice=[],
                execution_duration_ms=execution_duration_ms,
                dag_edges=edges,
            )

        severity = self._calculate_severity(ast_diffs, downstream_models, impacted_exposures)
        summary = self._generate_summary(severity, ast_diffs, downstream_models, impacted_exposures)
        remediation = self._generate_remediation(
            severity, ast_diffs, downstream_models, impacted_exposures
        )

        # Collect all column lineage paths across downstream models
        column_paths: list[ColumnImpact] = []
        for dm in downstream_models:
            column_paths.extend(dm.column_impacts)

        return BlastRadiusReport(
            modified_models=modified_models,
            ast_diffs=ast_diffs,
            downstream_models=downstream_models,
            impacted_exposures=impacted_exposures,
            max_dag_depth=max_dag_depth,
            risk_severity=severity,
            plain_english_summary=summary,
            remediation_advice=remediation,
            execution_duration_ms=execution_duration_ms,
            dag_edges=edges,
            column_lineage_paths=column_paths,
        )

    def _calculate_severity(
        self,
        ast_diffs: list[ModelASTDiff],
        downstream_models: list[DownstreamNode],
        impacted_exposures: list[ExposureNode],
    ) -> RiskSeverity:
        """Evaluate rules to determine the overall RiskSeverity."""
        # Rule 1: Breaking column changes referenced downstream -> CRITICAL
        if any(bool(m.broken_columns) for m in downstream_models):
            return RiskSeverity.CRITICAL

        # Check if dropped columns exist in upstream models with any downstream consumers
        has_dropped_columns = any(bool(d.dropped_columns) for d in ast_diffs)
        if has_dropped_columns and downstream_models:
            return RiskSeverity.CRITICAL

        has_exposures = len(impacted_exposures) > 0
        has_tier_nodes = any(bool(set(m.tags) & self.tier_tags) for m in downstream_models)

        # Rule 2: Predicate tightened/loosened/mutated upstream of exposures or tier-1 nodes -> CRITICAL
        has_predicate_changes = any(bool(d.predicates) for d in ast_diffs)
        if has_predicate_changes and (has_exposures or has_tier_nodes):
            return RiskSeverity.CRITICAL

        # Rule 3: Join type changed upstream of exposures or tier-1 nodes -> CRITICAL
        has_join_type_changes = any(
            any(j.diff_type == JoinDiffType.TYPE_CHANGED for j in d.structural.join_diffs)
            for d in ast_diffs
        )
        if has_join_type_changes and (has_exposures or has_tier_nodes):
            return RiskSeverity.CRITICAL

        # Rule 4: Join type changed without exposures -> HIGH
        if has_join_type_changes:
            return RiskSeverity.HIGH

        # Rule 5: Predicate change with > 5 downstream models or in a mart model -> HIGH
        has_mart_models = any(m.layer == ModelLayer.MARTS for m in downstream_models)
        if has_predicate_changes and (len(downstream_models) > 5 or has_mart_models):
            return RiskSeverity.HIGH

        # Rule 6: Dropped columns without known downstream consumers -> HIGH
        if has_dropped_columns:
            return RiskSeverity.HIGH

        # Rule 7: Calculation alterations or isolated filter changes -> MEDIUM
        has_calculation_changes = any(
            any(c.diff_type == ColumnDiffType.EXPRESSION_ALTERED for c in d.columns)
            for d in ast_diffs
        )
        if has_calculation_changes or has_predicate_changes:
            return RiskSeverity.MEDIUM

        # Rule 8: Non-breaking additions -> MEDIUM
        has_additions = any(
            any(c.diff_type == ColumnDiffType.ADDED for c in d.columns) for d in ast_diffs
        )
        if has_additions:
            return RiskSeverity.MEDIUM

        return RiskSeverity.LOW

    def _generate_summary(
        self,
        severity: RiskSeverity,
        ast_diffs: list[ModelASTDiff],
        downstream_models: list[DownstreamNode],
        impacted_exposures: list[ExposureNode],
    ) -> str:
        """Synthesize a high-impact plain-English sentence summarizing the impact."""
        prefix = {
            RiskSeverity.CRITICAL: "**CRITICAL RISK:**",
            RiskSeverity.HIGH: "**HIGH RISK:**",
            RiskSeverity.MEDIUM: "**MEDIUM RISK:**",
            RiskSeverity.LOW: "**LOW RISK:**",
        }.get(severity, "**INFO:**")

        # Find the primary mutation
        mutation_desc: list[str] = []
        for d in ast_diffs:
            for p in d.predicates:
                if p.diff_type == PredicateDiffType.TIGHTENED:
                    mutation_desc.append(
                        f"tightened filter `{p.old_expression}` -> `{p.new_expression}` on `{d.model_name}`"
                    )
                elif p.diff_type == PredicateDiffType.DROPPED:
                    mutation_desc.append(
                        f"dropped filter condition `{p.old_expression}` on `{d.model_name}`"
                    )
                elif p.diff_type == PredicateDiffType.MUTATED_OPERATOR:
                    mutation_desc.append(
                        f"mutated filter operator `{p.old_expression}` -> `{p.new_expression}` on `{d.model_name}`"
                    )

            for c in d.columns:
                if c.diff_type == ColumnDiffType.DROPPED:
                    mutation_desc.append(f"dropped column `{c.column_name}` on `{d.model_name}`")
                elif c.diff_type == ColumnDiffType.EXPRESSION_ALTERED:
                    mutation_desc.append(
                        f"modified calculation for `{c.column_name}` on `{d.model_name}`"
                    )

            for j in d.structural.join_diffs:
                if j.diff_type == JoinDiffType.TYPE_CHANGED:
                    mutation_desc.append(
                        f"altered join type on `{j.table_name}` ({j.old_join_type} -> {j.new_join_type}) on `{d.model_name}`"
                    )

        primary_change = mutation_desc[0] if mutation_desc else "modified query logic"

        # Downstream impact summary
        downstream_count = len(downstream_models)
        exposure_count = len(impacted_exposures)

        impact_desc: list[str] = []
        if downstream_count > 0:
            impact_desc.append(f"cascades across **{downstream_count} downstream models**")
        if exposure_count > 0:
            exp_names = ", ".join(f"`{e.label or e.name}`" for e in impacted_exposures[:3])
            if exposure_count > 3:
                exp_names += f" and {exposure_count - 3} more"
            impact_desc.append(f"impacts **{exposure_count} Executive Exposures** ({exp_names})")

        cascade_str = (
            " and ".join(impact_desc) if impact_desc else "remains isolated to modified models"
        )

        return f"{prefix} PR {primary_change}. This {cascade_str}."

    def _generate_remediation(
        self,
        severity: RiskSeverity,
        ast_diffs: list[ModelASTDiff],
        downstream_models: list[DownstreamNode],
        impacted_exposures: list[ExposureNode],
    ) -> list[str]:
        """Generate clear, actionable instructions for the author."""
        advice: list[str] = []

        # Check broken columns
        for m in downstream_models:
            if m.broken_columns:
                advice.append(
                    f"Fix schema reference: Model `{m.name}` relies on column(s) `{', '.join(m.broken_columns)}` which were modified or deleted."
                )

        # Check exposures
        if impacted_exposures:
            exp_names = ", ".join(f"`{e.label or e.name}`" for e in impacted_exposures)
            advice.append(
                f"Verify business metrics: Confirm that filter/calculation changes do not unintentionally alter executive metrics on: {exp_names}."
            )

        # Check predicate tightening
        has_tightened = any(
            any(p.diff_type == PredicateDiffType.TIGHTENED for p in d.predicates) for d in ast_diffs
        )
        if has_tightened:
            advice.append(
                "Audit dropped records: Confirm whether omitting non-matching statuses (e.g. pending/in-transit/disputed) was intended by business stakeholders."
            )

        if not advice:
            advice.append(
                "Standard review: Verify query performance and downstream data test results."
            )

        return advice
