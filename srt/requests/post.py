from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, func, cast, Boolean, delete
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, status, Request
from datetime import timedelta

from srt.schemas.request import UserCreate, LoginRequest, RefreshTokenRequest
from srt.schemas.response import TokenResponse, UserOut
from srt.data_base.models import User, RefreshToken, LoginAttempt
from srt.data_base.data_base import get_db
from srt.config import MAX_ACTIVE_SESSIONS, LOGIN_BLOCK_TIME, MAX_ATTEMPTS_ENTER_IN_N_MINUTES
from srt.tokens.refresh import REFRESH_TOKEN_EXPIRE_DAYS
from srt.exception import (UserAlreadyRegistered, InvalidCredentialsException, InvalidTokenException, UserNotFound,
                           ToManyAttemptsEnter)
from srt.tokens import (create_access_token, create_refresh_token, get_current_user, oauth2_scheme, get_hash_password,
                        verify_password)

router = APIRouter()


async def check_login_attempts(
    ip_address: str,
    login: str,
    db: AsyncSession
):
    """Проверяет количество неудачных попыток входа"""
    attempt_count = await db.scalar(
        select(func.count(LoginAttempt.attempt_id))
        .where(cast(
            (LoginAttempt.ip_address == ip_address) |
            (LoginAttempt.login == login), Boolean)
        )
        .where(LoginAttempt.attempt_time >= datetime.now(timezone.utc) - timedelta(minutes=5))
        .where(LoginAttempt.success == False)
    )

    if attempt_count >= MAX_ATTEMPTS_ENTER_IN_N_MINUTES:
        raise ToManyAttemptsEnter()

@router.post('/auth/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя"""
    # Проверяем, не зарегистрирован ли уже пользователь
    existing_user = await db.execute(select(User).where(User.login == user.login))
    if existing_user.scalar_one_or_none():
        raise UserAlreadyRegistered()

    # Хэшируем пароль
    hashed_password = get_hash_password(user.password)

    # Создаём пользователя
    new_user = User(
        login=user.login,
        hashed_password=hashed_password,
        full_name=user.full_name,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post('/auth/login', response_model=TokenResponse)
async def login(
        request: Request,
        login_data: LoginRequest,
        db: AsyncSession=Depends(get_db)
):
    # Получаем реальный IP из запроса
    client_ip = request.client.host

    user_db = await db.execute(select(User).where(cast(User.login == login_data.login, Boolean)))
    user = user_db.scalar()

    await check_login_attempts(client_ip, str(login_data.login), db)

    # если нет такого пользователя или пароль не совпадает
    if not user or not verify_password(login_data.password, user.hashed_password):
        # Логируем неудачную попытку
        attempt = LoginAttempt(
            user_id=user.user_id if user else None,
            ip_address=client_ip,
            login=login_data.login,  # Добавьте это поле в модель!
            success=False
        )
        db.add(attempt)
        await db.commit()
        raise InvalidCredentialsException()
    else:
        # Успешный вход - очищаем попытки
        await db.execute(
            delete(LoginAttempt)
            .where(cast(
                (LoginAttempt.ip_address == client_ip) |
                (LoginAttempt.login == login_data.login),
                Boolean
            ))
        )
        await db.commit()

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
    refresh_token = create_refresh_token(user.user_id)

    db_refresh_token = RefreshToken(
        user_id=user.user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(db_refresh_token)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

@router.post('/auth/refresh_token', response_model=TokenResponse)
async def refresh_token(
    access_token: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
        Обновление пары токенов по валидному refresh токену
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
    new_refresh_token = create_refresh_token(user.user_id)

    db_token.token = new_refresh_token
    db_token.expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    await db.commit()

    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token, token_type="bearer")