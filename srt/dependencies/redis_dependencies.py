import json
import os
from redis.asyncio import Redis  # Асинхронный клиент
from fastapi.security import HTTPBearer
from dotenv import load_dotenv

from confluent_kafka import Producer, KafkaException
import socket

from srt.config import logger

load_dotenv()
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS')

security = HTTPBearer()

redis_client = Redis(
    host=REDIS_HOST,  # Хост Redis-сервера
    port=REDIS_PORT,  # Порт по умолчанию
    db=0,  # Номер базы данных (0-15)
    decode_responses=True  # Автоматическое декодирование из bytes в str
)

async def get_redis():
    try:
        yield redis_client
    finally:
        pass # Не закрываем соединение явно, так как Redis клиент управляет соединением сам

class ProducerKafka:
    def __init__(self):
        self.conf = {
                'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
                'client.id': socket.gethostname()

            }
        self.producer = Producer(self.conf)

    def sent_message(self, topic: str, key: str, value: str):
        try:
            self.producer.produce(topic=topic, key=key, value=value, callback=self._acked)
            self.producer.flush()
            self.producer.poll(1)
        except KafkaException as e:
            logger.error(f"Kafka error: {e}")

    def _acked(self, err, msg):
        print(f"err: {err}\nmsg: {msg.value().decode('utf-8')}")


producer = ProducerKafka()