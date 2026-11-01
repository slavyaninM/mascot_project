"""Тесты v1 data flow: загрузка, метрики, интеграция с pipeline."""
import inspect
from pathlib import Path

import pytest

from src.mascot.agents.analytics_layer.schemas import AssessmentStatus
from src.mascot.agents.analytics_layer.skill_evaluator import evaluate_employee
from src.mascot.agents.data_layer import v1_loader
from src.mascot.agents.decision_layer.optimizer import build_team
from src.mascot.pipelines.distribute_team import recommend_team
from src.mascot.agents.data_layer.v1_loader import (
    _extract_skills_from_text,
    _interpret_project,
    load_projects_v1,
)


# =============================================================================
# 1. Загрузка сотрудников v1
# =============================================================================

class TestLoadEmployeesV1:
    def test_loads_30_employees(self):
        employees, profiles = v1_loader.load_employees_v1()
        assert len(employees) == 30
        assert len(profiles) == 30

    def test_employee_ids_in_v1_format(self):
        employees, _ = v1_loader.load_employees_v1()
        ids = {e.id for e in employees}
        assert all(i.startswith("ТН-") for i in ids)
        assert "ТН-1001" in ids
        assert "ТН-1030" in ids

    def test_employees_have_skills_in_0_1(self):
        employees, _ = v1_loader.load_employees_v1()
        for e in employees:
            assert e.skills, f"У {e.id} нет навыков"
            for level in e.skills.values():
                assert 0.0 <= level <= 1.0, f"{e.id}: {level} вне [0,1]"


# =============================================================================
# 2. Профили и метрики
# =============================================================================

class TestLoadProfilesV1:
    def test_profiles_have_metrics(self):
        _, profiles = v1_loader.load_employees_v1()
        for p in profiles:
            assert p.metrics, f"У {p.employee_id} нет метрик"
            assert len(p.metrics) >= 3, f"{p.employee_id}: всего {len(p.metrics)} метрик"

    def test_metrics_have_provenance(self):
        """Каждая метрика несёт источник, период, sample_size, confidence."""
        _, profiles = v1_loader.load_employees_v1()
        for p in profiles:
            for m in p.metrics:
                assert m.source, f"{m.name}: пустой source"
                assert m.period_start and m.period_end
                assert m.sample_size >= 1
                assert 0.0 <= m.confidence <= 1.0


# =============================================================================
# 3. Загрузка проектов v1
# =============================================================================

class TestLoadProjectsV1:
    def test_loads_3_projects(self):
        projects = v1_loader.load_projects_v1()
        assert len(projects) == 3
        assert {p.id for p in projects} == {"PRJ-GAME-01", "PRJ-FIN-02", "PRJ-ECO-03"}

    def test_projects_have_requirements(self):
        projects = v1_loader.load_projects_v1()
        for p in projects:
            assert p.requirements, f"У {p.id} нет требований"
            assert p.team_size >= 1
            for r in p.requirements:
                assert 0.0 <= r.min_level <= 1.0
                assert r.weight > 0

    def test_project_requirements_not_generic_role_names(self):
        """В требованиях не должно быть названий ролей — только навыки."""
        bad = {"backend developer", "unity developer", "fullstack",
               "mobile developer", "qa automation", "qa manual", "frontend"}
        for p in v1_loader.load_projects_v1():
            for r in p.requirements:
                assert r.skill not in bad, f"{p.id}: роль '{r.skill}' в требованиях"


# =============================================================================
# 4. Метрики доходят до аналитики
# =============================================================================

class TestMetricsPropagate:
    def test_with_profile_has_more_evidence(self):
        employees, profiles = v1_loader.load_employees_v1()
        profiles_by_id = {p.employee_id: p for p in profiles}
        emp = employees[0]

        without = evaluate_employee(emp)
        with_profile = evaluate_employee(emp, profiles_by_id[emp.id])

        sum_without = sum(len(a.evidence) for a in without.assessments)
        sum_with = sum(len(a.evidence) for a in with_profile.assessments)
        assert sum_with > sum_without

    def test_git_sufficient_with_metrics(self):
        """С метриками из git у сотрудника появляется SUFFICIENT по git."""
        employees, profiles = v1_loader.load_employees_v1()
        profiles_by_id = {p.employee_id: p for p in profiles}
        emp = next(e for e in employees if e.id == "ТН-1001")
        result = evaluate_employee(emp, profiles_by_id[emp.id])

        git_a = result.get("git")
        assert git_a is not None
        assert git_a.status == AssessmentStatus.SUFFICIENT


