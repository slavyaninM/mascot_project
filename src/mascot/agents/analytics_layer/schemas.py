from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class AssessmentStatus(str, Enum):
    """Статус достоверности оценки."""
    SUFFICIENT = "sufficient"        # данных достаточно, можно опираться
    INSUFFICIENT = "insufficient"    # данных мало, нужна доп проверка
    NO_DATA = "no_data"              # оценки нет вовсе null
    CONTRADICTORY = "contradictory"  # источники противоречат друг другу


class EvidenceSource(BaseModel):
    """
    Одно свидетельство в пользу оценки.
    Это «факт» — заявленный уровень, метрика из Git, отзыв и т.п.
    """
    source: str                            # declared, git, jira, lms, hr, test
    value: float                           # числовое значение уровня или метрики
    period_start: date | None = None
    period_end: date | None = None
    sample_size: int | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    note: str | None = None


class Contradiction(BaseModel):
    """Противоречие между источниками."""
    description: str
    sources: list[str]
    severity: str = "warning"              # warning | error


class CompetencyAssessment(BaseModel):
    """
    Оценка одной компетенции одного сотрудника.
    Ключевое: отдельно факты (evidence), отдельно вывод (level + rationale).
    """
    employee_id: str
    competency: str
    level: float = Field(ge=0.0, le=5.0)
    status: AssessmentStatus

    evidence: list[EvidenceSource] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)   # рекомендации доп проверок
    rationale: str                                        # почему такой уровень


class EmployeeEvaluation(BaseModel):
    """Полная оценка сотрудника — все компетенции."""
    employee_id: str
    full_name: str
    assessments: list[CompetencyAssessment] = Field(default_factory=list)

    def get(self, competency: str) -> CompetencyAssessment | None:
        for a in self.assessments:
            if a.competency == competency:
                return a
        return None