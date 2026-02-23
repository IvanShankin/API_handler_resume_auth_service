import os
import sys
import inspect

import fakeredis
from dotenv import load_dotenv

from src.api.app import init_fastapi_app
from src.database.creating import create_database
from src.database.models import RefreshToken, Users
from src.infrastructure.kafka import set_producer
from src.infrastructure.kafka.admin_client import set_admin_client
from src.infrastructure.kafka.topic_manager import check_exists_topic
from src.infrastructure.redis.core import set_redis
from src.service import get_config
from src.service.config import init_config
from tests.helper_func import FakeAdminClient, KafkaTestProducer

load_dotenv()  # Загружает переменные из .env
MODE = os.getenv('MODE')

# этот импорт необходимо указывать именно тут для корректного импорта .tests.env
import pytest_asyncio

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from src.repository.database import get_db as original_get_db

# НЕ УДАЛЯТЬ ИСПОЛЬЗУЕТСЯ В ТЕСТАХ
from tests.fixtures import client_with_db, session_db, replace_producer, user_service_fix, fake_request


@pytest_asyncio.fixture(scope='session', autouse=True)
async def start_test():
    conf = init_config()
    if conf.env.mode != "TEST":
        raise Exception("Используется основная БД!")

    await set_producer(KafkaTestProducer())

    await create_database()
    await set_redis(fakeredis.aioredis.FakeRedis())
    await set_admin_client(FakeAdminClient())
    await check_exists_topic(conf.env.kafka_topic_producer_for_uploading_data)

    init_fastapi_app()


# Мок-версия get_db
async def _mock_get_db():
    """Переопределяет функцию get_db. Отличия: каждый раз создаёт новый engine и session_local"""
    engine = create_async_engine(get_config().db_connection.sql_db_url)
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


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clearing_db(session_db: AsyncSession):
    """Очищает базу банных"""
    await session_db.execute(delete(RefreshToken))
    await session_db.execute(delete(Users))
    await session_db.commit()


