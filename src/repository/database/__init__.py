from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.core import get_db
from src.repository.database.refresh_token import RefreshTokenRepository
from src.repository.database.user import UserRepository
from src.service.config import get_config


async def get_user_repository(
    db: AsyncSession = Depends(get_db)
) -> UserRepository:
    return UserRepository(db, get_config())


async def get_refresh_token_repository(
    db: AsyncSession = Depends(get_db)
) -> RefreshTokenRepository:
    return RefreshTokenRepository(db, get_config())