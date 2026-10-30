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

     # v1
    "commits_count_30_days": "git",
    "code_reviews_done": "git",
    "resolved_tasks_30_days": "jira",
    "velocity_index": "jira",
    "average_test_score_percent": "lms",
    "customer_satisfaction_score_csat": "crm",
    "360_communication_and_empathy": "communication",
    "360_teamwork_collaboration": "teamwork",
    "360_problem_solving_creativity": "problem_solving",
    "360_adaptability_stress_tolerance": "adaptability",
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

def _is_level_comparable(evidence: EvidenceSource) -> bool:
    """
    Можно ли сравнивать значение метрики с уровнем навыка 0..1.

    Временнное правило: считаем level-метрикой только значение в диапазоне 0..1.
    Счетчики (commits_count, pr_opened, tasks_closed, bugs_count и т.п.)
    в противоречии не учавствуют.
    """
    return MIN_LEVEL <= evidence.value <= MAX_LEVEL


def _detect_contradictions(
    skill: str,
    declared_level: float,
    evidence: list[EvidenceSource],
) -> list[Contradiction]:
    """
    Противоречие ищем только при достаточных доказательствах и только среди level-метрик в шкале 0..1.
    """
    contradictions: list[Contradiction] = []

    if not _has_sufficient_evidence(evidence):
        return contradictions

    comparable = [
        e 
        for e in evidence
        if e.source != "declared" and _is_level_comparable(e)
    ]

    if not comparable:
        return contradictions

    avg_confirmed = sum(e.value for e in comparable) / len(comparable)

    if abs(declared_level - avg_confirmed) >= CONTRADICTION_THRESHOLD:
        contradictions.append(
            Contradiction(
                description=(
                    f"Заявленный уровень {skill}={declared_level}, "
                    f"но средний подтвержденный уровень ~{avg_confirmed:.2f}"
                ),
                sources=["declared"] + [e.source for e in comparable],
                severity="warning",
            )
        )
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

        # L_k = Σ(c_i · l_i) / Σ(c_i) — взвешенная сумма свидетельств только по лвл-метрикам (0..1), остальные игнорируем
        #счетчики (commits_count, pr_opened, tasks_closed, bugs_count и т.п.) в противоречии не учавствуют.
        level_evidence = [e for e in evidence if _is_level_comparable(e)]
        if level_evidence:
            total_c = sum(e.confidence for e in evidence)
            level = (sum(e.confidence * e.value for e in evidence) / total_c)
            
        else:
            level = float(declared_level)
        level = min(max(level, MIN_LEVEL), MAX_LEVEL)  # ограничиваем 0..1
        
        #3 Противоречия
        contradictions = _detect_contradictions(skill, declared_level, evidence)

        #4 Статус
        if not _has_sufficient_evidence(evidence):
            status = AssessmentStatus.INSUFFICIENT
        elif contradictions:
            status = AssessmentStatus.CONTRADICTORY
        else:
            status = AssessmentStatus.SUFFICIENT

        #5 Ограничения
        limitations = []
        if status == AssessmentStatus.INSUFFICIENT:
            limitations.append("Оценка основана только на заявленном уровне")
        if status == AssessmentStatus.CONTRADICTORY:
            limitations.append("Требуется ручная проверка противоречия")

        assessments.append(CompetencyAssessment(
            employee_id=employee.id,
            competency=skill,
            level=level,
            status=status,
            evidence=evidence,
            contradictions=contradictions,
            limitations=limitations,
            follow_up=_suggest_follow_up(skill, status, evidence),
            rationale=_build_rationale(skill, level, evidence, status),
        ))

    return EmployeeEvaluation(
        employee_id=employee.id,
        full_name=employee.name,
        assessments=assessments,
    )
