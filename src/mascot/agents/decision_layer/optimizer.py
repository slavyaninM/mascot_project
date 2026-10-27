import itertools
import logging
from math import comb

from src.mascot.agents.analytics_layer.schemas import (
    AssessmentStatus,
    EmployeeEvaluation,
)
from src.mascot.storage.models import Employee, Project, ProjectRequirement

from .schemas import (
    FollowUp,
    ReliabilityLevel,
    RequirementCoverage,
    RequirementStatus,
    TeamAlternative,
    TeamDecisionReport,
    TeamRisk,
    TeamStatus,
)

logger = logging.getLogger("mascot.optimizer")

# --- Пороги и веса (потом в config) ---
MAX_BRUTE_FORCE_COMBOS = 10_000
PENALTY_UNKNOWN = 0.3
PENALTY_INSUFFICIENT = 0.1
PENALTY_CONTRADICTORY = 0.2
TOP_ALTERNATIVES = 3


# =============================================================================
# Вспомогательные функции
# =============================================================================

def _status_to_reliability(status: AssessmentStatus) -> ReliabilityLevel:
    if status == AssessmentStatus.SUFFICIENT:
        return ReliabilityLevel.HIGH
    if status == AssessmentStatus.CONTRADICTORY:
        return ReliabilityLevel.LOW
    if status == AssessmentStatus.INSUFFICIENT:
        return ReliabilityLevel.LOW
    return ReliabilityLevel.UNKNOWN


def _get_effective_level(
    employee_id: str,
    skill: str,
    evaluations_by_id: dict[str, EmployeeEvaluation],
    employees_by_id: dict[str, Employee],
) -> tuple[float | None, ReliabilityLevel, list[str]]:
    """
    Возвращает (уровень, надёжность, заметки) для пары (сотрудник, навык).

    Приоритет:
    1. Оценка из аналитического слоя (assessment).
    2. Заявленный уровень в Employee.skills (fallback).
    3. None.
    """
    notes: list[str] = []
    evaluation = evaluations_by_id.get(employee_id)

    if evaluation:
        assessment = evaluation.get(skill)
        if assessment and assessment.status != AssessmentStatus.NO_DATA:
            reliability = _status_to_reliability(assessment.status)
            if assessment.status == AssessmentStatus.INSUFFICIENT:
                notes.append(f"Недостаточно данных для достоверной оценки {skill}")
            if assessment.status == AssessmentStatus.CONTRADICTORY:
                notes.append(f"Противоречивые данные по {skill}")
            return float(assessment.level), reliability, notes

    # Fallback: сырое значение из Employee.skills
    employee = employees_by_id.get(employee_id)
    if employee:
        raw = employee.skills.get(skill)
        if raw is not None:
            notes.append(f"Уровень {skill} взят из заявленного, без подтверждения")
            return float(raw), ReliabilityLevel.MEDIUM, notes

    return None, ReliabilityLevel.UNKNOWN, notes


def _evaluate_requirement_for_team(
    team_ids: list[str],
    requirement: ProjectRequirement,
    evaluations_by_id: dict[str, EmployeeEvaluation],
    employees_by_id: dict[str, Employee],
) -> RequirementCoverage:
    """Покрытие одного требования данной командой."""
    best_level: float | None = None
    best_emp_id: str | None = None
    best_reliability = ReliabilityLevel.UNKNOWN
    all_unknown = True
    notes: list[str] = []

    for emp_id in team_ids:
        level, reliability, emp_notes = _get_effective_level(
            emp_id, requirement.skill, evaluations_by_id, employees_by_id
        )
        if level is None:
            continue
        all_unknown = False
        if best_level is None or level > best_level:
            best_level = level
            best_emp_id = emp_id
            best_reliability = reliability
            notes = emp_notes

    # Определяем статус
    if all_unknown:
        status = RequirementStatus.UNKNOWN
        coverage_ratio = 0.0
        deficit = float(requirement.min_level)
    elif best_level is not None and best_level >= requirement.min_level:
        status = RequirementStatus.COVERED
        coverage_ratio = 1.0
        deficit = 0.0
    elif best_level and best_level > 0:
        status = RequirementStatus.PARTIAL
        coverage_ratio = min(1.0, best_level / requirement.min_level)
        deficit = max(0.0, requirement.min_level - best_level)
    else:
        status = RequirementStatus.UNCOVERED
        coverage_ratio = 0.0
        deficit = float(requirement.min_level)

    covered_by_name = None
    if best_emp_id:
        emp = employees_by_id.get(best_emp_id)
        covered_by_name = emp.name if emp else None

    return RequirementCoverage(
        skill=requirement.skill,
        min_level=requirement.min_level,
        weight=requirement.weight,
        achieved_level=best_level,
        coverage_ratio=coverage_ratio,
        deficit=deficit,
        status=status,
        covered_by_employee_id=best_emp_id,
        covered_by_name=covered_by_name,
        covered_by_reliability=best_reliability,
        reliability_notes=notes,
    )


