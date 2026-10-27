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

<<<<<<< HEAD
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
=======
    # Сюда скрипты будут записывать сухие цифры
    metrics: Dict[str, Any] = Field(
        default_factory=lambda: {
            "git": {"commits_count": 0, "pr_opened": 0},
            "jira": {"tasks_closed": 0, "bugs_count": 0, "avg_time_hours": 0.0},
            "lms": {"courses_completed": 0, "avg_score": 0.0}
        }
    )

    benchmark: Dict[str, Any] = Field(
        default_factory=lambda: {
            "cohort_size": 0, # кол-во людей, с которыми сравниваем
            "compared_at_global": True,  # Флаг: True — внутри компании, False — по рынку
            "metrics_comparison": {}
            # Сюда лягут дельты (например, "git.commits_count": {"delta_pct": 15.2, "status": "above_average"})
        }
    )
    is_available: bool = True  # Флаг для Агента-Фильтра Доступности
>>>>>>> analystics_layer
