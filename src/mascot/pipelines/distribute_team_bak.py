from src.mascot.storage.models import Employee, Project, TeamRecommendation


def match_team(staff: list[Employee], project: Project) -> TeamRecommendation:
    """Подбирает команду под требования проекта.
     Логика:
    1 Оставляем только доступных сотрудников (available=True).
    2 Идём по требованиям проекта - от важных (большой weight) к менее важным.
    3 На каждое требование ищем лучшего кандидата по уровню навыка.
    4 Если кандидат уже в команде -  требование считается закрытым.
    5 Если кандидат новый и есть свободное место - берём его в команду.
    6 Если места нет или кандидатов нет - требование уходит в gaps (пробелы).
    
    """

    #оставляем только тех кого можно брать
    free_staff = [person for person in staff if person.available]
    team: list[Employee] = []  
    covered = []    #закрытые навыки
    gaps = []   #не закрытые навыки
    slots_left = project.team_size  #сколько еще человек можно взять

    #добавить сортировку по весу навыков

    sorted_requirements = sorted(
        project.requirements,
        key=lambda req: req.weight,
        reverse=True,
    )

    # требования
    for req in project.requirements:
        candidates = [
            person
            for person in free_staff
            if person.skills.get(req.skill, 0) >= req.min_level
        ]
        # если никто не подходит
        if not candidates:
            gaps.append(req.skill)
            continue
        
        best = max(
            candidates,
            key=lambda person: person.skills.get(req.skill, 0),
        )

        if best in team:
            covered.append(req.skill)

        elif slots_left > 0:
            team.append(best)
            slots_left -= 1
            covered.append(req.skill)

        else:
        #    лучший новый но места закончились - требование закрыто
            gaps.append(req.skill)

        
    # отчет текстом что произошло, заготовка для trust_layer
    parts = [f"Для проекта «{project.name}» выбрано {len(team)} человек."]

    if covered:
        parts.append(f"Закрыты навыки: {', '.join(covered)}.")
    else:
        parts.append("Ни одно требование не закрыто.")

    if gaps:
        parts.append(f"Не хватает навыков: {', '.join(gaps)}.")

    return TeamRecommendation(
        project_id=project.id,
        selected_employee_ids=[person.id for person in team],   # ← было selected_employees=team
        covered_requirements=covered,
        missing_requirements=gaps,
        explanation=" ".join(parts),
    )