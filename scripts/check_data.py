from src.mascot.agents.data_layer.integrator import load_employees, load_projects
from src.mascot.agents.data_layer.scale_validator import (
    validate_employee,
    validate_project,
)


def main():
    employees = load_employees()
    projects = load_projects()

    for employee in employees:
        errors = validate_employee(employee)

        if errors:
            print("\n".join(errors))
        else:
            print(f"OK: {employee.name}")

    for project in projects:
        errors = validate_project(project)

        if errors:
            print("\n".join(errors))
        else:
            print(f"OK: {project.name}")


if __name__ == "__main__":
    main()