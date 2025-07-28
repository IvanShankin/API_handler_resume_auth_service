import os
import socket
from dotenv import load_dotenv
from confluent_kafka import Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from srt.config import logger

load_dotenv()
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA = os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')

admin_client = AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

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
        logger.info(f"Kafka new message: err: {err}\nmsg: {msg.value().decode('utf-8')}")

producer = ProducerKafka()



def create_topic(topic_name, num_partitions=1, replication_factor=1):
    """
    Создаёт топик в Kafka.

    :param topic_name: Название топика
    :param num_partitions: Количество партиций
    :param replication_factor: Фактор репликации
    """
    # Создание объекта топика
    new_topic = NewTopic(
        topic_name,
        num_partitions=num_partitions,
        replication_factor=replication_factor
    )

    # Запрос на создание топика
    futures = admin_client.create_topics([new_topic])

    # Ожидание результата
    for topic, future in futures.items():
        try:
            future.result()  # Блокирует выполнение, пока топик не создан
            logger.info(f"Топик '{topic}' успешно создан!")
        except Exception as e:
            logger.error(f"Ошибка при создании топика '{topic}': {e}")


def check_exists_topic(topic_name):
    """Проверяет, существует ли топик, если нет, то создаст его"""
    cluster_metadata = admin_client.list_topics()
    if not topic_name in cluster_metadata.topics: # если topic не существует
        create_topic(
            topic_name=KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA,
            num_partitions=1,
            replication_factor=1
        )

