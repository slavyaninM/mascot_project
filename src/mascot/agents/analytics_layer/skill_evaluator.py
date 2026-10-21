import logging
from src.mascot.agents.trust_layer.metric import Metric
from src.mascot.storage.models import Employee, EmployeeProfile

from .schemas import (
    AssessmentStatus,
    CompetencyAssessment,
    Contradiction,
    EmployeeEvaluation,
    EvidenceSource,
)

logger = logging.getLogger("mascot.evaluator")

# Пороги (потом вынесем в config, пока константы, главное не забыть)
MIN_LEVEL = 0.0
MAX_LEVEL = 1.0
MIN_SAMPLE_FOR_SUFFICIENT = 5
MIN_CONFIDENCE_FOR_SUFFICIENT = 0.5
DECLARED_ONLY_CONFIDENCE = 0.6          # заявленному без подтверждения верим не на все 100%
CONTRADICTION_THRESHOLD = 0.4             # разрыв между заявленным и измеренным


# ---------------------------------------------------------------------------
# Связь метрики и навыка. Простое правило по имени метрики.
# Потом заменим на словарь или конфиг.
# ---------------------------------------------------------------------------
_METRIC_TO_SKILL = {
    "commits_count": "git",
    "pr_opened": "git",
    "tasks_closed": "jira",
    "bugs_count": "jira",
    "courses_completed": "lms",
}


def _metric_relates_to_skill(metric: Metric, skill: str) -> bool:
    """Грузит ли эта метрика навык skill."""
    return _METRIC_TO_SKILL.get(metric.name) == skill


def _has_sufficient_evidence(evidence: list[EvidenceSource]) -> bool:
    """Есть ли хотя бы один источник с достаточной выборкой и уверенностью."""
    for e in evidence:
        if e.source == "declared":
            continue
        sample_ok = (e.sample_size or 0) >= MIN_SAMPLE_FOR_SUFFICIENT
        conf_ok = e.confidence >= MIN_CONFIDENCE_FOR_SUFFICIENT
        if sample_ok and conf_ok:
            return True
    return False


def _detect_contradictions(
    skill: str,
    declared_level: float,
    evidence: list[EvidenceSource],
) -> list[Contradiction]:
    """
    Противоречие: заявленный уровень сильно выше подтверждённого метрикой.
    Пока одна эвристика. Потом можно добавить «метрика выше заявленного» и др.
    """
    contradictions = []
    measured = [e for e in evidence if e.source != "declared"]
    if not measured:
        return contradictions

    # Примитивная нормализация - считаем подтверждённый уровень как
    # средневзвешенный по измеренным свидетельствам. Потом заменить!
    if measured:
        avg_confirmed = sum(e.value for e in measured) / len(measured)
        if abs(declared_level - avg_confirmed) >= CONTRADICTION_THRESHOLD:
            contradictions.append(Contradiction(
                description=(
                    f"Заявленный уровень {skill}={declared_level}, "
                    f"но средний по метрикам ~{avg_confirmed:.1f}"
                ),
                sources=["declared"] + [e.source for e in measured],
                severity="warning",
            ))
    return contradictions


def _suggest_follow_up(
    skill: str,
    status: AssessmentStatus,
    evidence: list[EvidenceSource],
) -> list[str]:
    """Рекомендации доп. проверок — правило 4 из ТЗ."""
    if status == AssessmentStatus.SUFFICIENT:
        return []
    if status == AssessmentStatus.NO_DATA:
        return [f"Провести оценку компетенции {skill}: данных нет"]
    if status == AssessmentStatus.INSUFFICIENT:
        return [f"Проверить {skill}: недостаточно данных для вывода"]
    if status == AssessmentStatus.CONTRADICTORY:
        return [f"Проверить {skill}: источники противоречат друг другу"]
    return []


def _build_rationale(
    skill: str,
    level: float,
    evidence: list[EvidenceSource],
    status: AssessmentStatus,
) -> str:
    parts = [f"Уровень {skill}={level} (статус: {status.value})."]
    if len(evidence) == 1 and evidence[0].source == "declared":
        parts.append("Источник — только заявленный уровень, без подтверждения.")
    elif evidence:
        sources = sorted({e.source for e in evidence})
        parts.append(f"Источники: {', '.join(sources)}.")
    return " ".join(parts)


def evaluate_employee(
    employee: Employee,
    profile: EmployeeProfile | None = None,
) -> EmployeeEvaluation:
    """
    Оценивает все заявленные компетенции сотрудника.

    Логика:
    1. Каждый навык из Employee.skills → CompetencyAssessment.
    2. Заявленный уровень → EvidenceSource с пониженной уверенностью.
    3. Метрики из profile → дополнительные EvidenceSource.
    4. Проверка противоречий.
    5. Определение статуса (sufficient / insufficient / no_data / contradictory).
    6. Рекомендации доп. проверок.
    """
    assessments: list[CompetencyAssessment] = []

    for skill, declared_level in employee.skills.items():
        #1 Заявленное - это свидетельство, но слабое
        evidence = [
            EvidenceSource(
                source="declared",
                value=float(declared_level),
                confidence=DECLARED_ONLY_CONFIDENCE,
                note="Заявлено в профиле",
            )
        ]

        #2 Подтягиваем метрики из профиля
        if profile:
            for metric in profile.metrics:
                if _metric_relates_to_skill(metric, skill):
                    evidence.append(EvidenceSource(
                        source=metric.source,
                        value=metric.value,
                        period_start=metric.period_start,
                        period_end=metric.period_end,
                        sample_size=metric.sample_size,
                        confidence=metric.confidence,
                    ))

        #3 Противоречия
        contradictions = _detect_contradictions(skill, declared_level, evidence)

        #4 Статус
        if contradictions:
            status = AssessmentStatus.CONTRADICTORY
        elif _has_sufficient_evidence(evidence):
            status = AssessmentStatus.SUFFICIENT
        elif len(evidence) > 1:
            status = AssessmentStatus.INSUFFICIENT
        else:
            status = AssessmentStatus.INSUFFICIENT  # только заявленное > недостаточно

        #5 Ограничения
        limitations = []
        if status == AssessmentStatus.INSUFFICIENT:
            limitations.append("Оценка основана только на заявленном уровне")
        if status == AssessmentStatus.CONTRADICTORY:
            limitations.append("Требуется ручная проверка противоречия")

        assessments.append(CompetencyAssessment(
            employee_id=employee.id,
            competency=skill,
            level=float(declared_level),
            status=status,
            evidence=evidence,
            contradictions=contradictions,
            limitations=limitations,
            follow_up=_suggest_follow_up(skill, status, evidence),
            rationale=_build_rationale(skill, declared_level, evidence, status),
        ))

    return EmployeeEvaluation(
        employee_id=employee.id,
        full_name=employee.name,
        assessments=assessments,
    )