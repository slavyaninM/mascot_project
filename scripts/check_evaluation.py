from src.mascot.agents.data_layer.v1_loader import load_employees_v1
from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee


def main() -> None:
    employees, profiles = load_employees_v1()
    profiles_by_id = {p.employee_id: p for p in profiles}

    print(f"Загружено {len(employees)} сотрудников и {len(profiles)} профилей")
    # Для демо оцениваем всех сотрудников
    for emp in employees:
        evaluation = evaluate_employee(emp, profiles_by_id.get(emp.id))
        print(f"\n=== {evaluation.full_name} ({evaluation.employee_id}) ===")
        for a in evaluation.assessments:
            print(f"  {a.competency}: level={a.level:.2f}, status={a.status.value}")
            for c in a.contradictions:
                print(f"    ! {c.description}")
            for f in a.follow_up:
                print(f"    → {f}")


if __name__ == "__main__":
    main()