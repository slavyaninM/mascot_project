from dataclasses import dataclass, field

# простой словарь предметной области
@dataclass
class Employee:
    id: str
    name: str
    role: str
    skills: dict[str, int] = field(default_factory=dict)
    available: bool = True


@dataclass
class ProjectRequirement:
    skill: str
    min_level: int
    weight: float = 1.0


@dataclass
class Project:
    id: str
    name: str
    description: str
    team_size: int
    requirements: list[ProjectRequirement] = field(default_factory=list)


# пока не реализовал
@dataclass
class TeamRecommendation:
    project_id: str
    selected_employee_ids: list[str]
    covered_requirements: list[str]
    missing_requirements: list[str]
    explanation: str
    