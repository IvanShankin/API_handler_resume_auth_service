from fastapi.params import Depends
from redis.asyncio import Redis

from src.infrastructure.redis.core import get_redis
from src.repository.redis.user_cache import UserCacheRepository
from src.service.config import get_config


async def get_user_cache_repository(
    redis: Redis = Depends(get_redis)
):
    return UserCacheRepository(redis, get_config())