def _score_team(
    team_ids: list[str],
    project: Project,
    evaluations_by_id: dict[str, EmployeeEvaluation],
    employees_by_id: dict[str, Employee],
) -> tuple[float, float, float, float, list[RequirementCoverage]]:
    """
    Возвращает (score, weighted_coverage, weighted_deficit, penalty, coverages).
    Формулы — см. документацию выше.
    """
    coverages = [
        _evaluate_requirement_for_team(team_ids, req, evaluations_by_id, employees_by_id)
        for req in project.requirements
    ]

    total_weight = sum(r.weight for r in project.requirements) or 1.0
    weighted_coverage = sum(
        r.weight * c.coverage_ratio
        for r, c in zip(project.requirements, coverages)
    ) / total_weight
    weighted_deficit = sum(r.weight * c.deficit for r, c in zip(project.requirements, coverages))

    # штрафы
    n_unknown = sum(1 for c in coverages if c.status == RequirementStatus.UNKNOWN)
    n_insufficient = sum(
        1 for c in coverages if c.covered_by_reliability == ReliabilityLevel.MEDIUM
    )
    n_contradictory = sum(
        1 for c in coverages
        if c.covered_by_reliability == ReliabilityLevel.LOW and c.status == RequirementStatus.COVERED
    )
    n_reqs = len(project.requirements) or 1
    penalty = (
        PENALTY_UNKNOWN * n_unknown / n_reqs
        + PENALTY_INSUFFICIENT * n_insufficient / n_reqs
        + PENALTY_CONTRADICTORY * n_contradictory / n_reqs
    )

    score = weighted_coverage - penalty
    return score, weighted_coverage, weighted_deficit, penalty, coverages


# =============================================================================
# Основной алгоритм
# =============================================================================

