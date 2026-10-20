import asyncio
import logging
from src.mascot.core.message_bus import MessageBus
from src.mascot.core.message import AgentMessage
from src.mascot.agents.data_layer.trace_parser import TraceParserAgent
from src.mascot.agents.analytics_layer.evaluator import EvaluatorAgent
from src.mascot.llm.client import LLMClient

# 1. Централизованная настройка логирования, чтобы видеть шаги каждого агента в MAS
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("atlas.pipeline")


async def main():

    logger.info("ЗАПУСК МУЛЬТИАГЕНТНОГО КОНВЕЙЕРА ОЦЕНКИ")

    # 2. Инициализация общей инфраструктуры ядра платформы
    bus = MessageBus()
    llm_client = LLMClient()

    # 3. Инициализация агентов.
    # В конструкторе (через BaseAgent) они автоматически регистрируют свои коллбэки в шине.
    logger.info("Инициализация слоёв агентов...")
    parser_agent = TraceParserAgent(
        name="trace_parser",
        agent_type="data_layer",
        message_bus=bus
    )

    # Главный оркестратор аналитики, содержащий 7 внутренних суб-агентов (модулей)
    evaluator_agent = EvaluatorAgent(
        name="evaluator",
        agent_type="analytics_layer",
        message_bus=bus,
        llm_client=llm_client
    )

    # 4. Имитация прихода сырого лога от внешней системы (например, коммит разработчика из Git)
    mock_raw_input = AgentMessage(
        message_id="msg_init_001",
        sender="external_api_gateway",
        receiver="trace_parser",  # Адресуем напрямую первому агенту-парсеру
        message_type="RAW_DATA_INPUT",
        payload={
            "data": {
                "employee_id": "emp_backend_developer_05",
                "source_system": "git",
                "event_type": "commit",
                "payload": {
                    "commits_count": 15,
                    "lines_added": 840,
                    "repository": "finance_billing_service"
                }
            }
        }
    )

    # 5. Отправка стартового триггера в шину обмена данными
    logger.info("Запуск сообщения с сырыми данными в шину сообщений...")
    await bus.send(mock_raw_input)

    logger.info("МУЛЬТИАГЕНТНЫЙ ТАКТ ВЫПОЛНЕНИЯ УСПЕШНО ЗАВЕРШЕН")


if __name__ == "__main__":
    # Запуск асинхронного цикла обработки событий
    asyncio.run(main())
