from src.mascot.storage.models import Employee, Project

# вынести шкалу в config/settings.py потом
MIN_SKILL_LEVEL = 0
MAX_SKILL_LEVEL = 5


# возвращает список ошибок до того как он уйдет в бд
def validate_employee(employee: Employee) -> list[str]:
    errors = []

    if not employee.id:
        errors.append("У сотрудника отсутствует id")

    if not employee.name:
        errors.append(f"У сотрудника {employee.id} отсутствует имя")

    for skill, level in employee.skills.items():
        if not MIN_SKILL_LEVEL <= level <= MAX_SKILL_LEVEL:
            errors.append(
                f"Некорректный уровень навыка {skill} "
                f"у сотрудника {employee.id}: {level}"
            )

    return errors


def validate_project(project: Project) -> list[str]:
    errors = []

    if not project.id:
        errors.append("У проекта отсутствует id")

    if project.team_size <= 0:
        errors.append(f"У проекта {project.id} некорректный размер команды")

    for requirement in project.requirements:
        if not MIN_SKILL_LEVEL <= requirement.min_level <= MAX_SKILL_LEVEL:
            errors.append(
                f"Некорректный минимальный уровень навыка "
                f"{requirement.skill} у проекта {project.id}"
            )

        if requirement.weight <= 0:
            errors.append(
                f"Некорректный вес навыка {requirement.skill} "
                f"у проекта {project.id}"
            )

    return errors