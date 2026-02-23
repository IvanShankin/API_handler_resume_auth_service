from typing import Optional

from src.infrastructure.kafka.producer import ProducerKafka
from src.infrastructure.kafka.topic_manager import create_topic

_producer: Optional[ProducerKafka] = None


async def init_producer() -> ProducerKafka:
    return await set_producer(ProducerKafka())


async def set_producer(producer: ProducerKafka) -> ProducerKafka:
    global _producer
    _producer = producer
    await _producer.start()

    return _producer


async def get_producer() -> ProducerKafka:
    global _producer
    if _producer is None:
        raise RuntimeError("ProducerKafka not initialized")
    return _producer


async def shutdown_producer():
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None