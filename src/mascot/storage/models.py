from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class RawDigitalTrace(BaseModel):
    """Схема сырого цифрового следа сотрудника."""
    employee_id: str
    source_system: str  # 'jira', 'git', 'lms', 'hr'
    event_type: str  # 'commit', 'task_closed', 'test_passed'
    payload: Dict[str, Any]


class EmployeeProfile(BaseModel):
    """Единый структурированный JSON-профиль сотрудника."""
    employee_id: str
    full_name: str
    role: str
    grade: str

    # Сюда скрипты будут записывать сухие цифры
    metrics: Dict[str, Any] = Field(
        default_factory=lambda: {
            "git": {"commits_count": 0, "pr_opened": 0},
            "jira": {"tasks_closed": 0, "bugs_count": 0, "avg_time_hours": 0.0},
            "lms": {"courses_completed": 0, "avg_score": 0.0}
        }
    )
    is_available: bool = True  # Флаг для Агента-Фильтра Доступности