# =============================================================================
# 5. Pipeline до оптимизатора
# =============================================================================

class TestPipelineV1:
    def _prepare(self):
        employees, profiles = v1_loader.load_employees_v1()
        profiles_by_id = {p.employee_id: p for p in profiles}
        evaluations = [
            evaluate_employee(e, profiles_by_id.get(e.id)) for e in employees
        ]
        return employees, profiles, evaluations

    def test_recommend_team_returns_report(self):
        employees, _, evaluations = self._prepare()
        project = v1_loader.load_projects_v1()[0]
        report = recommend_team(employees, project, evaluations)

        assert report.project_id == project.id
        assert report.selected_employee_ids
        assert len(report.selected_employee_ids) == project.team_size
        assert report.requirement_coverages
        assert report.explanation

    def test_team_size_respected(self):
        employees, _, evaluations = self._prepare()
        for project in v1_loader.load_projects_v1():
            report = build_team(project, evaluations, employees)
            assert len(report.selected_employee_ids) == project.team_size

    def test_match_scores_cover_all_members(self):
        employees, _, evaluations = self._prepare()
        project = v1_loader.load_projects_v1()[0]
        report = build_team(project, evaluations, employees)

        assert set(report.match_scores.keys()) == set(report.selected_employee_ids)
        for score in report.match_scores.values():
            assert 0.0 <= score <= 100.0


# =============================================================================
# 6. Ошибки загрузки
# =============================================================================

class TestLoadErrors:
    def test_missing_employees_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            v1_loader.load_employees_v1(path=tmp_path / "nope.json")

    def test_missing_projects_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            v1_loader.load_projects_v1(path=tmp_path / "nope.json")


# =============================================================================
# 7. Независимость от cwd и отсутствие legacy JSON
# =============================================================================

class TestPathAndLegacy:
    def test_data_dir_is_absolute(self):
        assert v1_loader.DATA_DIR.is_absolute()
        assert (v1_loader.DATA_DIR / "test_data_v1.json").exists()
        assert (v1_loader.DATA_DIR / "test_project_data_v1.json").exists()

    def test_v1_loader_does_not_touch_legacy_files(self):
        """Загрузчик v1 не читает старые employees.json / projects.json."""
        source = inspect.getsource(v1_loader)
        assert "test_data_v1.json" in source
        assert "test_project_data_v1.json" in source
        # Старые имена не должны встречаться даже в комментариях путей
        assert '"employees.json"' not in source
        assert '"projects.json"' not in source





def _make_raw(
    *,
    project_id: str = "PRJ-TEST",
    title: str = "Test",
    roles: list[str] | None = None,
    tech_spec: dict | None = None,
    frontend: list[str] | None = None,
) -> dict:
    """Минимальный v1-объект проекта."""
    return {
        "project_id": project_id,
        "meta": {"title": title, "description": ""},
        "customer_requirements": {
            "technical_specification": tech_spec or {},
            "frontend_and_ui": frontend or [],
        },
        "hr_staffing_implications": {
            "required_roles": roles or [],
        },
    }

# =============================================================================

# test_project_requirements

# =============================================================================
# 1. Отдельные технологии
# =============================================================================

class TestSingleSkills:
    def test_go_in_spec(self):
        project = _interpret_project(_make_raw(
            tech_spec={"backend": "Микросервисы на Go и Node.js"}
        ))
        assert "go" in {r.skill for r in project.requirements}

    def test_golang_in_spec(self):
        project = _interpret_project(_make_raw(
            tech_spec={"backend": "Сервис на Golang"}
        ))
        assert "go" in {r.skill for r in project.requirements}

    def test_unity_and_csharp(self):
        project = _interpret_project(_make_raw(
            tech_spec={"engine": "Unity 2023.x (LTS) / C#"}
        ))
        skills = {r.skill for r in project.requirements}
        assert "unity" in skills
        assert "csharp" in skills

    def test_flutter_and_dart_both(self):
        """Flutter и Dart — два отдельных навыка, если оба упомянуты."""
        project = _interpret_project(_make_raw(
            tech_spec={"mobile": "Flutter (язык Dart)"}
        ))
        skills = {r.skill for r in project.requirements}
        assert "flutter" in skills
        assert "dart" in skills


# =============================================================================
# 2. Отсутствие ложных срабатываний
# =============================================================================

