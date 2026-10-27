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

            pred_results = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            for i, res in enumerate(pred_results):
                if isinstance(res, Exception):
                    logger.warning(f"Суб-агент {i} завершился с ошибкой: {res}", exc_info=True)
                    results.append("Данные недоступны из-за технического сбоя модуля.")
                else:
                    results.append(res)

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

    def _calculate_employee_match(self, employee_skills: dict, role_requirements: dict) -> dict:
        """
        Детерминированный расчет соответствия сотрудника роли (Match_er).
        employee_skills: {'python': {'commits': 0.8, 'jira': 0.6}, 'asyncio': {...}}
        role_requirements: {'python': {'required': 0.7, 'weight': 3}, 'asyncio': {...}}
        """
        total_weighted_gap = 0.0
        total_weight = 0.0

        # Источники и их уровни доверия (c_ik)
        source_confidence = {"commits": 1.0, "jira": 0.8, "lms": 0.7, "feedback_360": 0.5}

        for skill, req in role_requirements.items():
            r_k = req.get("required", 0.0)
            w_k = req.get("weight", 1.0)
            total_weight += w_k

            # 1. Считаем взвешенный уровень L_k по источникам
            sources = employee_skills.get(skill, {})
            if not sources:
                l_k = 0.0
            else:
                top_sum = 0.0
                bottom_sum = 0.0
                for src_name, score in sources.items():
                    c_ik = source_confidence.get(src_name, 0.5)
                    top_sum += c_ik * score
                    bottom_sum += c_ik
                l_k = top_sum / bottom_sum if bottom_sum > 0 else 0.0

            # 2. Компетентностный разрыв G_k = max(0, R_k - L_k)
            g_k = max(0.0, r_k - l_k)  # cite: 1

            total_weighted_gap += w_k * g_k

        # 3. Итоговый процент Match_er
        if total_weight == 0:
            return {"match_percentage": 0, "status": "No requirements"}

        match_er = 100 * (1 - (total_weighted_gap / total_weight))  # cite: 1
        return {
            "match_percentage": round(match_er, 2),
            "processed_by": "DeterministicMatchEngine"
        }

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

    # мини фикс заглушка метод нигде не определен
    def _sub_agent_kpi_okr(self, data: Dict[str, Any]) -> dict:
        """Модуль 3 (Скрипт): детерминированный расчёт KPI/OKR. TODO."""
        return {"status": "not_implemented", "metrics": {}}