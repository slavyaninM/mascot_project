"""Диагностика: что реально извлечено из проектов v1."""
from src.mascot.agents.data_layer.v1_loader import load_projects_v1


def main() -> None:
    for p in load_projects_v1():
        print(f"\n=== {p.id} | {p.name} ===")
        print(f"team_size: {p.team_size}")
        print("Извлечённые требования:")
        for r in p.requirements:
            print(f"  {r.skill:<12} min_level={r.min_level:.2f}  weight={r.weight:.1f}")
        print(f"Всего: {len(p.requirements)}")


if __name__ == "__main__":
    main()