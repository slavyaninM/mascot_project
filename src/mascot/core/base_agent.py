from abc import ABC, abstractmethod
import logging

from src.mascot.core.message import AgentMessage
from src.mascot.core.message_bus import MessageBus

logger = logging.getLogger("mascot.mas")


class BaseAgent(ABC):

    def __init__(self, name: str, agent_type: str, message_bus: MessageBus):
        self.name = name
        self.agent_type = agent_type
        self.bus = message_bus

        self.bus.register_agent(self.name, self.handle_message)

    async def handle_message(self, message: AgentMessage) -> None:
        """Внутренний оберточный метод для обработки сообщений."""
        self.log_action(f"Received message {message.message_id} from {message.sender}")

        response: AgentMessage | None = await self.process(message)

        if response:
            await self.bus.send(response)

    @abstractmethod
    async def process(self, message: AgentMessage) -> AgentMessage | None:
        #Основной метод обработки входящего сообщения.
        pass

    def log_action(self, action_details: str):
        #Единый метод логирования для слоя доверия.
        logger.info(f"[{self.agent_type.upper()}] Agent '{self.name}' executed: {action_details}")