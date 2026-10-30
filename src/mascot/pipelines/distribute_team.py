"""
Фасад: собирает команду, используя аналитический и решающий слои.
Совместим со старым API match_team(employees, project) -> TeamRecommendation.
"""
from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee
from src.mascot.agents.decision_layer.optimizer import build_team
from src.mascot.storage.models import Employee, Project, TeamRecommendation

def _compute_evaluations(employees, evaluations, profiles):
    if evaluations is not None:
        return evaluations
    profile_by_id = {p.employee_id: p for p in (profiles or [])}
    return [evaluate_employee(emp, profile_by_id.get(emp.id)) for emp in employees]

def match_team(
    employees: list[Employee],
    project: Project,
    evaluations=None,
) -> TeamRecommendation:
    """Обратная совместимость: возвращает старый TeamRecommendation."""
    if evaluations is None:
        evaluations = [evaluate_employee(emp) for emp in employees]
    report = build_team(project, evaluations, employees)
    return TeamRecommendation(
        project_id=report.project_id,
        selected_employee_ids=report.selected_employee_ids,
        covered_requirements=report.covered_requirements,
        missing_requirements=report.missing_requirements,
        explanation=report.explanation,
    )


def recommend_team(
    employees: list[Employee],
    project: Project,
    evaluations=None,
):
    """Возвращает полный TeamDecisionReport."""
    if evaluations is None:
        evaluations = [evaluate_employee(emp) for emp in employees]
    return build_team(project, evaluations, employees)