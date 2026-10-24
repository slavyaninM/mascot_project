import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from src.mascot.llm.client import LLMClient


class SoftSkillRequirement(BaseModel):
    skill_name: str = Field(description="Название soft-skill")
    min_score: int = Field(description="Минимально необходимый уровень от 0 до 1")
    reasoning: str = Field(description="Обоснование, почему этот навык важен для данного ТЗ")


class ProjectRequirements(BaseModel):
    project_name: str = Field(description="Название проекта из ТЗ")
    tech_stack: List[str] = Field(
        description="Список технологий, фреймворков и БД (например, ['Python', 'PostgreSQL', 'FastAPI'])")
    project_type: str = Field(description="Характер проекта: например, MVP, Enterprise-модернизация, Стартап, R&D")
    soft_skills_requirements: List[SoftSkillRequirement] = Field(
        description="Требования к личностным качествам команды")


class ProjectInterpreterAgent:
    def __init__(self, client: LLMClient):
        """
        Инициализация агента.
        """
        self.client = client
        self.prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "llm", "prompts", "project_interpreter.txt"
        )

    def _load_system_prompt(self) -> str:
        """Загружает изолированный текстовый промпт из папки prompts."""
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"Системный промпт не найден по пути: {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def analyze_spec(self, file_content: str) -> ProjectRequirements:
        """
        Основной метод агента. Анализирует текст ТЗ и возвращает структурированный объект требований.
        """
        system_prompt = self._load_system_prompt()

        # Формируем запрос к GigaChat, используя механизм Structured Outputs (передаем Pydantic-модель)
        # Примечание: Убедитесь, что ваша обертка GigaChatClient поддерживает передачу response_model (FastAPI-style)
        # Если используете стандартный langchain_community.chat_models, там есть метод .with_structured_output(ProjectRequirements)

        response = self.client.generate(
            system_prompt=system_prompt,
            user_message=f"Проанализируй следующее Техническое Задание:\n\n{file_content}",
            response_model=ProjectRequirements
        )

        return response
