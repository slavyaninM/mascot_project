from abc import ABC, abstractmethod
import logging
from src.mascot.core.message import AgentMessage

logger = logging.getLogger("mascot.mas")


class BaseAgent(ABC):

    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type

    @abstractmethod
    async def process(self, message: AgentMessage) -> AgentMessage:
        #Основной метод обработки входящего сообщения.
        pass

    def log_action(self, action_details: str):
        #Единый метод логирования для слоя доверия.
        logger.info(f"[{self.agent_type.upper()}] Agent '{self.name}' executed: {action_details}")