import os
import uuid
import logging
import asyncio
from typing import Dict, Any, List
from pydantic import BaseModel, Field

# Импортируем базовые абстракции экосистемы mascot
from src.mascot.core.base_agent import BaseAgent
from src.mascot.core.message import AgentMessage
from src.mascot.llm.client import LLMClient

logger = logging.getLogger("mascot.project_interpreter")



class SoftSkillRequirement(BaseModel):
    skill_name: str = Field(description="Название soft-skill")
    min_score: float = Field(description="Минимально необходимый уровень от 0.0 до 1.0")  # Сделали float для точности
    reasoning: str = Field(description="Обоснование, почему этот навык важен для данного ТЗ")


class ProjectRequirements(BaseModel):
    project_name: str = Field(description="Название проекта из ТЗ")
    tech_stack: List[str] = Field(
        description="Список технологий, фреймворков и БД (например, ['Python', 'PostgreSQL', 'FastAPI'])"
    )
    project_type: str = Field(description="Характер проекта: например, MVP, Enterprise-модернизация, Стартап, R&D")
    soft_skills_requirements: List[SoftSkillRequirement] = Field(
        description="Требования к личностным качествам команды"
    )


class ProjectInterpreterAgent(BaseAgent):
    """
    Агент интерпретации проектных требований (ТЗ).
    Анализирует входящие спецификации и формирует строгую Pydantic-структуру требований.
    """

    def __init__(self, name: str, agent_type: str, message_bus, llm_client: LLMClient):
        # Инициализируем базового агента
        super().__init__(name, agent_type, message_bus)
        self.client = llm_client

        self.prompt_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "llm", "prompts", "project_interpreter.txt")
        )

    def _load_system_prompt(self) -> str:
        """Загружает изолированный текстовый промпт."""
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"Системный промпт не найден по пути: {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    async def process(self, message: AgentMessage) -> AgentMessage | None:
        # 1. Фильтруем тип сообщения (агент слушает запросы на анализ спецификаций)
        if message.message_type != "ANALYZE_PROJECT_SPEC":
            return None

        project_id = message.payload.get("project_id", "unknown")
        file_content = message.payload.get("file_content", "")

        if not file_content:
            logger.error(f"Агент {self.name} получил пустой контент файла для проекта {project_id}")
            return None

        self.log_action(f"Запуск ИИ-анализа технического задания для проекта: {project_id}")

        try:
            # 2. Выносим чтение промпта в неблокирующий поток (опционально, для тяжелых дисков)
            system_prompt = self._load_system_prompt()

            structured_requirements: ProjectRequirements = await self.client.generate(
                system_prompt=system_prompt,
                user_message=f"Проанализируй следующее Техническое Задание:\n\n{file_content}",
                response_model=ProjectRequirements
            )

            # 4. Возвращаем структурированный ответ в шину
            self.log_action(f"Анализ ТЗ проекта {project_id} успешно завершен.")
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver=message.sender,
                message_type="PROJECT_SPEC_ANALYZED",
                payload={
                    "project_id": project_id,
                    "requirements": structured_requirements.model_dump()
                }
            )

        except Exception as e:
            logger.error(f"Сбой анализа спецификации проекта {project_id}: {e}", exc_info=True)
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver=message.sender,
                message_type="PROJECT_SPEC_ERROR",
                payload={"project_id": project_id, "error": str(e)}
            )

