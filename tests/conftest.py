import os
import time
import sys
import inspect

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA= os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')
MODE = os.getenv('MODE')

# этот импорт необходимо указывать именно тут для корректного импорта .tests.env
import pytest_asyncio

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import delete
from confluent_kafka.cimpl import NewTopic
from sqlalchemy.orm import sessionmaker

from src.database.database import create_database, get_db as original_get_db, SQL_DB_URL
from src.database.models import User, RefreshToken
from src.dependencies import get_redis, admin_client
from src.config import logger
from src.tokens import get_hash_password, create_access_token, create_refresh_token

from confluent_kafka import Consumer

conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'foo',
    'auto.offset.reset': 'smallest'
}

consumer = Consumer(conf)


@pytest_asyncio.fixture(scope='session', autouse=True)
async def create_database_fixture():
    if MODE != "TEST":
        raise Exception("Используется основная БД!")

    await create_database()


# Мок-версия get_db
async def _mock_get_db():
    """Переопределяет функцию get_db. Отличия: каждый раз создаёт новый engine и session_local"""
    engine = create_async_engine(SQL_DB_URL)
    session_local = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    db = session_local()
    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture(autouse=True, scope="session")
def override_get_db_globally():
    original = original_get_db # сохранение оригинальной функции
    patched_modules = [] # хранит пути где переопределили get_db

    # поиск по всем модулям
    for module_name, module in list(sys.modules.items()):
        if not module:
            continue
        # фильтруем только свои модули
        if not module_name.startswith("src."):
            continue
        try:
            for attr_name, attr_value in inspect.getmembers(module):
                if attr_value is original_get_db: # если значение атрибута это оригинальная get_db
                    setattr(module, attr_name, _mock_get_db) # замена на новую get_db
                    patched_modules.append((module, attr_name))
        except Exception:
            # если модуль ломается при доступе к атрибутам — пропускаем
            continue

    # подмена в FastAPI dependency_overrides
    try:
        from src.main import app
        app.dependency_overrides[original_get_db] = _mock_get_db
    except ImportError:
        pass
    yield

    # откат
    for module, attr_name in patched_modules:
        setattr(module, attr_name, original)

    try:
        from src.main import app
        app.dependency_overrides.clear()
    except ImportError:
        pass

@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Соединение с БД"""
    from src.database.database import get_db  # Импортируем после переопределения

    db_gen = get_db()
    session = await db_gen.__anext__()
    try:
        yield session
    finally:
        await session.close()

@pytest_asyncio.fixture(scope='session', autouse=True)
async def check_kafka_connection():
    try:
        admin_client.list_topics(timeout=10)
    except Exception:
        raise Exception("Не удалось установить соединение с Kafka!")

@pytest_asyncio.fixture
async def redis_session():
    """Соединение с redis"""
    redis_gen = get_redis()
    session = await redis_gen.__anext__()
    try:
        yield session
    finally:
        await session.aclose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clearing_db(db_session: AsyncSession):
    """Очищает базу банных"""
    await db_session.execute(delete(RefreshToken))
    await db_session.execute(delete(User))
    await db_session.commit()

@pytest_asyncio.fixture(scope="function")
async def clearing_redis(redis_session):
    """Очищает redis"""
    await redis_session.flushdb()

@pytest_asyncio.fixture(scope='function')
async def clearing_kafka():
    """Очищает топик у kafka с которым работаем, путём его пересоздания"""
    max_retries = 7

    # Получаем метаданные кластера
    cluster_metadata = admin_client.list_topics()

    # Проверяем существование топика
    topic_exists = KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA in cluster_metadata.topics

    # Проверяем существует ли топик перед удалением
    if topic_exists:
        admin_client.delete_topics(topics=[KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA])

        # Ждём подтверждения удаления
        for _ in range(max_retries):
            current_metadata = admin_client.list_topics()
            if KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA not in current_metadata.topics:
                break
            time.sleep(1)
        else:
            logger.warning(f"Topic {KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA} still exists after deletion attempts")

    admin_client.create_topics([NewTopic(topic=KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA, num_partitions=1, replication_factor=1)])
    time.sleep(2)  # даём Kafka 2 секунды на инициализацию

    # Проверяем создание топика
    for _ in range(max_retries):
        current_metadata = admin_client.list_topics()
        if KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA in current_metadata.topics:
            break
        time.sleep(1)
    else:
        raise RuntimeError(f"Не удалось создать топик: {KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA}")


@pytest_asyncio.fixture(scope="function")
async def create_user(db_session: AsyncSession):
    """
    Создает тестового пользователя и возвращает данные о нём
    :return: dict {"username", 'password', "access_token", "refresh_token"}
    """

    password = "first_password_test"
    hashed_password = get_hash_password(password)
    new_user = User(
        username = 'first_user_test',
        hashed_password=hashed_password
    )
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    access_token = create_access_token(data={"sub": str(new_user.user_id)})
    refresh_token = await create_refresh_token(db_session)

    db_refresh_token = RefreshToken(
        user_id=new_user.user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db_session.add(db_refresh_token)
    await db_session.commit()

    return {
        "user_id": new_user.user_id,
        "username": new_user.username,
        'password': password,
        "access_token": access_token,
        "refresh_token": refresh_token
    }



