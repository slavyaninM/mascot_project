import uuid
import logging
import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.mascot.core.base_agent import BaseAgent
from src.mascot.core.message import AgentMessage


class BenchmarkerAgent(BaseAgent):
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

        self.metric_weights = {
            "git.commits_count": 1.5,
            "git.failed_pipelines": 2.0,
            "jira.tasks_closed": 1.0,
            "jira.bugs_count": 2.5,
            "jira.avg_time_hours": 1.5,
            "lms.avg_score": 1.0
        }


        self.inverse_metrics = {
            "jira.bugs_count",
            "jira.avg_time_hours",
            "git.rejected_prs",
            "git.failed_pipelines",
            "jira.reopened_tasks",
            "jira.overdue_tasks"
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
                    # Если время или баги НИЖЕ среднего — это ХОРОШО
                    if delta_pct < -10:
                        status = "above_average"
                    elif delta_pct > 10:
                        status = "below_average"
                    else:
                        status = "average"
                else:
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

    def _calculate_benchmarks_engine(self, current_metrics: Dict[str, Any], reference_df: pd.DataFrame) -> Dict[
        str, Any]:
        """
        Внутренний математический движок.
        Реализует детерминированный расчет Be и Delta_m_adj (cite: 1).
        """
        metrics_comparison = {}
        total_weighted_delta = 0.0
        total_weight = 0.0

        for system_name, system_metrics in current_metrics.items():
            for metric_key, employee_value in system_metrics.items():
                column_name = f"{system_name}.{metric_key}"
                v_m = self.metric_weights.get(column_name, 1.0)  # Вес v_m (по умолчанию 1.0)

                # 1. Получаем среднее значение x_m (когорта или рынок) (cite: 1)
                if not reference_df.empty and column_name in reference_df.columns:
                    x_m = reference_df[column_name].mean()
                else:
                    x_m = self.market_defaults.get(system_name, {}).get(metric_key, 0.0)

                x_im = float(employee_value)

                # 2. Расчет отклонения Delta_m
                if x_m != 0:
                    delta_m = (x_im - x_m) / x_m
                else:
                    delta_m = 0.0

                # 3. Корректировка знака для инвертированных метрик
                if column_name in self.inverse_metrics:
                    delta_m_adj = -delta_m  # Инвертируем (cite: 1)
                else:
                    delta_m_adj = delta_m

                # Накапливаем значения для итогового индекса Be
                total_weighted_delta += v_m * delta_m_adj
                total_weight += v_m

                metrics_comparison[column_name] = {
                    "employee_value": x_im,
                    "cohort_mean": round(float(x_m), 2),
                    "delta_adjusted": round(delta_m_adj, 4)
                }

        # 4. Расчет итогового индекса Be
        if total_weight > 0:
            be = 100 * (total_weighted_delta / total_weight)
        else:
            be = 0.0

        # 5. Определение качественного статуса по порогам
        if be >= 10:
            status = "above_average"
        elif be <= -10:
            status = "below_average"
        else:
            status = "average"

        return {
            "benchmark_index": round(be, 2),
            "status": status,  # cite: 1
            "metrics_comparison": metrics_comparison
        }

    async def process(self, message: AgentMessage) -> AgentMessage | None:
        """Точка входа агента при работе через асинхронную шину."""
        if message.message_type != "RUN_BENCHMARKING":
            return None

        employee_id = message.payload.get("employee_id")
        role = message.payload.get("role")
        grade = message.payload.get("grade")
        period = message.payload.get("period")
        current_metrics = message.payload.get("metrics")  # {'git': {...}, 'jira': {...}}

        # Передаем сессию БД из инжектора или контекста (в прод-версии)
        db: Session = message.payload.get("db_session")

        self.log_action(f"Запуск детерминированного бенчмаркинга для сотрудника {employee_id}")

        try:
            # 1. Загрузка когорты
            raw_cohort = self._load_cohort_from_db(db, role, grade, period=period)
            cohort_df = pd.json_normalize(raw_cohort) if raw_cohort else pd.DataFrame()

            # 2. Выбор режима (когорта или рынок) (cite: 1)
            if not cohort_df.empty and len(cohort_df) >= self.min_cohort_size:
                compared_at_global = True
                cohort_size = len(cohort_df)
                reference_df = cohort_df
            else:
                compared_at_global = False  # Переключение на рыночные эталоны (cite: 1)
                cohort_size = 0
                market_flat = {f"{sys}.{k}": v for sys, metrics in self.market_defaults.items() for k, v in
                               metrics.items()}
                reference_df = pd.DataFrame([market_flat])

            # 3. Вычисление
            analysis = self._calculate_benchmarks_engine(current_metrics, reference_df)

            # 4. Формирование ответа
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver=message.sender,
                message_type="BENCHMARK_PROCESSED",
                payload={
                    "employee_id": employee_id,
                    "benchmark": {
                        "cohort_size": cohort_size,
                        "compared_at_global": compared_at_global,
                        "benchmark_index": analysis["benchmark_index"],
                        "status": analysis["status"],  # cite: 1
                        "metrics_comparison": analysis["metrics_comparison"]
                    }
                }
            )

        except Exception as e:
            logger.error(f"Сбой бенчмаркинга для сотрудника {employee_id}: {e}", exc_info=True)
            return None