class TestFalsePositives:
    def test_django_does_not_produce_go(self):
        """'django' не должен давать навык 'go' (нет границы слова)."""
        project = _interpret_project(_make_raw(
            tech_spec={"backend": "Python с Django REST Framework"}
        ))
        skills = {r.skill for r in project.requirements}
        assert "go" not in skills
        assert "django" in skills

    def test_javascript_does_not_produce_java(self):
        """'javascript' не должен давать навык 'java'."""
        project = _interpret_project(_make_raw(
            tech_spec={"frontend": "Только JavaScript и TypeScript"}
        ))
        skills = {r.skill for r in project.requirements}
        assert "java" not in skills
        assert "javascript" in skills

    def test_java_does_not_produce_javascript(self):
        """'java' не должен давать навык 'javascript'."""
        project = _interpret_project(_make_raw(
            tech_spec={"backend": "Enterprise на Java 21"}
        ))
        skills = {r.skill for r in project.requirements}
        assert "java" in skills
        assert "javascript" not in skills


# =============================================================================
# 3. Разделение источников: роли vs спецификация
# =============================================================================

class TestSourceSplit:
    def test_generic_backend_role_does_not_inject_skills(self):
        """
        'Backend Developer' без явных технологий НЕ должен добавлять
        python/java/go/sql/docker из старого ROLE_KEYWORDS.
        """
        project = _interpret_project(_make_raw(
            roles=["Backend Developer (Senior)"],
        ))
        skills = {r.skill for r in project.requirements}
        # Разрешено только testing, если роль QA. Здесь роль backend,
        # значит никаких автоматических навыков быть не должно.
        assert skills == set(), f"ожидали [], получили {skills}"

    def test_explicit_tech_in_role_is_extracted(self):
        """'Backend Developer со знанием Go' — Go извлекается."""
        project = _interpret_project(_make_raw(
            roles=["Backend Developer (Senior) со знанием Go"],
        ))
        skills = {r.skill for r in project.requirements}
        assert "go" in skills

    def test_qa_role_produces_testing(self):
        """Роль QA → навык testing (даже без упоминания технологий)."""
        project = _interpret_project(_make_raw(
            roles=["QA Engineers (Automation & Manual)"],
        ))
        skills = {r.skill for r in project.requirements}
        assert "testing" in skills


# =============================================================================
# 4. Разные проекты — разные требования
# =============================================================================

class TestRealProjectsDiffer:
    def test_three_projects_have_distinct_unique_skills(self):
        """
        Каждый из трёх v1-проектов должен иметь свои уникальные навыки:
        - CyberTaiga: go, unity, csharp
        - ГосНалог:   java, spring, rust
        - ЭкоСфера:   flutter, dart (или vue)
        """
        projects = {p.id: p for p in load_projects_v1()}

        cyber = {r.skill for r in projects["PRJ-GAME-01"].requirements}
        fin = {r.skill for r in projects["PRJ-FIN-02"].requirements}
        eco = {r.skill for r in projects["PRJ-ECO-03"].requirements}

        # Уникальные для CyberTaiga
        assert "go" in cyber
        assert "unity" in cyber
        assert "csharp" in cyber
        assert "go" not in fin
        assert "unity" not in fin

        # Уникальные для ГосНалога
        assert "java" in fin
        assert "spring" in fin
        assert "rust" in fin
        assert "java" not in cyber or "java" not in eco

        # Уникальные для ЭкоСферы
        assert "flutter" in eco
        assert "flutter" not in cyber
        assert "flutter" not in fin


# =============================================================================
# 5. Пустой проект — никаких выдуманных навыков
# =============================================================================

class TestEmptyProject:
    def test_empty_spec_and_roles_produce_no_requirements(self):
        project = _interpret_project(_make_raw())
        assert project.requirements == []


# =============================================================================
# 6. Хелперы
# =============================================================================

class TestExtractSkillsHelper:
    def test_csharp_variants(self):
        assert "csharp" in _extract_skills_from_text("Unity + C#")
        assert "csharp" in _extract_skills_from_text("Разработка на Csharp")
        assert "csharp" in _extract_skills_from_text("Стек: C# .NET")

    def test_nodejs_variants(self):
        assert "nodejs" in _extract_skills_from_text("Node.js")
        assert "nodejs" in _extract_skills_from_text("NodeJS")
        assert "nodejs" in _extract_skills_from_text("Node")

    def test_vue_variants(self):
        assert "vue" in _extract_skills_from_text("Vue.js")
        assert "vue" in _extract_skills_from_text("Nuxt.js")
        assert "vue" in _extract_skills_from_text("Vue")