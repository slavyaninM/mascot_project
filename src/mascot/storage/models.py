from typing import Any

from pydantic import BaseModel, Field

from src.mascot.agents.trust_layer.metric import Metric


# Доменные модели — для подбора команды
# (были dataclass в ветке test_data, теперь Pydantic)

class Employee(BaseModel):
    """Сотрудник — кандидат в команду проекта."""
    id: str
    name: str
    role: str
    skills: dict[str, float] = Field(default_factory=dict)
    available: bool = True


class ProjectRequirement(BaseModel):
    """Одно требование проекта к навыку."""
    skill: str
    min_level: float
    weight: float = 1.0


class Project(BaseModel):
    """Проект, под который подбирается команда."""
    id: str
    name: str
    description: str
    team_size: int
    requirements: list[ProjectRequirement] = Field(default_factory=list)


class TeamRecommendation(BaseModel):
    """Результат подбора команды."""
    project_id: str
    selected_employee_ids: list[str]
    covered_requirements: list[str]
    missing_requirements: list[str]
    explanation: str


# Модели из ветки main


class RawDigitalTrace(BaseModel):
    """Схема сырого цифрового следа сотрудника."""
    employee_id: str

    source_system: str   # jira, git, lms, hr
    event_type: str      # commit, task_closed, test_passed
    payload: dict[str, Any]


class EmployeeProfile(BaseModel):
    """Единый структурированный профиль сотрудника."""


    employee_id: str
    full_name: str
    role: str
    grade: str

    # Метрики теперь несут провенанс (источник, период, уверенность).
    # Было: Dict[str, Any] с git/jira/lms.
    metrics: list[Metric] = Field(default_factory=list)

    is_available: bool = True


# Вспомогательные утилиты

def get_metric(profile: EmployeeProfile, name: str) -> Metric | None:
    """Находит метрику по имени. None, если её нет."""
    for metric in profile.metrics:
        if metric.name == name:
            return metric
    return None
