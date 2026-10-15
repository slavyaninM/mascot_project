from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentMessage(BaseModel):
    """Единый формат сообщений для шины обмена данными MAS."""
    message_id: str = Field(description="Уникальный идентификатор сообщения")
    sender: str = Field(description="Имя агента-отправителя (например, 'GitAnalyticsAgent')")
    receiver: str = Field(description="Имя агента-получателя или 'broadcast'")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Полезная нагрузка (данные/JSON)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Метаданные (токены, логи, трассировка)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время отправки")
