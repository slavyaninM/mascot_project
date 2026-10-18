import uuid
import logging
import asyncio
from typing import Dict, Any
from src.mascot.core.base_agent import BaseAgent
from src.mascot.core.message import AgentMessage
from src.mascot.llm.client import LLMClient

logger = logging.getLogger("mascot.evaluator")


class EvaluatorAgent(BaseAgent):
    """
    Главный аналитический агент-оркестратор (Консолидатор результатов).
    Управляет внутренними модулями ("суб-агентами") оценки hard/soft скиллов.
    """

    def __init__(self, name: str, agent_type: str, message_bus, llm_client: LLMClient):
        super().__init__(name, agent_type, message_bus)
        self.llm = llm_client

    async def process(self, message: AgentMessage) -> AgentMessage | None:
        # Принимаем валидированные данные сотрудников от слоя данных
        if message.message_type != "VALIDATED_TRACE":
            return None

        employee_id = message.payload.get("employee_id")
        self.log_action(f"Запуск модульного конвейера комплексной оценки для: {employee_id}")

        try:
            # 1. Запуск детерминированного скрипта KPI/OKR (Расчет математики)
            kpi_results = self._sub_agent_kpi_okr(message.payload)

            # 2. Запуск ИИ-модулей параллельно (для экономии времени)
            # В реальной системе здесь будут асинхронные запросы к LLM и ChromaDB
            tasks =[ self._sub_agent_hard_skills(message.payload),
            self._sub_agent_spec_requirements(message.payload),
            self._sub_agent_lms_trajectory(message.payload),
            self._sub_agent_feedback_360(message.payload),
            self._sub_agent_star(message.payload)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            hard_skills = results[0]
            spec_requirements = results[1]
            lms_trajectory = results[2]
            feedback_360 = results[3]
            star_method = results[4]


            # 3. Консолидация результатов через LLM в единый структурированный JSON
            final_profile = await self._sub_agent_consolidator(
                employee_id, hard_skills, spec_requirements, kpi_results, lms_trajectory, feedback_360, star_method
            )

            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver="broadcast",
                message_type="EVALUATION_SUCCESS",
                payload={"employee_id": employee_id, "profile": final_profile}
            )

        except Exception as e:
            logger.error(f"Сбой модульной оценки сотрудника {employee_id}: {e}", exc_info=True)
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver="broadcast",
                message_type="EVALUATION_ERROR",
                payload={"employee_id": employee_id, "error": str(e)}
            )

    # --- ВНУТРЕННИЕ СУБ-АГЕНТЫ (МОДУЛИ) ---

    async def _sub_agent_hard_skills(self, data: Dict[str, Any]) -> str:
        """Модуль 1 (LLM): Анализ тех. стека, сложности задач и кода."""
        prompt = f"Проанализируй техническую сложность и стек на основе данных: {data}"
        return await self.llm.generate(prompt, system_prompt="Ты AI-эксперт по оценке Hard-Skills.")

    async def _sub_agent_spec_requirements(self, data: Dict[str, Any]) -> str:
        """Модуль 2 (LLM + ChromaDB): Сопоставление с матрицей компетенций, слепые зоны."""
        # Здесь в будущем появится поиск по векторной базе ChromaDB
        prompt = f"Сравни навыки сотрудника с эталонной матрицей роли. Данные: {data}"
        return await self.llm.generate(prompt, system_prompt="Ты эксперт по профилированию ролей и поиску дефицитов навыков.")

    def _sub_agent_kpi_okr(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Модуль 3 (Скрипт): Детерминированный расчет планов, скоростей и ошибок."""
        # Чистая математика, без LLM (температура = 0 не нужна, это обычный Python-код)
        metrics = data.get("payload", {})
        commits = metrics.get("commits_count", 0)
        # Пример простейшего расчета
        kpi_score = min(100, commits * 5)
        return {"kpi_execution_rate": f"{kpi_score}%", "processed_by": "DeterministicScript"}

    async def _sub_agent_lms_trajectory(self, data: Dict[str, Any]) -> str:
        """Модуль 4 (LLM + Скрипт): Динамика обучения в LMS."""
        prompt = f"Оцени скорость прироста знаний и обучаемость по логам LMS: {data}"
        return await self.llm.generate(prompt, system_prompt="Ты аналитик корпоративного обучения.")

    async def _sub_agent_feedback_360(self, data: Dict[str, Any]) -> str:
        """Модуль 5 (LLM + ChromaDB): Выделение Soft-Skills из отзывов окружения."""
        prompt = f"Выдели софт-скиллы, сильные стороны и токсичность из отзывов коллег: {data}"
        return await self.llm.generate(prompt, system_prompt="Ты эксперт по оценке 360 градусов и поведенческому анализу.")

    async def _sub_agent_star(self, data: Dict[str, Any]) -> str:
        """Модуль 6 (LLM): Поведенческий анализ интервью/ревью по методологии STAR."""
        prompt = f"Разложи тексты интервью сотрудника по методологии STAR (Situation, Task, Action, Result): {data}"
        return await self.llm.generate(prompt, system_prompt="Ты сертифицированный HR-интервьюер, оценивающий кейсы по STAR.")

    async def _sub_agent_consolidator(self, emp_id: str, hard: str, spec: str, kpi: dict, lms: str, f360: str, star: str) -> Dict[str, Any]:
        """Модуль 7 (LLM): Сборщик финального структурированного JSON-профиля."""
        prompt = (
            f"Собери аналитические выводы всех модулей по сотруднику {emp_id} в единый лаконичный JSON.\n"
            f"Hard: {hard}\nMatrix: {spec}\nKPI: {kpi}\nLMS: {lms}\n360: {f360}\nSTAR: {star}"
        )
        system_prompt = "Ты главный консолидатор данных. Твой ответ должен быть СТРОГО в формате JSON без лишнего текста."
        ai_response = await self.llm.generate(prompt, system_prompt=system_prompt)

        # Для прототипа возвращаем словарь, в будущем здесь будет json.loads(ai_response)
        return {"employee_id": emp_id, "structured_analysis": ai_response}
