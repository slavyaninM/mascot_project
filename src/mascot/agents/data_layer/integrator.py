import json
from pathlib import Path

from src.mascot.storage.models import Employee, Project, ProjectRequirement
# путь определяется относительно текущего файла
DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "raw"


def load_employees() -> list[Employee]:
    file_path = DATA_DIR / "employees.json"
    # без кодировки ломается путь если будут русские символы
    with file_path.open(encoding="utf-8") as file:
        raw_employees = json.load(file)

    return [
        Employee(
            id=item["id"],
            name=item["name"],
            role=item["role"],
            skills=item["skills"],
            available=item["available"],
            # один работник не будет доступен это для дальнейших тестов
        )
        for item in raw_employees
    ]


def load_projects() -> list[Project]:
    file_path = DATA_DIR / "projects.json"

    with file_path.open(encoding="utf-8") as file:
        raw_projects = json.load(file)

    projects = []

    for item in raw_projects:
        requirements = [
            ProjectRequirement(
                skill=req["skill"],
                min_level=req["min_level"],
                weight=req["weight"],
            )
            for req in item["requirements"]
        ]

        projects.append(
            Project(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                team_size=item["team_size"],
                requirements=requirements,
            )
        )

    return projects