"""Загрузчик тестовых данных v1: test_data_v1.json и test_project_data_v1.json.

Сырые записи (6 блоков на сотрудника, свободный текст по проекту)
преобразуются во внутренние модели: Employee, EmployeeProfile, Metric, Project.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from src.mascot.agents.trust_layer.metric import Metric
from src.mascot.storage.models import (
    Employee,
    EmployeeProfile,
    Project,
    ProjectRequirement,
)

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "raw"

GRADE_LEVEL = {"Junior": 0.3, "Middle": 0.5, "Senior": 0.75, "Lead": 0.85}
DEFAULT_SKILL_LEVEL = 0.5
# Стек → нормализованное имя навыка
STACK_ALIASES: dict[str, str] = {
    "python": "python", "django": "django", "fastapi": "fastapi",
    "postgresql": "sql", "sql": "sql",
    "java": "java", "spring boot": "spring",
    "react": "react", "typescript": "typescript",
    "tailwind": "css", "css": "css",
    "docker": "docker",
    "postman": "testing", "devtools": "testing",
    "selenium": "testing", "pytest": "testing",
    "go": "go", "node": "node",
    "unity": "unity", "c#": "csharp",
    "flutter": "flutter", "dart": "dart",
    "vue": "vue", "nuxt": "vue",
}

# 360 → нормализованное имя soft-навыка
SOFT_SKILL_MAP = {
    "communication_and_empathy": "communication",
    "teamwork_collaboration": "teamwork",
    "problem_solving_creativity": "problem_solving",
    "adaptability_stress_tolerance": "adaptability",
}


def _normalize(name: str, raw: float) -> tuple[float, int, float]:
    """(value 0-1, sample_size, confidence). Эвристики нормализации."""
    if name == "commits_count_30_days":
        return min(1.0, raw / 100), int(raw), 0.7
    if name == "code_reviews_done":
        return min(1.0, raw / 50), int(raw), 0.7
    if name == "resolved_tasks_30_days":
        return min(1.0, raw / 40), int(raw), 0.6
    if name == "velocity_index":
        return min(1.0, raw / 1.2), 1, 0.6
    if name == "average_test_score_percent":
        return raw / 100, 1, 0.5
    if name == "customer_satisfaction_score_csat":
        return raw / 5, 1, 0.4
    if name.startswith("360_"):
         # v1 не передаёт число респондентов 360 - sample_size=1 (один
        # агрегированный отзыв). confidence ниже порога 0.5, чтобы soft-skill
        # не получал SUFFICIENT «на халяву».
        return raw / 5, 1, 0.3 
    return min(1.0, max(0.0, raw)), 1, 0.5


def _extract_metrics(raw: dict) -> list[Metric]:
    today = date.today()
    start = today - timedelta(days=30)
    metrics: list[Metric] = []

    def add(name: str, value: float, source: str) -> None:
        v, sample, conf = _normalize(name, value)
        metrics.append(Metric(
            name=name, value=v, source=source,
            period_start=start, period_end=today,
            sample_size=sample, confidence=conf,
        ))

    git = raw.get("git_analytics", {})
    if "commits_count_30_days" in git:
        add("commits_count_30_days", git["commits_count_30_days"], "git")
    if "code_reviews_done" in git:
        add("code_reviews_done", git["code_reviews_done"], "git")

    tt = raw.get("task_tracker", {})
    if "resolved_tasks_30_days" in tt:
        add("resolved_tasks_30_days", tt["resolved_tasks_30_days"], "jira")
    if "velocity_index" in tt:
        add("velocity_index", tt["velocity_index"], "jira")

    lms = raw.get("lms", {})
    if "average_test_score_percent" in lms:
        add("average_test_score_percent", lms["average_test_score_percent"], "lms")

    crm = raw.get("crm_service_desk", {})
    if "customer_satisfaction_score_csat" in crm:
        add("customer_satisfaction_score_csat",
            crm["customer_satisfaction_score_csat"], "crm")

    review = raw.get("soft_skills_and_feedback", {}) \
                 .get("performance_review_360", {})
    for key, value in review.get("scores", {}).items():
        if key in SOFT_SKILL_MAP:
            add(f"360_{key}", value, "360")

    return metrics


def _extract_skills(raw: dict) -> dict[str, float]:
    # Грейд → базовый уровень навыка (эвристика; заменить реальными оценками)
    hr = raw.get("hr_system", {})
    base_level = GRADE_LEVEL.get(hr.get("grade", ""), DEFAULT_SKILL_LEVEL)

    """Заявленные навыки (0-1): primary_stack + 360 + факт активности."""
    skills: dict[str, float] = {}

    for tech in raw.get("git_analytics", {}).get("primary_stack", []):
        skill = STACK_ALIASES.get(tech.lower().strip())
        if skill:
            skills[skill] = base_level  # работает с технологией, уровень не подтверждён

    review = raw.get("soft_skills_and_feedback", {}) \
                 .get("performance_review_360", {})
    for key, value in review.get("scores", {}).items():
        skill = SOFT_SKILL_MAP.get(key)
        if skill:
            skills[skill] = value / 5

    # Навыки, для которых есть прямые метрики: без них L_k не соберётся
    if raw.get("git_analytics", {}).get("commits_count_30_days", 0) > 0:
        skills.setdefault("git", 0.6)
    if raw.get("task_tracker", {}).get("resolved_tasks_30_days", 0) > 0:
        skills.setdefault("jira", 0.6)
    if raw.get("lms", {}).get("completed_courses_count", 0) > 0:
        skills.setdefault("lms", 0.6)
    if raw.get("crm_service_desk", {}).get("resolved_incidents", 0) > 0:
        skills.setdefault("crm", 0.6)
    # навык testing для QA-позиций(в primary его не бывает)
    position = hr.get("position", "").lower()
    if "тестиров" in position or "qa" in position:
        skills.setdefault("testing", base_level)

    return skills


def load_employees_v1(path: Path | None = None) -> tuple[list[Employee], list[EmployeeProfile]]:
    file_path = path or (DATA_DIR / "test_data_v1.json")
    with file_path.open(encoding="utf-8") as f:
        raw_list = json.load(f)

    employees: list[Employee] = []
    profiles: list[EmployeeProfile] = []

    for raw in raw_list:
        hr = raw.get("hr_system", {})
        emp_id = hr.get("employee_id", "")
        name = hr.get("full_name", "")
        role = hr.get("position", "")
        grade = hr.get("grade", "")

        employees.append(Employee(
            id=emp_id, name=name, role=role,
            skills=_extract_skills(raw), available=True,
        ))
        profiles.append(EmployeeProfile(
            employee_id=emp_id, full_name=name, role=role, grade=grade,
            metrics=_extract_metrics(raw), is_available=True,
        ))

    return employees, profiles


# --- Проекты ---

# ---------------------------------------------------------------------------
# Паттерны поиска технологий в тексте (word boundary, не подстрока).
# Нормализация составных имён (C#, Node.js, Vue.js) выполняется
# в _normalize_for_skills ДО применения паттернов.
# ---------------------------------------------------------------------------
_SKILL_PATTERNS: dict[str, str] = {
    # Языки
    "python":     r"\bpython\b",
    "java":       r"\bjava\b",                       # \b не сработает в javascript
    "javascript": r"\bjavascript\b",
    "typescript": r"\btypescript\b",
    "rust":       r"\brust\b",
    "go":         r"\bgo\b|\bgolang\b",              # \b не сработает в django
    "dart":       r"\bdart\b",
    # Фреймворки / платформы
    "django":     r"\bdjango\b",
    "fastapi":    r"\bfastapi\b",
    "spring":     r"\bspring\b",
    "nodejs":     r"\bnodejs\b|\bnode\b",
    "react":      r"\breact\b",
    "vue":        r"\bvue\b|\bnuxt\b",
    "angular":    r"\bangular\b",
    "unity":      r"\bunity\b",
    "csharp":     r"\bcsharp\b",
    "flutter":    r"\bflutter\b",
    # Данные / инфраструктура
    "sql":        r"\bpostgres(?:ql)?\b|\bsql\b|\bmysql\b|\bsqlite\b|\bpostgis\b",
    "docker":     r"\bdocker\b",
    "kubernetes": r"\bkubernetes\b|\bk8s\b",
    "kafka":      r"\bkafka\b",
    "redis":      r"\bredis\b",
}

# Семантические маркеры ролей → навык (не технологии, а роль)
_QA_ROLE_MARKERS = ("qa", "тестиров")
_MOBILE_ROLE_MARKERS = ("mobile", "мобильн")


def _normalize_for_skills(text: str) -> str:
    """
    Приводит текст к виду, где \\b работает для составных названий.
    C# → csharp, Node.js → nodejs, Vue.js → vue.
    """
    text = text.lower()
    for old, new in (
        ("c#", " csharp "),
        ("node.js", " nodejs "),
        ("vue.js", " vue "),
        ("nuxt.js", " nuxt "),
        (".net", " dotnet "),
    ):
        text = text.replace(old, new)
    return text


def _extract_skills_from_text(text: str) -> set[str]:
    """Все технологии из текста по word-boundary паттернам."""
    normalized = _normalize_for_skills(text)
    found: set[str] = set()
    for skill, pattern in _SKILL_PATTERNS.items():
        if re.search(pattern, normalized):
            found.add(skill)
    return found


def _flatten_to_text(obj) -> str:
    """Рекурсивно собирает все строки из dict / list / str."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_flatten_to_text(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten_to_text(v) for v in obj)
    return ""


