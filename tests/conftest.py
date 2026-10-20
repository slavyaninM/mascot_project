"""Общие фикстуры и хелперы для тестов MASCOT."""
from datetime import date

from src.mascot.agents.analytics_layer.schemas import (
    AssessmentStatus,
    CompetencyAssessment,
    Contradiction,
    EmployeeEvaluation,
    EvidenceSource,
)
from src.mascot.agents.trust_layer.metric import Metric
from src.mascot.storage.models import Employee, Project, ProjectRequirement

# Билдер функции
def make_employee(
    id: str = "emp_001",
    name: str = "Test Employee",
    role: str = "Developer",
    skills: dict[str, int] | None = None,
    available: bool = True,
) -> Employee:
    return Employee(
        id=id,
        name=name,
        role=role,
        skills=skills if skills is not None else {},
        available=available,
    )


def make_requirement(skill: str, min_level: int, weight: float = 1.0) -> ProjectRequirement:
    return ProjectRequirement(skill=skill, min_level=min_level, weight=weight)


def make_project(
    id: str = "proj_001",
    name: str = "Test Project",
    team_size: int = 2,
    requirements: list[ProjectRequirement] | None = None,
) -> Project:
    return Project(
        id=id,
        name=name,
        description="test",
        team_size=team_size,
        requirements=requirements if requirements is not None else [],
    )


def make_metric(
    name: str = "commits_count",
    value: float = 10.0,
    source: str = "git",
    sample_size: int = 10,
    confidence: float = 1.0,
) -> Metric:
    return Metric(
        name=name,
        value=value,
        source=source,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        sample_size=sample_size,
        confidence=confidence,
    )


def make_profile(
    employee_id: str = "emp_001",
    full_name: str = "Test Employee",
    metrics: list[Metric] | None = None,
):
    from src.mascot.storage.models import EmployeeProfile
    return EmployeeProfile(
        employee_id=employee_id,
        full_name=full_name,
        role="Developer",
        grade="Middle",
        metrics=metrics if metrics is not None else [],
    )


def make_assessment(
    employee_id: str = "emp_001",
    competency: str = "python",
    level: float = 3.0,
    status: AssessmentStatus = AssessmentStatus.SUFFICIENT,
) -> CompetencyAssessment:
    return CompetencyAssessment(
        employee_id=employee_id,
        competency=competency,
        level=level,
        status=status,
        evidence=[EvidenceSource(source="declared", value=level, confidence=1.0)],
        rationale="test",
    )


def make_evaluation(
    employee_id: str = "emp_001",
    full_name: str = "Test Employee",
    assessments: list[CompetencyAssessment] | None = None,
) -> EmployeeEvaluation:
    return EmployeeEvaluation(
        employee_id=employee_id,
        full_name=full_name,
        assessments=assessments if assessments is not None else [],
    )