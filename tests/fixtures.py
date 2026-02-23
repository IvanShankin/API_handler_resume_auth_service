import fakeredis
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.app import get_app
from src.database.core import get_db
from src.infrastructure.kafka import set_producer, get_producer
from src.infrastructure.redis.core import get_redis
from src.repository.database import RefreshTokenRepository, UserRepository
from src.repository.redis import UserCacheRepository
from src.service import get_config, UserService
from tests.helper_func import KafkaTestProducer


@pytest_asyncio.fixture
async def session_db() -> AsyncSession:
    """Соединение с БД"""
    from src.repository.database import get_db  # Импортируем после переопределения

    db_gen = get_db()
    session = await db_gen.__anext__()
    try:
        yield session
    finally:
        await session.close()



@pytest_asyncio.fixture
async def client_with_db(session_db):  # session_db открываем заранее
    app = get_app()
    # переопределяем Depends(get_db) на уже открытую сессию
    app.dependency_overrides[get_db] = lambda: session_db
    async with AsyncClient(transport=ASGITransport(get_app()), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def replace_producer() -> KafkaTestProducer:
    return await set_producer(KafkaTestProducer())


@pytest_asyncio.fixture
async def user_service_fix(session_db):
    conf = get_config()
    return UserService(
        user_repo=UserRepository(
            session_db=session_db,
            config=conf,
        ),
        refresh_token_repo=RefreshTokenRepository(
            session_db=session_db,
            config=conf,
        ),
        cache_repo=UserCacheRepository(
            redis_session=get_redis(),
            config=conf,
        ),
        session_db=session_db,
        producer=await get_producer(),
        config=conf,
    )


@pytest.fixture(scope="function", autouse=True)
async def clearing_redis():
    redis = get_redis()
    await redis.flushall()
    await redis.close()
    return redis


@pytest.fixture
def fake_request():

    def _make(
        headers: dict[str, str] | None = None,
        client_host: str = "127.0.0.1"
    ) -> Request:
        if headers is None:
            headers = {"x-forwarded-for": "10.0.0.1"}

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "method": "GET",
            "path": "/",
            "headers": [
                (k.lower().encode(), v.encode())
                for k, v in (headers or {}).items()
            ],
            "client": (client_host, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }

        async def receive():
            return {"type": "http.request", "body": b""}

        return Request(scope, receive)

    return _make

