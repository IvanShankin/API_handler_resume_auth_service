import os
from redis.asyncio import Redis  # Асинхронный клиент
from fastapi.security import HTTPBearer
from dotenv import load_dotenv

load_dotenv()
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))

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
        await redis_client.aclose()
