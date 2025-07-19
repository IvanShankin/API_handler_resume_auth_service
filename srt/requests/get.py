from sqlalchemy import  text
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException

from srt.config import logger
from srt.schemas.response import UserOut
from srt.data_base.models import User
from srt.data_base.data_base import get_db
from srt.dependencies.redis_dependencies import Redis, get_redis
from srt.tokens import  get_current_user

router = APIRouter()

@router.get("/get_me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    return UserOut(
        user_id=current_user.user_id,
        username=current_user.username,
        full_name=current_user.full_name,
        created_at=current_user.created_at
    )


@router.get("/health")
async def health_check(
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis)
):
    # Проверка БД
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.error("Database connection failed")
        raise HTTPException(500, "Database unavailable")

    # Проверка Redis
    try:
        await redis.ping()
    except Exception:
        logger.error("Redis connection failed")
        raise HTTPException(500, "Redis unavailable")

    return {"status": "OK"}