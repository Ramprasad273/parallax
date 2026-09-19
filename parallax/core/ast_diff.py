"""AST-based SQL semantic diff engine using SQLGlot."""

from typing import Any

import sqlglot
from sqlglot import exp

from parallax.core.jinja import JinjaSanitizer
from parallax.core.logging import logger
from parallax.core.models import (
    ColumnDiff,
    ColumnDiffType,
    JoinDiff,
    JoinDiffType,
    ModelASTDiff,
    PredicateClauseType,
    PredicateDiff,
    PredicateDiffType,
    StructuralDiff,
)


class ASTDiffEngine:
    """
    Performs dialect-aware Abstract Syntax Tree (AST) parsing and semantic
    comparison between Base and Head SQL queries.
    """

    def __init__(self, default_dialect: str = "snowflake") -> None:
        self.default_dialect = default_dialect

    def parse_sql(self, sql: str, dialect: str | None = None) -> exp.Expression | None:
        """
        Safely parse raw or compiled SQL into a SQLGlot AST.
        Falls back through standard dialects if vendor dialect raises ParseError.
        """
        if not sql or not sql.strip():
            return None

        sanitized = JinjaSanitizer.sanitize(sql)
        target_dialect = dialect or self.default_dialect

        for d in [target_dialect, "duckdb", "postgres", "ansi", ""]:
            try:
                tree = sqlglot.parse_one(sanitized, read=d if d else None)
                if tree is not None:
                    return tree  # type: ignore[return-value]
            except (sqlglot.errors.ParseError, sqlglot.errors.TokenError, ValueError) as err:
                logger.debug("Failed parsing with dialect %s: %s", d, err)
                continue

        logger.warning("Failed to parse SQL into AST; proceeding with raw comparison.")
        return None

    def diff_model(
        self,
        model_name: str,
        file_path: str,
        base_sql: str | None,
        head_sql: str | None,
        dialect: str | None = None,
    ) -> ModelASTDiff:
        """
        Compare Base and Head SQL for a model and return structured semantic diffs.
        """
        active_dialect = dialect or self.default_dialect

        base_tree = self.parse_sql(base_sql or "", dialect=active_dialect)
        head_tree = self.parse_sql(head_sql or "", dialect=active_dialect)

        predicates: list[PredicateDiff] = []
        columns: list[ColumnDiff] = []
        join_diffs: list[JoinDiff] = []
        group_by_altered = False
        distinct_altered = False

        # Case 1: Newly added file
        if base_tree is None and head_tree is not None:
            for col in self._extract_columns(head_tree):
                columns.append(
                    ColumnDiff(
                        column_name=col["name"],
                        diff_type=ColumnDiffType.ADDED,
                        new_expression=col["expr"],
                        explanation=f"New column '{col['name']}' introduced.",
                    )
                )
            for pred in self._extract_where_predicates(head_tree):
                predicates.append(
                    PredicateDiff(
                        clause=PredicateClauseType.WHERE,
                        diff_type=PredicateDiffType.ADDED,
                        new_expression=pred,
                        explanation="New WHERE predicate introduced in new model.",
                    )
                )
            return ModelASTDiff(
                model_name=model_name,
                file_path=file_path,
                predicates=predicates,
                columns=columns,
            )

        # Case 2: Deleted file
        if base_tree is not None and head_tree is None:
            for col in self._extract_columns(base_tree):
                columns.append(
                    ColumnDiff(
                        column_name=col["name"],
                        diff_type=ColumnDiffType.DROPPED,
                        old_expression=col["expr"],
                        explanation=f"Column '{col['name']}' dropped due to model deletion.",
                    )
                )
            return ModelASTDiff(
                model_name=model_name,
                file_path=file_path,
                columns=columns,
            )

        # Case 3: Both queries exist -> detailed AST semantic diff
        if base_tree is not None and head_tree is not None:
            # 1. Compare Predicates (WHERE and HAVING)
            predicates.extend(
                self._diff_predicates(base_tree, head_tree, exp.Where, PredicateClauseType.WHERE)
            )
            predicates.extend(
                self._diff_predicates(base_tree, head_tree, exp.Having, PredicateClauseType.HAVING)
            )

            # 2. Compare Projected Columns
            columns.extend(self._diff_columns(base_tree, head_tree))

            # 3. Compare Joins
            join_diffs.extend(self._diff_joins(base_tree, head_tree))

            # 4. Compare GROUP BY & DISTINCT
            base_group = [e.sql() for e in base_tree.find_all(exp.Group)]
            head_group = [e.sql() for e in head_tree.find_all(exp.Group)]
            group_by_altered = base_group != head_group

            base_distinct = bool(base_tree.find(exp.Distinct))
            head_distinct = bool(head_tree.find(exp.Distinct))
            distinct_altered = base_distinct != head_distinct

        structural = StructuralDiff(
            join_diffs=join_diffs,
            group_by_altered=group_by_altered,
            distinct_altered=distinct_altered,
        )

        return ModelASTDiff(
            model_name=model_name,
            file_path=file_path,
            predicates=predicates,
            columns=columns,
            structural=structural,
        )

    def _extract_columns(self, tree: exp.Expression) -> list[dict[str, str]]:
        """Extract projected column names and expressions from outermost SELECT."""
        results: list[dict[str, str]] = []
        # Find outermost select expressions
        select_node = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
        if not select_node:
            return results

        for expression in select_node.expressions:
            col_name = expression.alias_or_name
            results.append({"name": col_name, "expr": expression.sql()})
        return results

    def _diff_columns(
        self, base_tree: exp.Expression, head_tree: exp.Expression
    ) -> list[ColumnDiff]:
        """Compare projected SELECT columns for additions, deletions, renames, and mutations."""
        diffs: list[ColumnDiff] = []
        base_cols = {c["name"]: c["expr"] for c in self._extract_columns(base_tree)}
        head_cols = {c["name"]: c["expr"] for c in self._extract_columns(head_tree)}

        # Detect dropped columns (Breaking Schema Change)
        for col_name, old_expr in base_cols.items():
            if col_name not in head_cols:
                diffs.append(
                    ColumnDiff(
                        column_name=col_name,
                        diff_type=ColumnDiffType.DROPPED,
                        old_expression=old_expr,
                        explanation=f"Column '{col_name}' dropped from projection list.",
                    )
                )

        # Detect added columns & altered expressions
        for col_name, new_expr in head_cols.items():
            if col_name not in base_cols:
                diffs.append(
                    ColumnDiff(
                        column_name=col_name,
                        diff_type=ColumnDiffType.ADDED,
                        new_expression=new_expr,
                        explanation=f"New column '{col_name}' added to projection list.",
                    )
                )
            else:
                old_expr = base_cols[col_name]
                # Compare canonical SQL string of expressions
                if old_expr.strip() != new_expr.strip():
                    diffs.append(
                        ColumnDiff(
                            column_name=col_name,
                            diff_type=ColumnDiffType.EXPRESSION_ALTERED,
                            old_expression=old_expr,
                            new_expression=new_expr,
                            explanation=f"Calculation for column '{col_name}' modified.",
                        )
                    )

        return diffs

    def _decompose_predicates(self, clause_node: exp.Expression | None) -> list[exp.Expression]:
        """Flatten nested boolean AND conjuncts into a flat list of conditions."""
        if not clause_node:
            return []
        inner = clause_node.this if hasattr(clause_node, "this") else clause_node
        if not inner:
            return []

        conjuncts: list[exp.Expression] = []

        def _walk(node: Any) -> None:
            if isinstance(node, exp.And):
                _walk(node.left)
                _walk(node.right)
            elif isinstance(node, exp.Expression):
                conjuncts.append(node)

        _walk(inner)
        return conjuncts

    def _extract_where_predicates(self, tree: exp.Expression) -> list[str]:
        where_node = tree.find(exp.Where)
        if not where_node:
            return []
        return [c.sql() for c in self._decompose_predicates(where_node)]

    def _diff_predicates(
        self,
        base_tree: exp.Expression,
        head_tree: exp.Expression,
        clause_cls: type[exp.Expression],
        clause_type: PredicateClauseType,
    ) -> list[PredicateDiff]:
        """Compare boolean conditions in WHERE or HAVING clauses."""
        diffs: list[PredicateDiff] = []
        base_clause = base_tree.find(clause_cls)
        head_clause = head_tree.find(clause_cls)

        if not base_clause and not head_clause:
            return diffs

        base_conjuncts = self._decompose_predicates(base_clause)
        head_conjuncts = self._decompose_predicates(head_clause)

        base_map = {c.sql().strip(): c for c in base_conjuncts}
        head_map = {c.sql().strip(): c for c in head_conjuncts}

        # Case A: Predicates in base that are missing in head
        for b_sql, b_node in base_map.items():
            if b_sql not in head_map:
                # Check if there is an altered condition on the same column/identifier
                matching_head = self._find_matching_condition(b_node, head_conjuncts)
                if matching_head is not None:
                    h_sql = matching_head.sql().strip()
                    diff_type, explanation = self._classify_predicate_change(b_node, matching_head)
                    diffs.append(
                        PredicateDiff(
                            clause=clause_type,
                            diff_type=diff_type,
                            old_expression=b_sql,
                            new_expression=h_sql,
                            explanation=explanation,
                        )
                    )
                else:
                    diffs.append(
                        PredicateDiff(
                            clause=clause_type,
                            diff_type=PredicateDiffType.DROPPED,
                            old_expression=b_sql,
                            explanation=f"Filter condition '{b_sql}' removed entirely.",
                        )
                    )

        # Case B: Newly added conditions in head that have no counterpart in base
        for h_sql, h_node in head_map.items():
            if h_sql not in base_map:
                matching_base = self._find_matching_condition(h_node, base_conjuncts)
                if matching_base is None:
                    diffs.append(
                        PredicateDiff(
                            clause=clause_type,
                            diff_type=PredicateDiffType.TIGHTENED,
                            new_expression=h_sql,
                            explanation=f"New restrictive filter condition '{h_sql}' added.",
                        )
                    )

        return diffs

    def _find_matching_condition(
        self, target: exp.Expression, candidates: list[exp.Expression]
    ) -> exp.Expression | None:
        """Find a candidate condition that operates on the same column or expression."""
        target_cols = {col.sql().lower() for col in target.find_all(exp.Column)}
        if not target_cols:
            return None

        for cand in candidates:
            cand_cols = {col.sql().lower() for col in cand.find_all(exp.Column)}
            if target_cols & cand_cols:
                return cand
        return None

    @staticmethod
    def _extract_col_and_num(node: exp.Expression) -> tuple[str, float] | None:
        """Extract (column_name, float_val) from a binary comparison with a numeric literal."""
        left = getattr(node, "this", None)
        right = getattr(node, "expression", None)
        if isinstance(left, exp.Column) and isinstance(right, exp.Literal) and right.is_number:
            try:
                return (left.sql().lower(), float(right.this))
            except (ValueError, TypeError):
                return None
        if isinstance(right, exp.Column) and isinstance(left, exp.Literal) and left.is_number:
            try:
                return (right.sql().lower(), float(left.this))
            except (ValueError, TypeError):
                return None
        return None

    def _classify_predicate_change(
        self, old_node: exp.Expression, new_node: exp.Expression
    ) -> tuple[PredicateDiffType, str]:
        """
        Classify the semantic nature of a changed predicate
        (e.g., negative filter to strict equality: NOT IN -> =).
        """
        old_sql = old_node.sql()
        new_sql = new_node.sql()

        # Check for NOT IN ('returned', 'cancelled') <-> status = 'delivered'
        is_old_negative = isinstance(old_node, exp.Not) or "NOT IN" in old_sql.upper()
        is_new_positive = isinstance(new_node, (exp.EQ, exp.In)) and not isinstance(
            new_node, exp.Not
        )
        is_old_positive = isinstance(old_node, (exp.EQ, exp.In)) and not isinstance(
            old_node, exp.Not
        )
        is_new_negative = isinstance(new_node, exp.Not) or "NOT IN" in new_sql.upper()

        if is_old_negative and is_new_positive:
            return (
                PredicateDiffType.TIGHTENED,
                f"Filter tightened from negative exclusion ({old_sql}) to strict match ({new_sql}), omitting unhandled categories.",
            )
        if is_old_positive and is_new_negative:
            return (
                PredicateDiffType.LOOSENED,
                f"Filter loosened from strict match ({old_sql}) to negative exclusion ({new_sql}), expanding matched records.",
            )

        # Check for IN list expansion or contraction
        if (
            isinstance(old_node, exp.In)
            and not isinstance(old_node, exp.Not)
            and isinstance(new_node, exp.In)
            and not isinstance(new_node, exp.Not)
        ):
            old_items = {e.sql().strip("'\"").lower() for e in getattr(old_node, "expressions", [])}
            new_items = {e.sql().strip("'\"").lower() for e in getattr(new_node, "expressions", [])}
            if new_items > old_items:
                return (
                    PredicateDiffType.LOOSENED,
                    f"Filter loosened: allowed set expanded in IN clause ({old_sql} -> {new_sql}).",
                )
            if new_items < old_items:
                return (
                    PredicateDiffType.TIGHTENED,
                    f"Filter tightened: allowed set reduced in IN clause ({old_sql} -> {new_sql}).",
                )

        # Check for comparison threshold changes on numeric literals (e.g. amount > 100 -> amount > 50)
        old_comp = self._extract_col_and_num(old_node)
        new_comp = self._extract_col_and_num(new_node)
        if old_comp and new_comp and old_comp[0] == new_comp[0]:
            _, old_val = old_comp
            _, new_val = new_comp
            if isinstance(old_node, (exp.GT, exp.GTE)) and isinstance(new_node, (exp.GT, exp.GTE)):
                if new_val < old_val:
                    return (
                        PredicateDiffType.LOOSENED,
                        f"Filter threshold relaxed from {old_sql} to {new_sql}.",
                    )
                if new_val > old_val:
                    return (
                        PredicateDiffType.TIGHTENED,
                        f"Filter threshold restricted from {old_sql} to {new_sql}.",
                    )
            elif isinstance(old_node, (exp.LT, exp.LTE)) and isinstance(new_node, (exp.LT, exp.LTE)):
                if new_val > old_val:
                    return (
                        PredicateDiffType.LOOSENED,
                        f"Filter threshold relaxed from {old_sql} to {new_sql}.",
                    )
                if new_val < old_val:
                    return (
                        PredicateDiffType.TIGHTENED,
                        f"Filter threshold restricted from {old_sql} to {new_sql}.",
                    )

        # Check for operator mutation
        old_op = type(old_node)
        new_op = type(new_node)
        if old_op != new_op:
            return (
                PredicateDiffType.MUTATED_OPERATOR,
                f"Filter operator changed from {old_op.__name__} to {new_op.__name__} ({old_sql} -> {new_sql}).",
            )

        # General mutation
        return (
            PredicateDiffType.MUTATED_OPERATOR,
            f"Filter condition altered from '{old_sql}' to '{new_sql}'.",
        )

    def _diff_joins(self, base_tree: exp.Expression, head_tree: exp.Expression) -> list[JoinDiff]:
        """Detect JOIN additions, deletions, and type alterations (INNER to LEFT)."""
        diffs: list[JoinDiff] = []
        base_joins = {self._join_table_name(j): j for j in base_tree.find_all(exp.Join)}
        head_joins = {self._join_table_name(j): j for j in head_tree.find_all(exp.Join)}

        for tbl, b_join in base_joins.items():
            if tbl not in head_joins:
                diffs.append(
                    JoinDiff(
                        table_name=tbl,
                        diff_type=JoinDiffType.JOIN_REMOVED,
                        explanation=f"Join on table '{tbl}' removed.",
                    )
                )
            else:
                h_join = head_joins[tbl]
                b_side = (b_join.side or "INNER").upper()
                h_side = (h_join.side or "INNER").upper()
                b_kind = (b_join.kind or "").upper()
                h_kind = (h_join.kind or "").upper()

                b_type = f"{b_side} {b_kind}".strip()
                h_type = f"{h_side} {h_kind}".strip()

                if b_type != h_type:
                    diffs.append(
                        JoinDiff(
                            table_name=tbl,
                            diff_type=JoinDiffType.TYPE_CHANGED,
                            old_join_type=b_type,
                            new_join_type=h_type,
                            explanation=f"Join type changed from {b_type} to {h_type} (may introduce NULLs downstream).",
                        )
                    )

        for tbl, h_join in head_joins.items():
            if tbl not in base_joins:
                diffs.append(
                    JoinDiff(
                        table_name=tbl,
                        diff_type=JoinDiffType.JOIN_ADDED,
                        explanation=f"New join on table '{tbl}' added.",
                    )
                )

        return diffs

    def _join_table_name(self, join_node: exp.Join) -> str:
        this = join_node.this
        if hasattr(this, "alias_or_name"):
            name = this.alias_or_name
            return str(name) if name else str(this)
        return str(this)
