import json
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import select, func, cast, Boolean, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, Request, Form
from datetime import timedelta

from srt.dependencies import redis_client, producer, get_redis
from srt.schemas.request import UserCreate, RefreshTokenRequest
from srt.schemas.response import TokenResponse, UserOut
from srt.data_base.models import User, RefreshToken
from srt.data_base.data_base import get_db
from srt.config import MAX_ACTIVE_SESSIONS, LOGIN_BLOCK_TIME, MAX_ATTEMPTS_ENTER
from srt.tokens.refresh import REFRESH_TOKEN_EXPIRE_DAYS
from srt.config import logger
from srt.exception import (UserAlreadyRegistered, InvalidCredentialsException, InvalidTokenException, UserNotFound,
                           ToManyAttemptsEnter)
from srt.tokens import (create_access_token, create_refresh_token, get_current_user, get_hash_password,
                        verify_password)

load_dotenv()
KAFKA_TOPIC_NAME = os.getenv('KAFKA_TOPIC_NAME')

router = APIRouter()


async def check_login_attempts(
    ip_address: str,
    username: str,
):

    """Проверяет количество неудачных попыток входа"""
    # Проверяем блокировку в Redis
    block_key = f"login_block:{ip_address}:{username}"
    if await redis_client.get(block_key):
        raise ToManyAttemptsEnter()

    # Логируем попытку в Redis
    attempt_key = f"login_attempt:{ip_address}:{username}"
    attempts = await redis_client.incr(attempt_key)
    await redis_client.expire(attempt_key, LOGIN_BLOCK_TIME) # Устанавливаем TTL для ключа

    # Если превышено количество попыток - блокируем
    if attempts > MAX_ATTEMPTS_ENTER:
        await redis_client.setex(block_key, LOGIN_BLOCK_TIME, "1")
        raise ToManyAttemptsEnter()

@router.post('/auth/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя"""
    # Проверяем, не зарегистрирован ли уже пользователь
    existing_user = await db.execute(select(User).where(User.username == user.username))
    if existing_user.scalar_one_or_none():
        raise UserAlreadyRegistered()

    # Хэшируем пароль
    hashed_password = get_hash_password(user.password)

    # Создаём пользователя
    new_user = User(
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    producer.sent_message(
        topic=KAFKA_TOPIC_NAME,
        key=f'user_{new_user.user_id}',
        value=json.dumps({
            'user_id': int(new_user.user_id),
            'username': new_user.username,
            'full_name': new_user.full_name,
            'created_at': str(new_user.created_at),
        }).encode('utf-8')
    )

    return new_user


@router.post('/auth/login', response_model=TokenResponse, tags=["Authentication"],)
async def login(
        request: Request,
        username: str = Form(...),  # Для совместимости со Swagger UI
        password: str = Form(...),  # Для совместимости со Swagger UI
        db: AsyncSession = Depends(get_db)
):
    # Получаем реальный IP из запроса
    client_ip = request.headers.get("x-forwarded-for", request.client.host)

    await check_login_attempts(client_ip, str(username))

    user_db = await db.execute(select(User).where(cast(User.username == username, Boolean)))
    user = user_db.scalar()

    # если нет такого пользователя или пароль не совпадает
    if not user or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsException()

    tokens_the_current_user = await db.execute(
        select(func.count(RefreshToken.id))
        .where(cast(RefreshToken.user_id == user.user_id,Boolean))
    ) # получим число токенов с переданным id

    quantity_tokens = tokens_the_current_user.scalar()

    if quantity_tokens and quantity_tokens >= MAX_ACTIVE_SESSIONS: # если есть токены и их количество больше возможно
        # Находим ID самого старого токена
        oldest_token = await db.execute(
            select(RefreshToken.id)
            .where(cast(RefreshToken.user_id == user.user_id, Boolean))
            .order_by(RefreshToken.expires_at.asc())
            .limit(1)
        )

        oldest_token_id = oldest_token.scalar()
        if oldest_token_id:
            await db.execute(
                delete(RefreshToken)
                .where(cast(RefreshToken.id == oldest_token_id, Boolean))
            )

    access_token = create_access_token(data={"sub": str(user.user_id)})
    refresh_token = await create_refresh_token(db)

    db_refresh_token = RefreshToken(
        user_id=user.user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(db_refresh_token)
    await db.commit()

    logger.info(f"User {user.user_id} logged in from IP {client_ip}")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

@router.post('/auth/refresh_token', response_model=TokenResponse)
async def refresh_token(
    access_token: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
        Обновление пары токенов по валидному refresh токен
        Требует:
        - refresh_token (из предыдущего успешного логина)
        Возвращает:
        - Новую пару access + refresh токенов
    """

    result_token_db = await db.execute(select(RefreshToken).where(access_token.refresh_token == RefreshToken.token))
    db_token = result_token_db.scalar_one_or_none()
    if not db_token:
        raise InvalidTokenException()

    user = await db.get(User, db_token.user_id)
    if not user:
        raise UserNotFound()

    new_access_token = create_access_token(data={"sub": str(user.user_id)})
    new_refresh_token = await create_refresh_token(db)

    db_token.token = new_refresh_token
    db_token.expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    await db.commit()

    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token, token_type="bearer")


@router.post('/auth/logout')
async def logout(
        current_user: User = Depends(get_current_user),
        redis_client: Redis = Depends(get_redis),
        db: AsyncSession = Depends(get_db)
):
    """Удаляет refresh токен у всех сессий"""
    # Удаляем из Redis
    await redis_client.delete(f"user:{current_user.user_id}")

    # Удаляем refresh-токены из БД (опционально)
    await db.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == current_user.user_id)
    )
    await db.commit()

    return {"status": "success"}
