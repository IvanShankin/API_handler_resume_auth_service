import os
import secrets
from datetime import datetime, timedelta, UTC
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from srt.data_base.models import RefreshToken

load_dotenv()
REFRESH_TOKEN_EXPIRE_DAYS = float(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS'))
ALGORITHM = os.getenv('ALGORITHM')


def create_refresh_token(user_id: int) -> str:
    # Генерируем случайную строку
    return secrets.token_urlsafe(64)

async def save_refresh_token(user_id: int, token: str, db: AsyncSession):
    expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_token)
    await db.commit()

async def validate_refresh_token(token: str, db: AsyncSession) -> Optional[int]:
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token == token)
        .where(RefreshToken.expires_at >= datetime.now(UTC))
    )
    db_token = result.scalar_one_or_none()
    return db_token.user_id if db_token else None

async def update_refresh_token(old_token: str, new_token: str, db: AsyncSession):
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token == old_token)
        .values(token=new_token)
    )
    await db.commit()