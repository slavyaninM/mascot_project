"""Тесты аналитического слоя: контракты и оценщик компетенций."""
import pytest

from src.mascot.agents.analytics_layer.schemas import AssessmentStatus
from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee
from src.mascot.agents.trust_layer.metric import Metric
from tests.conftest import make_employee, make_metric, make_profile


# =============================================================================
# Базовое поведение evaluator
# =============================================================================

class TestEvaluatorBasics:
    def test_returns_one_assessment_per_skill(self):
        emp = make_employee(skills={"python": 4, "sql": 3, "git": 2})
        result = evaluate_employee(emp)
        assert len(result.assessments) == 3
        assert {a.competency for a in result.assessments} == {"python", "sql", "git"}

    def test_empty_skills_returns_empty_evaluations(self):
        emp = make_employee(skills={})
        result = evaluate_employee(emp)
        assert result.assessments == []

    def test_evaluation_preserves_employee_id_and_name(self):
        emp = make_employee(id="emp_X", name="Иван", skills={"python": 3})
        result = evaluate_employee(emp)
        assert result.employee_id == "emp_X"
        assert result.full_name == "Иван"

    def test_declared_level_is_used_as_level(self):
        emp = make_employee(skills={"python": 4})
        result = evaluate_employee(emp)
        assert result.assessments[0].level == 4.0


# =============================================================================
# Статусы: INSUFFICIENT / SUFFICIENT / CONTRADICTORY
# =============================================================================

class TestAssessmentStatus:
    def test_only_declared_is_insufficient(self):
        """Только заявленное без подтверждения → INSUFFICIENT."""
        emp = make_employee(skills={"python": 4})
        result = evaluate_employee(emp)
        assert result.assessments[0].status == AssessmentStatus.INSUFFICIENT

    def test_sufficient_with_metric_evidence(self):
        """Метрика с sample_size>=5 и confidence>=0.5 → SUFFICIENT."""
        emp = make_employee(skills={"git": 3})
        profile = make_profile(metrics=[make_metric(name="commits_count", value=50)])
        result = evaluate_employee(emp, profile)
        assert result.assessments[0].status == AssessmentStatus.SUFFICIENT

    def test_insufficient_when_metric_sample_too_small(self):
        """Метрика с sample_size<5 → всё равно INSUFFICIENT."""
        emp = make_employee(skills={"git": 3})
        profile = make_profile(
            metrics=[make_metric(name="commits_count", value=50, sample_size=2)]
        )
        result = evaluate_employee(emp, profile)
        assert result.assessments[0].status == AssessmentStatus.INSUFFICIENT

    def test_insufficient_when_metric_confidence_low(self):
        """Метрика с confidence<0.5 → INSUFFICIENT."""
        emp = make_employee(skills={"git": 3})
        profile = make_profile(
            metrics=[make_metric(name="commits_count", value=50, confidence=0.3)]
        )
        result = evaluate_employee(emp, profile)
        assert result.assessments[0].status == AssessmentStatus.INSUFFICIENT

    def test_contradictory_when_large_gap(self):
        """Заявлено 5, метрика даёт ~0 → CONTRADICTORY."""
        emp = make_employee(skills={"git": 5})
        profile = make_profile(
            metrics=[make_metric(name="commits_count", value=0.5, sample_size=20)]
        )
        result = evaluate_employee(emp, profile)
        assert result.assessments[0].status == AssessmentStatus.CONTRADICTORY
        assert len(result.assessments[0].contradictions) > 0

    def test_no_contradiction_with_small_gap(self):
        """Заявлено 4, метрика ~3 → не противоречие."""
        emp = make_employee(skills={"git": 4})
        profile = make_profile(
            metrics=[make_metric(name="commits_count", value=3.0, sample_size=20)]
        )
        result = evaluate_employee(emp, profile)
        assert result.assessments[0].status != AssessmentStatus.CONTRADICTORY


# =============================================================================
# Follow-up и rationale
# =============================================================================

class TestFollowUps:
    def test_insufficient_generates_follow_up(self):
        emp = make_employee(skills={"python": 3})
        result = evaluate_employee(emp)
        assessment = result.assessments[0]
        assert len(assessment.follow_up) > 0
        assert any("python" in f for f in assessment.follow_up)

    def test_sufficient_has_no_follow_up(self):
        emp = make_employee(skills={"git": 3})
        profile = make_profile(
            metrics=[make_metric(name="commits_count", value=50, sample_size=10)]
        )
        result = evaluate_employee(emp, profile)
        assert result.assessments[0].status == AssessmentStatus.SUFFICIENT
        assert result.assessments[0].follow_up == []

    def test_rationale_mentions_skill(self):
        emp = make_employee(skills={"python": 3})
        result = evaluate_employee(emp)
        assert "python" in result.assessments[0].rationale


# =============================================================================
# Вспомогательные методы модели
# =============================================================================

class TestEmployeeEvaluationHelpers:
    def test_get_returns_assessment_by_skill(self):
        emp = make_employee(skills={"python": 4, "sql": 3})
        result = evaluate_employee(emp)
        python_a = result.get("python")
        assert python_a is not None
        assert python_a.competency == "python"

    def test_get_returns_none_for_missing_skill(self):
        emp = make_employee(skills={"python": 4})
        result = evaluate_employee(emp)
        assert result.get("cobol") is None