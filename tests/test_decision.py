"""Тесты слоя принятия решений: оптимизатор команды."""
import pytest

from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee
from src.mascot.agents.decision_layer.optimizer import (
    build_team,
    _score_team,
    _evaluate_requirement_for_team,
)
from src.mascot.agents.decision_layer.schemas import (
    RequirementStatus,
    ReliabilityLevel,
    TeamStatus,
)
from tests.conftest import (
    make_assessment,
    make_employee,
    make_evaluation,
    make_project,
    make_requirement,
)


# =============================================================================
# Infeasible случаи
# =============================================================================

class TestInfeasible:
    def test_no_available_employees(self):
        employees = [
            make_employee(id="e1", skills={"python": 0.8}, available=False),
            make_employee(id="e2", skills={"python": 0.6}, available=False),
        ]
        project = make_project(team_size=2, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert report.status == TeamStatus.INFEASIBLE
        assert len(report.infeasibility_reasons) > 0
        assert "доступных" in report.infeasibility_reasons[0].lower()

    def test_zero_team_size(self):
        employees = [make_employee(id="e1", skills={"python": 0.8})]
        project = make_project(team_size=0, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert report.status == TeamStatus.INFEASIBLE
        assert any("размер" in r.lower() for r in report.infeasibility_reasons)


# =============================================================================
# Ограничения (жёсткие правила)
# =============================================================================

class TestHardConstraints:
    def test_unavailable_not_selected(self):
        employees = [
            make_employee(id="e1", skills={"python": 0.8}, available=False),
            make_employee(id="e2", skills={"python": 0.6}, available=True),
        ]
        project = make_project(team_size=2, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert "e1" not in report.selected_employee_ids
        assert "e2" in report.selected_employee_ids

    def test_no_duplicate_employees(self):
        employees = [make_employee(id=f"e{i}", skills={"python": 0.6}) for i in range(3)]
        project = make_project(
            team_size=2,
            requirements=[make_requirement("python", 0.6), make_requirement("sql", 0.4)],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert len(report.selected_employee_ids) == len(set(report.selected_employee_ids))

    def test_does_not_exceed_team_size(self):
        employees = [make_employee(id=f"e{i}", skills={"python": 0.8}) for i in range(5)]
        project = make_project(
            team_size = 2,
            requirements=[make_requirement("python", 0.6)],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert len(report.selected_employee_ids) == 2

    def test_degraded_when_fewer_available_than_team_size(self):
        employees = [
            make_employee(id="e1", skills={"python": 0.8}, available=True),
            make_employee(id="e2", skills={"python": 0.6}, available=False),
        ]
        project = make_project(team_size=2, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)
        assert report.status == TeamStatus.DEGRADED
        assert len(report.selected_employee_ids) == 1
        assert any(r.type == "size" for r in report.risks)


# =============================================================================
# Покрытие требований
# =============================================================================

class TestCoverage:
    def test_covered_requirement(self):
        emp = make_employee(id="e1", skills={"python": 0.8})
        project = make_project(team_size=1, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(emp)]

        report = build_team(project, evaluations, [emp])

        cov = report.requirement_coverages[0]
        assert cov.status == RequirementStatus.COVERED
        assert cov.deficit == 0.0
        assert cov.coverage_ratio == 1.0

    def test_partial_coverage_deficit(self):
        emp = make_employee(id="e1", skills={"python": 0.4})
        project = make_project(team_size=1, requirements=[make_requirement("python", 1.0)])
        evaluations = [evaluate_employee(emp)]

        report = build_team(project, evaluations, [emp])

        cov = report.requirement_coverages[0]
        assert cov.status == RequirementStatus.PARTIAL
        assert cov.deficit == 3.0
        assert 0.0 < cov.coverage_ratio < 1.0

    def test_uncovered_requirement_unknown_data(self):
        """Нет данных по навыку у всех — UNKNOWN, не 0-уровень."""
        emp = make_employee(id="e1", skills={})   # нет навыка вообще
        project = make_project(
            team_size=1, requirements=[make_requirement("cobol", 0.6)]
        )
        evaluations = [evaluate_employee(emp)]

        report = build_team(project, evaluations, [emp])

        cov = report.requirement_coverages[0]
        assert cov.status == RequirementStatus.UNKNOWN
        assert cov.achieved_level is None

    def test_coverage_by_team_not_individual(self):
        """Требование может быть закрыто ЛЮБЫМ членом команды."""
        employees = [
            make_employee(id="e1", skills={"python": 0.2}),   # низкий
            make_employee(id="e2", skills={"python": 1.0}),   # высокий
        ]
        project = make_project(team_size=2, requirements=[make_requirement("python", 0.8)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        cov = report.requirement_coverages[0]
        assert cov.status == RequirementStatus.COVERED
        assert cov.covered_by_employee_id == "e2"


# =============================================================================
# Метрики
# =============================================================================

class TestMetrics:
    def test_weighted_coverage_in_range(self):
        employees = [make_employee(id="e1", skills={"python": 0.8})]
        project = make_project(team_size=1, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert 0.0 <= report.weighted_coverage <= 1.0

    def test_full_coverage_is_one(self):
        employees = [make_employee(id="e1", skills={"python": 0.8, "sql": 0.8})]
        project = make_project(
            team_size=1,
            requirements=[
                make_requirement("python", 0.6, weight=2.0),
                make_requirement("sql", 0.6, weight=1.0),
            ],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert report.weighted_coverage == pytest.approx(1.0)

    def test_zero_coverage_when_all_uncovered(self):
        employees = [make_employee(id="e1", skills={})]
        project = make_project(
            team_size=1,
            requirements=[make_requirement("cobol", 0.6)],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert report.weighted_coverage == 0.0

    def test_weighted_deficit_accumulates(self):
        employees = [make_employee(id="e1", skills={"python": 0.4, "sql": 0.2})]
        project = make_project(
            team_size=1,
            requirements=[
                make_requirement("python", 0.8, weight=1.0),  # дефицит 2
                make_requirement("sql", 0.6, weight=2.0),     # дефицит 2
            ],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        # weighted_deficit = 1.0*2 + 2.0*2 = 6.0
        assert report.weighted_deficit == pytest.approx(6.0)


# =============================================================================
# Альтернативы и риски
# =============================================================================

class TestAlternativesAndRisks:
    def test_alternatives_generated(self):
        employees = [make_employee(id=f"e{i}", skills={"python": 0.6}) for i in range(4)]
        project = make_project(team_size=2, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert len(report.alternatives) > 0
        # Ни одна альтернатива не совпадает с победителем
        winner_set = set(report.selected_employee_ids)
        for alt in report.alternatives:
            assert set(alt.selected_employee_ids) != winner_set

    def test_uncovered_generates_risk(self):
        emp = make_employee(id="e1", skills={})
        project = make_project(team_size=1, requirements=[make_requirement("cobol", 0.6)])
        evaluations = [evaluate_employee(emp)]

        report = build_team(project, evaluations, [emp])

        assert any(r.type == "unknown_data" for r in report.risks)

    def test_low_reliability_generates_risk_and_follow_up(self):
        emp = make_employee(id="e1", skills={"python": 0.6})   # только заявленное
        project = make_project(team_size=1, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(emp)]

        report = build_team(project, evaluations, [emp])

        # Оценка MEDIUM надёжности (заявленное без подтверждения)
        assert any(r.type == "low_confidence" for r in report.risks)
        assert len(report.follow_ups) > 0


# =============================================================================
# Детерминизм и объяснение
# =============================================================================

class TestDeterminism:
    def test_same_input_same_output(self):
        employees = [make_employee(id=f"e{i}", skills={"python": 0.6}) for i in range(3)]
        project = make_project(team_size=2, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report1 = build_team(project, evaluations, employees)
        report2 = build_team(project, evaluations, employees)

        assert report1.selected_employee_ids == report2.selected_employee_ids
        assert report1.weighted_coverage == report2.weighted_coverage

    def test_explanation_mentions_team(self):
        employees = [make_employee(id="e1", name="Иван", skills={"python": 0.8})]
        project = make_project(team_size=1, requirements=[make_requirement("python", 0.6)])
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert "Иван" in report.explanation
        assert project.name in report.explanation

    def test_covered_missing_lists_match_coverages(self):
        employees = [make_employee(id="e1", skills={"python": 0.8, "sql": 0.2})]
        project = make_project(
            team_size=1,
            requirements=[
                make_requirement("python", 0.6),
                make_requirement("sql", 1.0),
            ],
        )
        evaluations = [evaluate_employee(e) for e in employees]

        report = build_team(project, evaluations, employees)

        assert "python" in report.covered_requirements
        assert "sql" in report.missing_requirements


# =============================================================================
# Низкоуровневые функции оптимизатора
# =============================================================================

class TestInternalFunctions:
    def test_get_effective_level_from_evaluation(self):
        emp = make_employee(id="e1", skills={"python": 0.6})
        evaluation = make_evaluation(
            employee_id="e1",
            assessments=[make_assessment(competency="python", level=4.0)],
        )
        employees_by_id = {"e1": emp}
        evaluations_by_id = {"e1": evaluation}

        cov = _evaluate_requirement_for_team(
            ["e1"],
            make_requirement("python", 0.6),
            evaluations_by_id,
            employees_by_id,
        )

        assert cov.achieved_level == 4.0

    def test_get_effective_level_fallback_to_skills(self):
        """Если оценки нет — используется Employee.skills с MEDIUM надёжностью."""
        emp = make_employee(id="e1", skills={"python": 0.6})
        employees_by_id = {"e1": emp}

        cov = _evaluate_requirement_for_team(
            ["e1"],
            make_requirement("python", 0.6),
            {},   # пустые evaluations
            employees_by_id,
        )

        assert cov.achieved_level == 3.0
        assert cov.covered_by_reliability == ReliabilityLevel.MEDIUM