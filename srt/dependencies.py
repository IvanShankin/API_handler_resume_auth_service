from redis.asyncio import Redis  # Асинхронный клиент
from fastapi.security import HTTPBearer

security = HTTPBearer()


redis_client = Redis(
    host='localhost',  # Хост Redis-сервера
    port=6379,  # Порт по умолчанию
    db=0,  # Номер базы данных (0-15)
    decode_responses=True  # Автоматическое декодирование из bytes в str
)

async def get_redis():
    try:
        yield redis_client
    finally:
        # Не закрываем соединение явно, так как Redis клиент управляет соединением сам
        pass
