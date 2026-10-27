from abc import abstractmethod
import os
import uuid
import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field

# Импортируем базовые абстракции экосистемы mascot
from src.mascot.core.base_agent import BaseAgent
from src.mascot.core.message import AgentMessage
from src.mascot.llm.client import LLMClient

logger = logging.getLogger("mascot.competency_mapper")


class SkillGap(BaseModel):
    skill_name: str = Field(description="Название дефицитного навыка или слепой зоны")
    severity: str = Field(description="Уровень критичности дефицита: 'Критичный', 'Средний', 'Низкий'")
    description: str = Field(description="Чего именно не хватает сотруднику согласно матрице роли и почему это важно")


class CompetencyAnalysis(BaseModel):
    match_percentage: int = Field(description="Процент общего соответствия роли (от 0 до 100)")
    matched_skills: List[str] = Field(description="Подтвержденные навыки сотрудника, которые совпали с матрицей")
    skill_gaps: List[SkillGap] = Field(description="Список выявленных слепых зон и дефицитов навыков (Skill Gaps)")
    development_recommendations: List[str] = Field(
        description="Пошаговые рекомендации и вектор развития для сотрудника на ближайший квартал"
    )


class CompetencyMapperAgent(BaseAgent):
    """
    Агент профилирования и маппинга компетенций.
    Сравнивает профиль сотрудника с матрицей роли и формирует строгую Pydantic-структуру анализа.
    """

    def __init__(self, name: str, agent_type: str, message_bus, llm_client: LLMClient, vector_db_client=None):
        super().__init__(name, agent_type, message_bus)
        self.client = llm_client
        self.chroma_db = vector_db_client  # для интеграции с векторной БД


        self.prompt_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "llm", "prompts", "competency_mapper.txt")
        )

    def _load_system_prompt(self) -> str:
        """Загружает изолированный текстовый промпт из папки prompts."""
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"Системный промпт не найден по пути: {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    @abstractmethod
    async def process(self, message: AgentMessage) -> AgentMessage | None:
        # Агент слушает запросы на маппинг компетенций
        if message.message_type != "MAP_COMPETENCIES":
            return None

        employee_id = message.payload.get("employee_id")
        role = message.payload.get("target_role", "Not Specified")
        employee_data = message.payload.get("employee_data", {})

        self.log_action(f"Запуск ИИ-маппинга компетенций для {employee_id} на роль: {role}")

        try:
            # 1. Получаем эталонную матрицу для роли (пока фолбэк, далее — ChromaDB)
            role_matrix = await self._get_role_matrix(role)

            # 2. Загружаем системный промпт
            system_prompt = self._load_system_prompt()

            # 3. Формируем пользовательское сообщение
            user_message = (
                f"Задача: Сравни текущие навыки сотрудника с эталонной матрицей компетенций для роли '{role}'.\n\n"
                f"--- ЭТАЛОННАЯ МАТРИЦА РОЛИ ---\n{role_matrix}\n\n"
                f"--- ДАННЫЕ СОТРУДНИКА ---\n{employee_data}\n"
            )

            # 4. Асинхронно вызываем генерацию с поддержкой Structured Outputs
            structured_analysis: CompetencyAnalysis = await self.client.generate(
                prompt=user_message,                            #elevator.py не ломается, copmetency_mapper.py получает аналитику и .model_dump()
                system_prompt=system_prompt,
                response_model=CompetencyAnalysis
            )

            # 5. Возвращаем структурированный ответ в шину
            self.log_action(f"Маппинг компетенций сотрудника {employee_id} успешно завершен.")
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver=message.sender,
                message_type="COMPETENCY_MAP_SUCCESS",
                payload={
                    "employee_id": employee_id,
                    "target_role": role,
                    # Pydantic модель преобразуем в dict для сериализации в шине сообщений
                    "analysis": structured_analysis.model_dump()
                }
            )

        except Exception as e:
            logger.error(f"Сбой маппинга компетенций для сотрудника {employee_id}: {e}", exc_info=True)
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver=message.sender,
                message_type="COMPETENCY_MAP_ERROR",
                payload={"employee_id": employee_id, "error": str(e)}
            )

    async def _get_role_matrix(self, role: str) -> str:
        """
        Внутренний метод получения матрицы компетенций.
        В будущем здесь будет асинхронный поиск эмбеддингов в ChromaDB.
        """
        fallback_matrices = {
            "backend_engineer": (
                "Hard Skills: Python, Asyncio, PostgreSQL, Docker, REST API, Git, FastAPI, Микросервисы. "
                "Soft Skills: Проведение качественного Code Review, менторство джуниоров, кросс-командное взаимодействие."
            ),

            "frontend_engineer": (
                "Hard Skills: JavaScript, TypeScript, React, Redux, CSS/HTML, Webpack, Next.js, REST API. "
                "Soft Skills: Отличное чувство UX/UI, внимание к микроконтролям, адаптивность к изменениям дизайна."
            ),

            "qa_automation": (
                "Hard Skills: Python, PyTest, Selenium WebDriver, Playwright, CI/CD pipelines (GitLab/GitHub Actions), "
                "REST API Testing (Postman/Requests), SQL basics, Git, Понимание жизненного цикла тестирования (STLC). "
                "Soft Skills: Высокая внимательность к деталям, сильные аналитические навыки, умение аргументировать баги и защищать позицию."
            )
        }
        normalized_role = role.lower().replace(" ", "_")
        return fallback_matrices.get(normalized_role, "Общие ИТ-компетенции: Понимание жизненного цикла разработки, Git.")
