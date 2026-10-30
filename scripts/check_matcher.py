from src.mascot.agents.data_layer.v1_loader import (
    load_employees_v1,
    load_projects_v1
)
from src.mascot.pipelines.distribute_team import match_team
from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee

def main() -> None:
    # точка входа, хагружает данные, подбирает команду, передает отчеты
    # загружает данные из json в объекты Employee Project
    employees, profiles = load_employees_v1()
    projects = load_projects_v1()
    profiles_by_id = {p.employee_id: p for p in profiles}
    evaluations = [evaluate_employee(e, profiles_by_id.get(e.id)) for e in employees]

    employees_by_id = {emp.id: emp for emp in employees}

    for project in projects:
        result = match_team(employees, project, evaluations)
        print(f"\n=== {project.name} ({project.id}) ===")
        print(f"Требуется: {project.team_size}")
        print("Команда:")
        for emp_id in result.selected_employee_ids:
            emp = employees_by_id[emp_id]
            print(f"  - {emp.name} ({emp.role})")
        print(f"Покрыто: {', '.join(result.covered_requirements) or 'нет'}")
        print(f"Не покрыто: {', '.join(result.missing_requirements) or 'нет'}")
        print(f"Объяснение: {result.explanation}")


if __name__ == "__main__":
    main()