from src.mascot.agents.data_layer.integrator import load_employees, load_projects
from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee


def main():
    employees = load_employees()
    projects = load_projects()

    # Для демо оцениваем всех сотрудников
    for emp in employees:
        evaluation = evaluate_employee(emp)
        print(f"\n=== {evaluation.full_name} ({evaluation.employee_id}) ===")
        for a in evaluation.assessments:
            print(f"  {a.competency}: level={a.level}, status={a.status.value}")
            if a.contradictions:
                for c in a.contradictions:
                    print(f"    ! {c.description}")
            if a.follow_up:
                for f in a.follow_up:
                    print(f"    → {f}")


if __name__ == "__main__":
    main()