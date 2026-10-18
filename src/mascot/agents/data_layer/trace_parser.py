import uuid
from src.mascot.core.base_agent import BaseAgent
from src.mascot.core.message import AgentMessage
from src.mascot.storage.models import RawDigitalTrace


class TraceParserAgent(BaseAgent):
    """
    Агент первого слоя данных.
    Отвечает за парсинг и первичную валидацию цифрового следа сотрудников.
    """

    async def process(self, message: AgentMessage) -> AgentMessage | None:
        # Проверяем, предназначен ли этот тип сообщения для парсера
        if message.message_type != "RAW_DATA_INPUT":
            return None

        self.log_action(f"Starting to parse raw data from system: {message.payload.get('source_system')}")

        try:
            # Извлекаем сырые данные из тела сообщения
            raw_data = message.payload.get("data", {})

            # Валидируем данные через Pydantic-модель

            validated_trace = RawDigitalTrace(
                employee_id=raw_data.get("employee_id"),
                source_system=raw_data.get("source_system"),
                event_type=raw_data.get("event_type"),
                payload=raw_data.get("payload", {})
            )

            # Формируем ответное сообщение для аналитического слоя
            output_message = AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver="evaluator",  # Отправляем напрямую Оценщику в analytics_layer
                message_type="VALIDATED_TRACE",
                payload=validated_trace.model_dump()  # Экспортируем модель в чистый JSON/словарь
            )

            self.log_action(f"Successfully validated trace for employee {validated_trace.employee_id}")
            return output_message

        except Exception as e:
            self.log_action(f"Parsing failed due to validation error: {str(e)}")

            # В случае ошибки возвращаем сообщение об аварии на шину
            return AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender=self.name,
                receiver="broadcast",
                message_type="PARSING_ERROR",
                payload={"error": str(e), "original_message_id": message.message_id}
            )