def build_team(
    project: Project,
    evaluations: list[EmployeeEvaluation],
    employees: list[Employee],
) -> TeamDecisionReport:
    """Собирает оптимальную команду и полный отчёт."""
    employees_by_id = {e.id: e for e in employees}
    evaluations_by_id = {e.employee_id: e for e in evaluations}

    #1 Жёсткие ограничения: только доступные
    available = [e for e in employees if e.available]
    available_ids = [e.id for e in available]

    infeasibility_reasons: list[str] = []
    limitations: list[str] = []
    risks: list[TeamRisk] = []

    #2 Проверка infeasible
    if not available:
        return _make_infeasible_report(
            project,
            reason="Нет доступных сотрудников",
            risks=risks,
        )

    if project.team_size <= 0:
        return _make_infeasible_report(
            project,
            reason=f"Некорректный размер команды: {project.team_size}",
            risks=risks,
        )

    #3 Размер команды
    target_size = min(project.team_size, len(available_ids))
    if project.team_size > len(available_ids):
        risks.append(TeamRisk(
            type="size",
            severity="warning",
            description=(
                f"Запрошено {project.team_size}, доступно {len(available_ids)}. "
                f"Команда будет неполной."
            ),
        ))
        limitations.append(
            f"Команда собрана размером {target_size} вместо {project.team_size}"
        )

    #4 Перебор или жадный
    total_combos = comb(len(available_ids), target_size)
    if total_combos <= MAX_BRUTE_FORCE_COMBOS:
        candidates = list(itertools.combinations(available_ids, target_size))
    else:
        logger.info(
            f"C({len(available_ids)}, {target_size}) = {total_combos} > "
            f"{MAX_BRUTE_FORCE_COMBOS} — используем жадный алгоритм"
        )
        candidates = [_greedy_team(available_ids, target_size, project, evaluations_by_id, employees_by_id)]

    #5 Оценка всех вариантов
    scored: list[tuple[float, tuple[str, ...], list[RequirementCoverage]]] = []
    for team_ids in candidates:
        score, _, _, _, coverages = _score_team(
            list(team_ids), project, evaluations_by_id, employees_by_id
        )
        scored.append((score, team_ids, coverages))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_team, best_coverages = scored[0]

    #6 Альтернативы (топ 3 без победителя)
    alternatives = []
    for alt_score, alt_ids, alt_coverages in scored[1:1 + TOP_ALTERNATIVES]:
        wcov = sum(
            r.weight * c.coverage_ratio
            for r, c in zip(project.requirements, alt_coverages)
        ) / (sum(r.weight for r in project.requirements) or 1.0)
        wdef = sum(r.weight * c.deficit for r, c in zip(project.requirements, alt_coverages))
        status = _determine_status(alt_coverages, project)
        alternatives.append(TeamAlternative(
            selected_employee_ids=list(alt_ids),
            weighted_coverage=wcov,
            total_deficit=wdef,
            status=status,
        ))

    #7 Сводные метрики и диагностика
    total_weight = sum(r.weight for r in project.requirements) or 1.0
    weighted_coverage = sum(
        r.weight * c.coverage_ratio
        for r, c in zip(project.requirements, best_coverages)
    ) / total_weight
    weighted_deficit = sum(r.weight * c.deficit for r, c in zip(project.requirements, best_coverages))

    covered = [c.skill for c in best_coverages if c.status == RequirementStatus.COVERED]
    missing = [
        c.skill for c in best_coverages
        if c.status in (RequirementStatus.UNCOVERED, RequirementStatus.PARTIAL)
    ]
    covered_ratio_simple = len(covered) / len(best_coverages) if best_coverages else 0.0

    # Риски по покрытиям
    for c in best_coverages:
        if c.status == RequirementStatus.UNKNOWN:
            risks.append(TeamRisk(
                type="unknown_data",
                severity="warning",
                description=f"Нет данных по навыку {c.skill} ни у кого в команде",
                related_skills=[c.skill],
            ))
        elif c.status == RequirementStatus.UNCOVERED:
            risks.append(TeamRisk(
                type="uncovered",
                severity="error",
                description=f"Требование {c.skill} >= {c.min_level} не покрыто",
                related_skills=[c.skill],
            ))
        elif c.status == RequirementStatus.PARTIAL:
            risks.append(TeamRisk(
                type="uncovered",
                severity="warning",
                description=(
                    f"Частичное покрытие {c.skill}: {c.achieved_level}/{c.min_level} "
                    f"(дефицит {c.deficit})"
                ),
                related_skills=[c.skill],
            ))
        if c.covered_by_reliability in (ReliabilityLevel.MEDIUM, ReliabilityLevel.LOW):
            risks.append(TeamRisk(
                type="low_confidence",
                severity="warning",
                description=(
                    f"Оценка {c.skill} у {c.covered_by_name} имеет низкую надёжность"
                ),
                related_skills=[c.skill],
                related_employee_ids=[c.covered_by_employee_id] if c.covered_by_employee_id else [],
            ))

    # Follow-ups
    follow_ups: list[FollowUp] = []
    for c in best_coverages:
        if c.covered_by_reliability == ReliabilityLevel.LOW and c.covered_by_employee_id:
            follow_ups.append(FollowUp(
                employee_id=c.covered_by_employee_id,
                competency=c.skill,
                reason="Низкая надёжность оценки, требуется доп. проверка",
            ))
        if c.status == RequirementStatus.UNKNOWN:
            follow_ups.append(FollowUp(
                competency=c.skill,
                reason="Нет данных ни у кого в команде",
            ))

    status = _determine_status(best_coverages, project)
    selected_names = [
        employees_by_id[i].name for i in best_team if i in employees_by_id
    ]
    explanation = _build_explanation(
        project, best_team, selected_names, best_coverages, status, risks, follow_ups
    )

    return TeamDecisionReport(
        project_id=project.id,
        project_name=project.name,
        team_size_limit=project.team_size,
        selected_employee_ids=list(best_team),
        selected_employee_names=selected_names,
        requirement_coverages=best_coverages,
        weighted_coverage=weighted_coverage,
        weighted_deficit=weighted_deficit,
        coverage_ratio_simple=covered_ratio_simple,
        covered_requirements=covered,
        missing_requirements=missing,
        risks=risks,
        follow_ups=follow_ups,
        alternatives=alternatives,
        infeasibility_reasons=infeasibility_reasons,
        limitations=limitations,
        status=status,
        explanation=explanation,
    )


