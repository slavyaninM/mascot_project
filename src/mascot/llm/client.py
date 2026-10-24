import os
import requests
from typing import Type, TypeVar
from pydantic import BaseModel

# Создаем переменную типа для динамической типизации Pydantic-моделей
T = TypeVar('T', bound=BaseModel)


class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("GIGACHAT_CREDENTIALS") or os.getenv("OPENAI_API_KEY")
        # Используем эндпоинт, поддерживающий структурированный вывод
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://gigachat.com")

    def generate(self, system_prompt: str, user_message: str, response_model: Type[T]) -> T:
        """
        Отправляет запрос в LLM с требованием вернуть данные строго по схеме Pydantic-модели.
        Возвращает уже готовый, провалидированный объект этой модели.
        """
        if not self.api_key:
            raise ValueError("API-ключ не найден. Проверьте переменные окружения.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Превращаем Pydantic-модель в строгую JSON-схему для нейросети
        json_schema = response_model.model_json_schema()

        payload = {
            "model": "GigaChat-Pro",  # Модель с поддержкой Structured Outputs
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.1,
            # Инструктируем API возвращать данные строго по нашей схеме
            "response_format": {
                "type": "json_object",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": json_schema
                }
            }
        }

        response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()

        # Достаем строку с JSON из ответа модели
        raw_json_content = response.json()["choices"]["message"]["content"]

        # Парсим строку обратно в готовый объект Pydantic-модели
        return response_model.model_validate_json(raw_json_content)
