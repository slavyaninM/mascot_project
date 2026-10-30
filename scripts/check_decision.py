from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee
from src.mascot.agents.data_layer.v1_loader import load_employees_v1, load_projects_v1
from src.mascot.pipelines.distribute_team import recommend_team


def main() -> None:
    employees, profiles = load_employees_v1()
    projects = load_projects_v1()
    profiles_by_id = {p.employee_id: p for p in profiles}
    evaluations = [evaluate_employee(e, profiles_by_id.get(e.id)) for e in employees]

    for project in projects:
        report = recommend_team(employees, project, evaluations)

        print(f"\n=== {project.name} ===")
        print(f"Статус: {report.status.value}")
        print(f"Команда: {', '.join(report.selected_employee_names) or 'пусто'}")
        print(f"Взвешенное покрытие: {report.weighted_coverage:.2f}")
        print(f"Взвешенный дефицит: {report.weighted_deficit:.2f}")
        print(f"Покрыто: {', '.join(report.covered_requirements) or '—'}")
        print(f"Не покрыто: {', '.join(report.missing_requirements) or '—'}")

        if report.risks:
            print("\nРиски:")
            for r in report.risks:
                print(f"  [{r.severity}] {r.description}")

        if report.follow_ups:
            print("\nДоп. проверки:")
            for f in report.follow_ups:
                print(f"  • {f.employee_id or '—'} / {f.competency or '—'}: {f.reason}")

        # if report.infeasibility_reasons:
        #     print("\nПричины невозможности:")
        #     for reason in report.infeasibility_reasons:
        #         print(f"  — {reason}")


        print(f"\nОбъяснение: {report.explanation}")


if __name__ == "__main__":
    main()