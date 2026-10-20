import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text


from src.mascot.storage.models import EmployeeProfile


class BenchmarkerAgent:
    def __init__(self, min_cohort_size: int = 3):
        """
        Инициализация бенчмаркера.
        min_cohort_size: Минимальное количество людей в когорте для внутреннего сравнения.
        """
        self.min_cohort_size = min_cohort_size

        # рыночные эталоны (внешний бенчмарк) на случай, если когорта в БД пуста
        self.market_defaults = {
            "git": {"commits_count": 20, "pr_opened": 5},
            "jira": {"tasks_closed": 10, "bugs_count": 2, "avg_time_hours": 8.0},
            "lms": {"courses_completed": 1, "avg_score": 75.0}
        }

    def _load_cohort_from_db(self, db: Session,
                             role: str,
                             grade: str,
                             period: str) -> List[Dict[str, Any]]:
        """
        Выгружает профили сотрудников за конкретный месяц.
        """
        query = text("""
            SELECT metrics FROM employee_profiles 
            WHERE role = :role AND grade = :grade
              AND evaluation_period = :period
        """)
        result = db.execute(query, {
            "role": role,
            "grade": grade,
            "period": period
        }).fetchall()

        cohort_metrics = [row[0] for row in result if row[0] is not None]

        return cohort_metrics

    def _calculate_metrics_comparison(
            self,
            current_metrics: Dict[str, Any],
            reference_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Внутренний движок подсчета дельт и статусов на Pandas.
        """
        comparison_results = {}

        for system_name, system_metrics in current_metrics.items():
            for metric_key, employee_value in system_metrics.items():
                column_name = f"{system_name}.{metric_key}"

                # Получаем среднее значение по когорте/рынку
                if not reference_df.empty and column_name in reference_df.columns:
                    mean_value = reference_df[column_name].mean()
                else:
                    # Если в DataFrame нет такой колонки, берем дефолт из рыночных данных
                    mean_value = self.market_defaults.get(system_name, {}).get(metric_key, 0.0)

                # Защита от деления на ноль
                if mean_value > 0:
                    delta_pct = round(((employee_value - mean_value) / mean_value) * 100, 1)
                else:
                    delta_pct = 0.0 # отклонения нет, так как сравнивать не с чем


                inverse_metrics = ["jira.bugs_count",
                                   "jira.avg_time_hours",
                                   "git.rejected_prs",
                                   "git.failed_pipelines",
                                   "jira.reopened_tasks",
                                   "jira.overdue_tasks"]

                if column_name in inverse_metrics:
                    # Если время или баги НИЖЕ среднего — это ХОРОШО (above_average)
                    if delta_pct < -10:
                        status = "above_average"
                    elif delta_pct > 10:
                        status = "below_average"
                    else:
                        status = "average"
                else:
                    # Стандартная логика: если метрика ВЫШЕ среднего — это ХОРОШО
                    if delta_pct > 10:
                        status = "above_average"
                    elif delta_pct < -10:
                        status = "below_average"
                    else:
                        status = "average"

                comparison_results[column_name] = {
                    "employee_value": float(employee_value),
                    "cohort_mean": round(float(mean_value), 2),
                    "delta_percent": float(delta_pct),
                    "status": status
                }

        return comparison_results

    def calculate_benchmarks(self, current_profile: EmployeeProfile,
                             db: Session,
                             period: str) -> EmployeeProfile:
        """
        Основной метод агента. Принимает Pydantic-профиль, обогащает его блоком benchmark и возвращает обратно.
        """
        role = current_profile.role
        grade = current_profile.grade

        # 1. Попытка загрузить внутреннюю когорту из БД
        raw_cohort = self._load_cohort_from_db(db, role, grade, period=period)

        # Разворачиваем вложенные JSON-метрики когорты в плоский Pandas DataFrame для удобства расчетов
        if raw_cohort:
            cohort_df = pd.json_normalize(raw_cohort)
        else:
            cohort_df = pd.DataFrame()

        # 2. Определяем режим: внутренний (global) или рыночный (рыночные дефолты)
        if not cohort_df.empty and len(cohort_df) >= self.min_cohort_size:
            compared_at_global = True
            cohort_size = len(cohort_df)
            reference_df = cohort_df
        else:
            compared_at_global = False
            cohort_size = 0
            # Создаем фейковый DataFrame из одной строки рыночных эталонов для унификации математики
            market_flat = {}
            for sys, metrics in self.market_defaults.items():
                for k, v in metrics.items():
                    market_flat[f"{sys}.{k}"] = v
            reference_df = pd.DataFrame([market_flat])

        # 3. Запускаем расчет сравнения метрик
        metrics_comparison = self._calculate_metrics_comparison(
            current_metrics=current_profile.metrics,
            reference_df=reference_df
        )

        # 4. Перезаписываем поле benchmark в Pydantic-модели
        current_profile.benchmark = {
            "cohort_size": cohort_size,
            "compared_at_global": compared_at_global,
            "metrics_comparison": metrics_comparison
        }

        return current_profile
