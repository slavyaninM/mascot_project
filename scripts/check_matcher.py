from src.mascot.agents.data_layer.integrator import (
    load_employees,
    load_projects,
)
from src.mascot.pipelines.distribute_team import match_team


def main():
    # точка входа, хагружает данные, подбирает команду, передает отчеты
    # загружает данные из json в объекты Employee Project
    employees = load_employees()
    projects = load_projects()

    # берем первый проект из списка и запускаем подбор
    project = projects[0]
    # для проверки одного проекта норм, но позже можно переделать, чтобы сейчас не усложнять
    result = match_team(employees, project)

    # отчет по блокам
    print(f"Проект: {project.name}")
    print(f"Требуется сотрудников: {project.team_size}")


    # в result лежат только id а не объекты
    employees_by_id = {emp.id: emp for emp in employees}   

    # список объектов, не ИД => можно сразу вытягивать данные
    print("\nВыбранная команда:")
    for emp_id in result.selected_employee_ids:
        emp = employees_by_id[emp_id]
        print(f"- {emp.name} ({emp.role})")
    # удалить \/
    # for employee in result.selected_employees:
    #     print(f"- {employee.name} ({employee.role})")


    # вывод требований
    print("\nПокрытые требования:")
    print(", ".join(result.covered_requirements) or "нет")

    print("\nНепокрытые требования:")
    print(", ".join(result.missing_requirements) or "нет")
    
    print("\nОбъяснение:")
    print(result.explanation)


if __name__ == "__main__":
    main()