from typing import List, Optional

from src.infrastructure.kafka import ProducerKafka
from src.service import get_config
from tests.schemas import ProducerMessage


class KafkaTestProducer(ProducerKafka):
    """
    Async helper для тестов.
    """
    def __init__(self,):
        super().__init__()
        self.all_message: List[ProducerMessage] = []

    async def send_message(
        self,
        topic: str,
        value: dict | str | bytes,
        key: Optional[str] = None,
    ):
        """Сохранит все """
        self.all_message.append(
            ProducerMessage(topic=topic, key=key, value=value)
        )

    async def start(self):
        pass

    async def stop(self):
        pass


class FakeAdminClient:
    def __init__(self):
        pass

    async def list_topics(self):
        conf = get_config()
        return conf.kafka_topics.all_topics