import asyncio
import logging
from typing import Dict, List, Callable, Awaitable
from src.mascot.core.message import AgentMessage

logger = logging.getLogger("mascot.message_bus")


AgentCallback = Callable[[AgentMessage], Awaitable[None]]


class MessageBus:

    def __init__(self):
        # Словарь, где ключ — имя агента, а значение — его функция-обработчик
        self._subscribers: Dict[str, AgentCallback] = {}

    def register_agent(self, agent_name: str, callback: AgentCallback) -> None:
        """Регистрирует агента в шине, чтобы он мог получать сообщения."""
        if agent_name in self._subscribers:
            logger.warning(f"Агент {agent_name} уже зарегистрирован. Перезаписываем обработчик.")
        self._subscribers[agent_name] = callback
        logger.info(f"Агент [{agent_name}] успешно подключен к шине сообщений.")

    def unregister_agent(self, agent_name: str) -> None:
        """Отключает агента от шины."""
        if agent_name in self._subscribers:
            del self._subscribers[agent_name]
            logger.info(f"Агент [{agent_name}] отключен от шины.")

    async def send(self, message: AgentMessage) -> None:
        """Отправляет сообщение конкретному получателю или делает broadcast."""
        logger.debug(f"Шина приняла сообщение {message.message_id} от [{message.sender}] для [{message.receiver}].")

        # Сценарий 1: Широковещательная рассылка всем агентам
        if message.receiver.lower() == "broadcast":
            tasks = []
            for agent_name, callback in self._subscribers.items():
                if agent_name != message.sender:  # Не отправляем сообщение самому себе
                    tasks.append(self._safely_deliver(agent_name, callback, message))
            if tasks:
                await asyncio.gather(*tasks)
            return

        # Сценарий 2: Адресная отправка конкретному агенту
        if message.receiver in self._subscribers:
            callback = self._subscribers[message.receiver]
            await self._safely_deliver(message.receiver, callback, message)
        else:
            logger.error(f"Ошибка доставки: Агент [{message.receiver}] не зарегистрирован в системе!")

    async def _safely_deliver(self, agent_name: str, callback: AgentCallback, message: AgentMessage) -> None:
        """Вспомогательный метод для безопасного вызова обработчика агента."""
        try:
            await callback(message)
        except Exception as e:
            logger.critical(f"Критическая ошибка внутри агента [{agent_name}] при обработке сообщения: {e}", exc_info=True)
