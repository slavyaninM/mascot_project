import os
import httpx
import logging
import uuid
from pydantic import BaseModel
import config.settings # noqa

logger = logging.getLogger("mascot.llm_client")


class LLMClient:
    """Изолированный клиент для взаимодействия с GigaChat API."""

    def __init__(self):

        self.api_url = os.getenv("GIGACHAT_API_URL", "https://sberbank.ru")
        self.api_key = os.getenv("GIGACHAT_API_KEY", "your_api_key_here")
        self.model_name = os.getenv("GIGACHAT_MODEL_NAME", "GigaChat:latest")
    # дальше код ожидает что generate вернет CompetencyAnalysis с .model_dump(), но возвращает str
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "Ты полезный ИИ-помощник.",
        response_model: type[BaseModel] | None = None,
    ) -> str | BaseModel:
            
        # Пока заглушка, поменять .env
        if self.api_key == "your_api_key_here":
            logger.warning("Используется ИИ-заглушка")
            return f"[Заглушка GigaChat] Анализ сотрудника выполнен. Продуктивность высокая."

        # Для официального API GigaChat обычно требуется заголовок авторизации
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        data = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:  # verify=False часто нужен для сертификатов Сбера
                response = await client.post(self.api_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Ошибка при обращении к GigaChat API: {e}")
            raise e

        # после получения ответа:                               может быть плохая идея, удалить если не надо
        content = result["choices"][0]["message"]["content"]

        if response_model is not None:
            # Structured Output: ожидаем JSON в ответе
            return response_model.model_validate_json(content)

        return content
