"""Интеграционные тесты: полный pipeline от данных до решения."""
import pytest

from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee
from src.mascot.agents.decision_layer.optimizer import build_team
from src.mascot.pipelines.distribute_team import match_team, recommend_team
from tests.conftest import make_employee, make_project, make_requirement
from src.mascot.agents.decision_layer.schemas import TeamStatus


class TestFullPipeline:
    def test_employees_to_report(self):
        """Полная цепочка: Employee → evaluation → report."""
        employees = [
            make_employee(id="e1", name="Иван", skills={"python": 4}),
            make_employee(id="e2", name="Мария", skills={"testing": 4}),
        ]
        project = make_project(
            team_size=2,
            requirements=[
                make_requirement("python", 3),
                make_requirement("testing", 3),
            ],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert report.status in (TeamStatus.OPTIMAL, TeamStatus.DEGRADED)
        assert len(report.selected_employee_ids) == 2
        assert report.weighted_coverage == pytest.approx(1.0)


class TestBackwardCompatibility:
    def test_match_team_returns_old_model(self):
        """Старый API match_team возвращает TeamRecommendation."""
        from src.mascot.storage.models import TeamRecommendation

        employees = [make_employee(id="e1", skills={"python": 4})]
        project = make_project(team_size=1, requirements=[make_requirement("python", 3)])

        result = match_team(employees, project)

        assert isinstance(result, TeamRecommendation)
        assert result.project_id == project.id
        assert len(result.selected_employee_ids) == 1

    def test_match_team_with_precomputed_evaluations(self):
        """match_team принимает готовые evaluations."""
        employees = [make_employee(id="e1", skills={"python": 4})]
        project = make_project(team_size=1, requirements=[make_requirement("python", 3)])
        evaluations = [evaluate_employee(e) for e in employees]

        result = match_team(employees, project, evaluations)

        assert len(result.selected_employee_ids) == 1

    def test_recommend_team_returns_full_report(self):
        """Новый API recommend_team возвращает расширенный отчёт."""
        employees = [make_employee(id="e1", skills={"python": 4})]
        project = make_project(team_size=1, requirements=[make_requirement("python", 3)])

        report = recommend_team(employees, project)

        # Расширенные поля, которых нет в старом TeamRecommendation
        assert hasattr(report, "requirement_coverages")
        assert hasattr(report, "risks")
        assert hasattr(report, "alternatives")
        assert hasattr(report, "follow_ups")


class TestEmptyInputs:
    def test_empty_employees(self):
        project = make_project(team_size=2, requirements=[make_requirement("python", 3)])

        report = build_team(project, [], [])

        assert report.status == TeamStatus.INFEASIBLE
        assert len(report.infeasibility_reasons) > 0

    def test_empty_requirements(self):
        employees = [make_employee(id="e1", skills={"python": 4})]
        project = make_project(team_size=1, requirements=[])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        # Нет требований — нечего покрывать, coverage=0 (0/0 → 0)
        assert report.weighted_coverage == 0.0


class TestRealData:
    """Проверка на тестовых данных из data/raw (если они доступны)."""

    def test_real_data_pipeline(self):
        from src.mascot.agents.data_layer.integrator import (
            load_employees,
            load_projects,
        )

        try:
            employees = load_employees()
            projects = load_projects()
        except FileNotFoundError:
            pytest.skip("data/raw не найдены")

        evaluations = [evaluate_employee(e) for e in employees]
        project = projects[0]

        report = build_team(project, evaluations, employees)

        assert report.selected_employee_ids
        assert len(report.selected_employee_ids) <= project.team_size
        assert report.status != TeamStatus.INFEASIBLE