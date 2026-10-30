from src.mascot.agents.data_layer.v1_loader import load_employees_v1, load_projects_v1
from src.mascot.agents.data_layer.scale_validator import (
    validate_employee,
    validate_project,
)


def main() -> None:
    employees, profiles = load_employees_v1()
    projects = load_projects_v1()
    profiles_by_id = {p.employee_id: p for p in profiles}
    print(f"Загружено {len(employees)} сотрудников, {len(profiles)} профилей и {len(projects)} проектов")
    
    for employee in employees:
        errors = validate_employee(employee)
        if employee.id not in profiles_by_id:
            errors.append(f"Сотрудник {employee.name} ({employee.id}) не имеет профиля")
        print(f"{'FAIL' if errors else 'OK'}: {employee.name} ({employee.id})")

    for project in projects:
        errors = validate_project(project)
        if not project.requirements:
            errors.append(f"Проект {project.name} ({project.id}) не имеет требований")
        print(f"{'FAIL' if errors else 'OK'}: {project.id} | {project.name}"
              f" | требований: {len(project.requirements)}"
              + (f" | {'; '.join(errors)}" if errors else ""))



if __name__ == "__main__":
    main()