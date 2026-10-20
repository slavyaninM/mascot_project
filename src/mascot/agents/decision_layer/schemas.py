from enum import Enum

from pydantic import BaseModel, Field


class RequirementStatus(str, Enum):
    """Статус покрытия требования командой."""
    COVERED = "covered"           # уровень >= min_level
    PARTIAL = "partial"           # 0 < уровень < min_level
    UNCOVERED = "uncovered"       # уровень = 0
    UNKNOWN = "unknown"           # данных нет ни у кого в команде


class TeamStatus(str, Enum):
    """Общий статус сборки команды."""
    OPTIMAL = "optimal"           # все покрыты, все оценки sufficient
    DEGRADED = "degraded"         # есть непокрытые / неопределённые
    INFEASIBLE = "infeasible"     # собрать нельзя


class ReliabilityLevel(str, Enum):
    """Надёжность одной оценки."""
    HIGH = "high"                 # SUFFICIENT
    MEDIUM = "medium"             # заявленный уровень, без подтверждения
    LOW = "low"                   # INSUFFICIENT или CONTRADICTORY
    UNKNOWN = "unknown"


class RequirementCoverage(BaseModel):
    """Покрытие одного требования всей командой."""
    skill: str
    min_level: int
    weight: float

    achieved_level: float | None      # нет данных
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    deficit: float

    status: RequirementStatus
    covered_by_employee_id: str | None = None
    covered_by_name: str | None = None
    covered_by_reliability: ReliabilityLevel = ReliabilityLevel.UNKNOWN
    reliability_notes: list[str] = Field(default_factory=list)


class TeamRisk(BaseModel):
    """Один риск состава или ограничение данных."""
    type: str                         # uncovered, unknown_data, low_confidence, size, availability
    severity: str = "warning"         # info | warning | error
    description: str
    related_skills: list[str] = Field(default_factory=list)
    related_employee_ids: list[str] = Field(default_factory=list)


class FollowUp(BaseModel):
    """Рекомендация доп. проверки (правило 4 ТЗ)."""
    employee_id: str | None = None
    competency: str | None = None
    reason: str


class TeamAlternative(BaseModel):
    """Краткая сводка альтернативного варианта — для сравнения."""
    selected_employee_ids: list[str]
    weighted_coverage: float
    total_deficit: float
    status: TeamStatus


class TeamDecisionReport(BaseModel):
    """Полный отчёт слоя принятия решений."""
    project_id: str
    project_name: str
    team_size_limit: int

    selected_employee_ids: list[str]
    selected_employee_names: list[str]

    requirement_coverages: list[RequirementCoverage]

    # Сводные метрики
    
    weighted_coverage: float = Field(ge=0.0, le=1.0)
    weighted_deficit: float
    coverage_ratio_simple: float = Field(ge=0.0, le=1.0)   # доля требований со статусом COVERED

    # Совместимость со старым TeamRecommendation

    covered_requirements: list[str]
    missing_requirements: list[str]

    # Диагностика

    risks: list[TeamRisk] = Field(default_factory=list)
    follow_ups: list[FollowUp] = Field(default_factory=list)
    alternatives: list[TeamAlternative] = Field(default_factory=list)
    infeasibility_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    status: TeamStatus
    explanation: str