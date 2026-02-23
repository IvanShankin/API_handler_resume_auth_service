from orjson import orjson
from redis.asyncio import Redis
from dateutil.parser import parse

from src.database.models import Users
from src.service.config.schemas import Config


class UserCacheRepository:

    def __init__(self, redis_session: Redis, config: Config):
        self.redis_session = redis_session
        self.conf = config


    async def get_login_block(
        self,
        ip_address: str,
        username: str,
    ) -> bool:
        block_key = f"auth:login_block:{ip_address}:{username}"
        return bool(await self.redis_session.get(block_key))

    async def get_user(self, user_id: int) -> Users | None:
        user_redis = await self.redis_session.get(f"auth:user:{user_id}")

        if user_redis:
            data = orjson.loads(user_redis)
            user = Users(**data)
            user.created_at = parse(data["created_at"])
            return user

        return None

    async def set_block_user(
        self,
        ip_address: str,
        username: str,
    ):
        block_key = f"auth:login_block:{ip_address}:{username}"
        await self.redis_session.setex(block_key, self.conf.login_block_time, "_")

    async def set_user(self, user: Users) -> None:
        await self.redis_session.setex(
            f"auth:user:{user.user_id}",
            int(self.conf.tokens.access_token_expire_minutes * 60),  # Время жизни в секундах
            orjson.dumps(user.to_dict())
        )

    async def incr_login_attempt(
        self,
        ip_address: str,
        username: str,
    ) -> int:
        """
        Повысит на +1 количество попыток входа
        :return int: Количество попыток после увеличения
        """
        attempt_key = f"auth:login_attempt:{ip_address}:{username}"
        attempts = await self.redis_session.incr(attempt_key)

        await self.redis_session.expire(attempt_key, self.conf.login_block_time)

        return attempts

    async def delete_user(self, user_id: int):
        await self.redis_session.delete(f"auth:user:{user_id}")



