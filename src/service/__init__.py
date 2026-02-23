from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.core import get_db
from src.infrastructure.kafka import get_producer
from src.infrastructure.kafka.producer import ProducerKafka
from src.repository.database import UserRepository, get_user_repository, get_refresh_token_repository, \
    RefreshTokenRepository
from src.repository.redis import get_user_cache_repository
from src.repository.redis.user_cache import UserCacheRepository
from src.service.config import get_config
from src.service.config.schemas import Config
from src.service.user import UserService


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    cache_repo: UserCacheRepository = Depends(get_user_cache_repository),
    session_db: AsyncSession = Depends(get_db),
    producer: ProducerKafka = Depends(get_producer),
    config: Config = Depends(get_config),
) -> UserService:
    return UserService(
        user_repo=user_repo,
        cache_repo=cache_repo,
        refresh_token_repo=refresh_token_repo,
        producer=producer,
        session_db=session_db,
        config=config,
    )


