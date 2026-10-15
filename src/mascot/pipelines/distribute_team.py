from src.mascot.storage.models import Employee, Project, TeamRecommendation


def match_team(staff: list[Employee], project: Project) -> TeamRecommendation:
    """Подбирает команду под требования проекта."""

    #оставляем только тех кого можно брать
    free_staff = [person for person in staff if person.available]
    team: list[Employee] = []  
    covered = []    #закрытые навыки
    gaps = []   #не закрытые навыки
    slots_left = project.team_size  #сколько еще человек можно взять

    #добавить сортировку по весу навыков

    # требования по отсортированным навыкам
    for req in project.requirements:
        candidates = [
            person
            for person in free_staff
            if person.skills.get(req.skill, 0) >= req.min_level
        ]

        if not candidates:
            gaps.append(req.skill)
            continue

        best = max(
            candidates,
            key=lambda person: person.skills.get(req.skill, 0),
        )

        if best not in team and slots_left > 0:
            team.append(best)
            slots_left -= 1

        if best in team:
            covered.append(req.skill)

        

    parts = [f"Для проекта «{project.name}» выбрано {len(team)} человек."]

    if covered:
        parts.append(f"Закрыты навыки: {', '.join(covered)}.")
    else:
        parts.append("Ни одно требование не закрыто.")

    if gaps:
        parts.append(f"Не хватает навыков: {', '.join(gaps)}.")

    return TeamRecommendation(
        project_id=project.id,
        selected_employees=team,
        covered_requirements=covered,
        missing_requirements=gaps,
        explanation=" ".join(parts),
    )