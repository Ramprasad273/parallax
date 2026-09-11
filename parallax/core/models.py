"""Data contracts and schemas for Parallax AST diffing and blast radius engine."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RiskSeverity(str, Enum):
    """Risk severity levels assigned by Parallax."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    NEVER = "NEVER"

    @property
    def _rank(self) -> int:
        order = {
            RiskSeverity.NEVER: -1,
            RiskSeverity.LOW: 0,
            RiskSeverity.MEDIUM: 1,
            RiskSeverity.HIGH: 2,
            RiskSeverity.CRITICAL: 3,
        }
        return order[self]

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RiskSeverity):
            return NotImplemented
        return self._rank >= other._rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RiskSeverity):
            return NotImplemented
        return self._rank > other._rank


class PredicateClauseType(str, Enum):
    """Clause where a predicate condition lives."""

    WHERE = "WHERE"
    HAVING = "HAVING"
    JOIN_ON = "JOIN_ON"


class PredicateDiffType(str, Enum):
    """Type of semantic change in a filter predicate."""

    TIGHTENED = "TIGHTENED"
    LOOSENED = "LOOSENED"
    DROPPED = "DROPPED"
    ADDED = "ADDED"
    MUTATED_OPERATOR = "MUTATED_OPERATOR"


class ColumnDiffType(str, Enum):
    """Type of mutation on a projected column."""

    DROPPED = "DROPPED"
    RENAMED = "RENAMED"
    EXPRESSION_ALTERED = "EXPRESSION_ALTERED"
    ADDED = "ADDED"


class JoinDiffType(str, Enum):
    """Type of mutation on a table join."""

    TYPE_CHANGED = "TYPE_CHANGED"
    CONDITION_CHANGED = "CONDITION_CHANGED"
    JOIN_ADDED = "JOIN_ADDED"
    JOIN_REMOVED = "JOIN_REMOVED"


class ModelLayer(str, Enum):
    """Standard dbt model architectural layer."""

    STAGING = "staging"
    INTERMEDIATE = "intermediate"
    MARTS = "marts"
    REPORTING = "reporting"
    OTHER = "other"

    @classmethod
    def from_path(cls, path: str) -> "ModelLayer":
        normalized = path.lower().replace("\\", "/")
        if "/staging/" in normalized or "stg_" in normalized:
            return cls.STAGING
        if "/intermediate/" in normalized or "int_" in normalized:
            return cls.INTERMEDIATE
        if "/marts/" in normalized or "fct_" in normalized or "dim_" in normalized:
            return cls.MARTS
        if "/reporting/" in normalized or "rpt_" in normalized:
            return cls.REPORTING
        return cls.OTHER


class ExposureType(str, Enum):
    """dbt Exposure type."""

    DASHBOARD = "dashboard"
    NOTEBOOK = "notebook"
    ANALYSIS = "analysis"
    ML = "ml"
    APPLICATION = "application"
    REVERSE_ETL = "reverse_etl"


class PredicateDiff(BaseModel):
    """Represents a semantic difference in a SQL boolean predicate."""

    model_config = ConfigDict(frozen=True)

    clause: PredicateClauseType
    diff_type: PredicateDiffType
    old_expression: str | None = None
    new_expression: str | None = None
    explanation: str


class ColumnDiff(BaseModel):
    """Represents a mutation in a model's SELECT projection list."""

    model_config = ConfigDict(frozen=True)

    column_name: str
    diff_type: ColumnDiffType
    old_expression: str | None = None
    new_expression: str | None = None
    explanation: str


class JoinDiff(BaseModel):
    """Represents a structural mutation in a table JOIN."""

    model_config = ConfigDict(frozen=True)

    table_name: str
    diff_type: JoinDiffType
    old_join_type: str | None = None
    new_join_type: str | None = None
    old_condition: str | None = None
    new_condition: str | None = None
    explanation: str


class StructuralDiff(BaseModel):
    """Represents high-level structural changes in a SQL query."""

    model_config = ConfigDict(frozen=True)

    join_diffs: list[JoinDiff] = Field(default_factory=list)
    group_by_altered: bool = False
    distinct_altered: bool = False
    explanation: str | None = None


class ModelASTDiff(BaseModel):
    """Complete AST diff for a single modified SQL model file."""

    model_config = ConfigDict(frozen=True)

    model_name: str
    file_path: str
    predicates: list[PredicateDiff] = Field(default_factory=list)
    columns: list[ColumnDiff] = Field(default_factory=list)
    structural: StructuralDiff = Field(default_factory=StructuralDiff)

    @property
    def has_semantic_changes(self) -> bool:
        return (
            bool(self.predicates)
            or bool(self.columns)
            or bool(self.structural.join_diffs)
            or self.structural.group_by_altered
            or self.structural.distinct_altered
        )

    @property
    def dropped_columns(self) -> list[str]:
        return [
            c.column_name
            for c in self.columns
            if c.diff_type in (ColumnDiffType.DROPPED, ColumnDiffType.RENAMED)
        ]


class ExposureNode(BaseModel):
    """A downstream consumer declared in dbt schema (e.g. Looker/Tableau)."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str | None = None
    exposure_type: ExposureType = ExposureType.DASHBOARD
    owner_name: str | None = None
    url: str | None = None
    description: str | None = None


class DownstreamNode(BaseModel):
    """A dbt model affected by an upstream modification."""

    model_config = ConfigDict(frozen=True)

    unique_id: str
    name: str
    layer: ModelLayer
    file_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    broken_columns: list[str] = Field(default_factory=list)
    distance_from_source: int = 1


class BlastRadiusReport(BaseModel):
    """The comprehensive report containing all AST and lineage diff results."""

    model_config = ConfigDict(frozen=True)

    modified_models: list[str]
    ast_diffs: list[ModelASTDiff]
    downstream_models: list[DownstreamNode]
    impacted_exposures: list[ExposureNode]
    max_dag_depth: int = 0
    risk_severity: RiskSeverity = RiskSeverity.LOW
    plain_english_summary: str = "No semantic changes detected."
    remediation_advice: list[str] = Field(default_factory=list)
    execution_duration_ms: float = 0.0

    @property
    def has_breaking_changes(self) -> bool:
        return any(bool(m.broken_columns) for m in self.downstream_models)
