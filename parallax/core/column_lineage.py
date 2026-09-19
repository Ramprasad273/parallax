"""Multi-hop Column-Level Lineage (CLL) Engine for Parallax."""

import re
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage

from parallax.core.jinja import JinjaSanitizer
from parallax.core.logging import logger
from parallax.core.models import ColumnImpact


class ColumnLineageEngine:
    """
    Traces column-level lineage across dbt models in the downstream blast radius.

    Operates purely statically in-memory without requiring database credentials
    or live warehouse connections.
    """

    def __init__(self, default_dialect: str = "postgres") -> None:
        self.default_dialect = default_dialect

    def trace_subgraph_column_lineage(
        self,
        nodes: dict[str, dict[str, Any]],
        modified_models: list[str],
        dropped_or_modified_columns: dict[str, list[str]],
        subgraph_node_ids: list[str],
        dialect: str | None = None,
    ) -> tuple[dict[str, list[ColumnImpact]], dict[str, list[str]]]:
        """
        Trace column derivations and detect broken column contracts across
        models in the downstream blast radius.

        Args:
            nodes: Manifest nodes dictionary mapping unique_id to node data.
            modified_models: Short names or unique_ids of modified root models.
            dropped_or_modified_columns: Dict of {model_identifier: [col1, col2]}.
            subgraph_node_ids: Unique IDs of downstream models to analyze.
            dialect: SQL dialect (postgres, snowflake, bigquery, etc.).

        Returns:
            Tuple of:
              - column_impacts_by_id: {unique_id: [ColumnImpact, ...]}
              - broken_columns_by_id: {unique_id: [broken_col_name, ...]}
        """
        active_dialect = dialect or self.default_dialect

        # Normalize modified model names
        mod_names: set[str] = set()
        for m in modified_models:
            clean = m.split("/")[-1].replace(".sql", "").split(".")[-1]
            mod_names.add(clean)

        # Collect dropped columns across all modified models
        all_dropped_cols: set[str] = set()
        dropped_by_model: dict[str, set[str]] = {}
        for m_key, cols in dropped_or_modified_columns.items():
            clean_m = m_key.split("/")[-1].replace(".sql", "").split(".")[-1]
            dropped_by_model.setdefault(clean_m, set()).update(cols)
            all_dropped_cols.update(cols)

        # 1. Prepare sanitized SQL for models in the blast radius
        sources: dict[str, str] = {}
        for uid, node_data in nodes.items():
            name = node_data.get("name", "")
            if not name:
                continue
            # Include downstream nodes or modified root models
            if uid in subgraph_node_ids or name in mod_names:
                raw_code = node_data.get("raw_code") or node_data.get("compiled_code") or ""
                if raw_code:
                    sources[name] = JinjaSanitizer.sanitize(raw_code)

        column_impacts_by_id: dict[str, list[ColumnImpact]] = {}
        broken_columns_by_id: dict[str, list[str]] = {}

        # 2. Analyze each downstream model
        for uid in subgraph_node_ids:
            node_data = nodes.get(uid, {})
            model_name = node_data.get("name", uid)
            sql = sources.get(model_name)

            if not sql:
                continue

            impacts: list[ColumnImpact] = []
            broken_cols: set[str] = set()

            # Attempt AST-based column lineage
            try:
                parsed = sqlglot.parse_one(sql, read=active_dialect)

                # A. Check WHERE, HAVING, JOIN ON clauses for dropped columns
                all_dropped_cols_lower = {c.lower(): c for c in all_dropped_cols}
                mod_names_lower = {m.lower(): m for m in mod_names}
                for identifier in parsed.find_all(exp.Column):
                    col_id_name = identifier.name.lower()
                    if col_id_name in all_dropped_cols_lower:
                        orig_col = all_dropped_cols_lower[col_id_name]
                        table_id = (identifier.table or "").lower()
                        if not table_id or table_id in mod_names_lower:
                            broken_cols.add(orig_col)

                # B. Trace projected SELECT columns
                select_node = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
                if select_node and hasattr(select_node, "selects"):
                    for sel in select_node.selects:
                        col_name = sel.alias_or_name
                        if not col_name or col_name == "*":
                            continue

                        try:
                            lineage_tree = lineage(
                                col_name,
                                sql,
                                sources=sources,
                                dialect=active_dialect,
                            )

                            # Walk upstream lineage
                            trail: list[str] = []
                            is_broken = False
                            matched_upstream_col: str | None = None
                            matched_upstream_mod: str | None = None

                            for step in lineage_tree.walk():
                                s_name = step.name
                                s_source = step.source_name
                                trail.append(s_name)

                                # Check if this step references any dropped or mutated column
                                for mod_cand, dropped_set in dropped_by_model.items():
                                    mod_cand_lower = mod_cand.lower()
                                    for d_col in dropped_set:
                                        d_col_lower = d_col.lower()
                                        s_name_lower = s_name.lower()
                                        s_source_lower = (s_source or "").lower()
                                        if (
                                            s_name_lower == d_col_lower
                                            or s_name_lower == f"{mod_cand_lower}.{d_col_lower}"
                                            or (s_source_lower == mod_cand_lower and s_name_lower.endswith(d_col_lower))
                                            or s_name_lower.endswith(f".{d_col_lower}")
                                        ):
                                            is_broken = True
                                            matched_upstream_col = d_col
                                            matched_upstream_mod = mod_cand
                                            broken_cols.add(d_col)

                            if matched_upstream_col and matched_upstream_mod:
                                clean_trail = [
                                    n for n in reversed(trail) if n and not n.startswith("CTE")
                                ]
                                if clean_trail and clean_trail[-1] != f"{model_name}.{col_name}":
                                    clean_trail.append(f"{model_name}.{col_name}")

                                expr_summary = None
                                if hasattr(sel, "this") and sel.this:
                                    expr_summary = str(sel.this)[:100]

                                impacts.append(
                                    ColumnImpact(
                                        model_name=model_name,
                                        column_name=col_name,
                                        upstream_model=matched_upstream_mod,
                                        upstream_column=matched_upstream_col,
                                        is_broken=is_broken,
                                        lineage_path=clean_trail,
                                        expression_summary=expr_summary,
                                    )
                                )
                                if model_name not in dropped_by_model:
                                    dropped_by_model[model_name] = set()
                                dropped_by_model[model_name].add(col_name)

                        except Exception as col_err:  # noqa: BLE001
                            logger.debug(
                                "AST column lineage skipped for %s.%s: %s",
                                model_name,
                                col_name,
                                col_err,
                            )

            except Exception as parse_err:  # noqa: BLE001
                logger.debug(
                    "AST parse failed on %s: %s. Falling back to heuristic.",
                    model_name,
                    parse_err,
                )

            # C. Robust Fallback: Regex scan for dropped columns if AST missed or failed
            if all_dropped_cols:
                for col in all_dropped_cols:
                    if col not in broken_cols:
                        pattern = rf"\b{re.escape(col)}\b"
                        if re.search(pattern, sql, re.IGNORECASE):
                            broken_cols.add(col)
                            if not any(imp.upstream_column.lower() == col.lower() for imp in impacts):
                                impacts.append(
                                    ColumnImpact(
                                        model_name=model_name,
                                        column_name=col,
                                        upstream_model=next(iter(mod_names)) if mod_names else "",
                                        upstream_column=col,
                                        is_broken=True,
                                        lineage_path=[
                                            f"upstream.{col}",
                                            f"{model_name}.(referenced)",
                                        ],
                                        expression_summary="Direct SQL column reference",
                                    )
                                )

            if impacts:
                column_impacts_by_id[uid] = impacts
            if broken_cols:
                broken_columns_by_id[uid] = sorted(broken_cols)

        return column_impacts_by_id, broken_columns_by_id