def _is_qa_role(role: str) -> bool:
    lower = role.lower()
    return any(marker in lower for marker in _QA_ROLE_MARKERS)


def _role_min_level(role: str) -> float:
    """Минимальный уровень по грейд-подсказке в тексте роли."""
    role_lower = role.lower()
    levels = [
        level for grade_key, level in GRADE_LEVEL.items()
        if grade_key.lower() in role_lower
    ]
    return max(levels) if levels else DEFAULT_SKILL_LEVEL

def _interpret_project(raw: dict) -> Project:
    """
    Извлекает требования проекта из v1-структуры.

    Правила (по задаче «разделить источники»):
    1. required_roles — конкретные должности; из них берутся только ЯВНО
       упомянутые технологии (Go, Java, Unity, Flutter, React ...).
       Автоматическая подстановка «backend → python, java, go, sql, docker»
       отключена: иначе Go появлялся в проектах, где его нет.
    2. technical_specification + frontend_and_ui + quality_assurance_scope —
       все скалярные строки customer_requirements. Оттуда берутся
       все найденные технологии.
    3. QA-роль → навык testing (семантика, не технология).
    4. Веса: явно в роли → 2.0, только в спецификации → 1.0.
    """
    meta = raw.get("meta", {})
    reqs = raw.get("customer_requirements", {})
    staffing = raw.get("hr_staffing_implications", {}) \
        or reqs.get("hr_staffing_implications", {})
    roles = staffing.get("required_roles", []) or []
    roles_text = " ".join(roles)

    # 1. Технологии из спецификации (все поля customer_requirements)
    spec_skills = _extract_skills_from_text(_flatten_to_text(reqs))
    
    # 2. Технологии, явно упомянутые в тексте ролей
    role_skills = _extract_skills_from_text(roles_text)

    # 3. QA-роль → testing
    if any(_is_qa_role(r) for r in roles):
        role_skills.add("testing")

    # 4. Итоговый пул навыков
    all_skills = spec_skills | role_skills

    # 5. Минимальный уровень — max по грейд-подсказкам всех ролей
    min_level = max(
        (_role_min_level(r) for r in roles),
        default=DEFAULT_SKILL_LEVEL,
    )

    # 6. Веса и сборка
    requirements = [
        ProjectRequirement(
            skill=skill,
            min_level=min_level,
            weight=2.0 if skill in role_skills else 1.0,
        )
        for skill in sorted(all_skills)
    ]

    return Project(
        id=raw.get("project_id", ""),
        name=meta.get("title", ""),
        description=meta.get("description", ""),
        team_size=max(1, len(roles)),
        requirements=requirements,
    )


def load_projects_v1(path: Path | None = None) -> list[Project]:
    file_path = path or (DATA_DIR / "test_project_data_v1.json")
    with file_path.open(encoding="utf-8") as f:
        raw_list = json.load(f)
    return [_interpret_project(raw) for raw in raw_list]