def _greedy_team(
    available_ids: list[str],
    target_size: int,
    project: Project,
    evaluations_by_id: dict[str, EmployeeEvaluation],
    employees_by_id: dict[str, Employee],
) -> tuple[str, ...]:
    """Жадный выбор команды — используется при большом пространстве вариантов."""
    selected: list[str] = []
    remaining = list(available_ids)
    for _ in range(target_size):
        best_id, best_score = None, -1.0
        for emp_id in remaining:
            score, *_ = _score_team(
                selected + [emp_id], project, evaluations_by_id, employees_by_id
            )
            if score > best_score:
                best_score = score
                best_id = emp_id
        if best_id is None:
            break
        selected.append(best_id)
        remaining.remove(best_id)
    return tuple(selected)


def _determine_status(
    coverages: list[RequirementCoverage],
    project: Project,
) -> TeamStatus:
    if not coverages:
        return TeamStatus.INFEASIBLE
    covered = sum(1 for c in coverages if c.status == RequirementStatus.COVERED)
    if covered == len(coverages) and all(
        c.covered_by_reliability == ReliabilityLevel.HIGH for c in coverages
    ):
        return TeamStatus.OPTIMAL
    if covered == 0:
        return TeamStatus.INFEASIBLE
    return TeamStatus.DEGRADED


def _make_infeasible_report(
    project: Project,
    reason: str,
    risks: list[TeamRisk],
) -> TeamDecisionReport:
    return TeamDecisionReport(
        project_id=project.id,
        project_name=project.name,
        team_size_limit=project.team_size,
        selected_employee_ids=[],
        selected_employee_names=[],
        requirement_coverages=[],
        weighted_coverage=0.0,
        weighted_deficit=sum(r.weight * r.min_level for r in project.requirements),
        coverage_ratio_simple=0.0,
        covered_requirements=[],
        missing_requirements=[r.skill for r in project.requirements],
        risks=risks,
        follow_ups=[],
        alternatives=[],
        infeasibility_reasons=[reason],
        limitations=[],
        status=TeamStatus.INFEASIBLE,
        explanation=f"Команду собрать невозможно: {reason}.",
    )


def _build_explanation(
    project: Project,
    team_ids: tuple[str, ...],
    names: list[str],
    coverages: list[RequirementCoverage],
    status: TeamStatus,
    risks: list[TeamRisk],
    follow_ups: list[FollowUp],
) -> str:
    parts = [
        f"Для проекта «{project.name}» подобрана команда из {len(team_ids)}: "
        f"{', '.join(names) if names else 'нет'}."
    ]
    covered = [c.skill for c in coverages if c.status == RequirementStatus.COVERED]
    partial = [c.skill for c in coverages if c.status == RequirementStatus.PARTIAL]
    unknown = [c.skill for c in coverages if c.status == RequirementStatus.UNKNOWN]
    uncovered = [c.skill for c in coverages if c.status == RequirementStatus.UNCOVERED]

    if covered:
        parts.append(f"Полностью покрыто: {', '.join(covered)}.")
    if partial:
        parts.append(f"Частично: {', '.join(partial)}.")
    if uncovered:
        parts.append(f"Не покрыто: {', '.join(uncovered)}.")
    if unknown:
        parts.append(f"Без данных: {', '.join(unknown)}.")

    if status == TeamStatus.OPTIMAL:
        parts.append("Статус: оптимальный состав.")
    elif status == TeamStatus.DEGRADED:
        parts.append("Статус: рабочий состав с ограничениями.")
    else:
        parts.append("Статус: команда не собрана.")

    if follow_ups:
        parts.append(f"Рекомендаций доп. проверок: {len(follow_ups)}.")
    return " ".join(parts)