# from dataclasses import dataclass, field

# # простой словарь предметной области
# @dataclass
# class Employee:
#     id: str
#     name: str
#     role: str
#     skills: dict[str, int] = field(default_factory=dict)
#     available: bool = True


# @dataclass
# class ProjectRequirement:
#     skill: str
#     min_level: int
#     weight: float = 1.0


# @dataclass
# class Project:
#     id: str
#     name: str
#     description: str
#     team_size: int
#     requirements: list[ProjectRequirement] = field(default_factory=list)


# # пока не реализовал
# @dataclass
# class TeamRecommendation:
#     project_id: str
#     selected_employee_ids: list[str]
#     covered_requirements: list[str]
#     missing_requirements: list[str]
#     explanation: str

# ========================================================================================================================================================================
# ===============================================================объединённый models.py===================================================================================
# ========================================================================================================================================================================
from src.mascot.agents.trust_layer.metric import Metric
class Employee(BaseModel):        # был dataclass в test_data
    id: str; name: str; role: str
    skills: dict[str, int] = {}
    available: bool = True

class ProjectRequirement(BaseModel): ...
class Project(BaseModel): ...
class TeamRecommendation(BaseModel): ...

class RawDigitalTrace(BaseModel): ...   # из main
class EmployeeProfile(BaseModel): ...   # из main