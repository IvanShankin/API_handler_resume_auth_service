import os
from datetime import datetime, timedelta, UTC

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from srt.data_base.data_base import get_db
from srt.exception import InvalidCredentialsException
from srt.data_base.models import User

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')
ACCESS_TOKEN_EXPIRE_MINUTES = float(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
ALGORITHM = os.getenv('ALGORITHM')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()

    # Установка времени истечения токена
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Добавляем поле с временем истечения
    to_encode.update({"exp": expire})

    # Кодируем данные в JWT токен
    return jwt.encode(
        to_encode,  # Данные для кодирования
        SECRET_KEY,  # Секретный ключ из конфига
        algorithm=ALGORITHM  # Алгоритм шифрования
    )

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):

    try:
        # Декодируем токен
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True}
        )

        # Извлекаем ID пользователя
        user_id: str = payload.get("sub")
        if user_id is None:
            raise InvalidCredentialsException

    except JWTError:  # Ловим все ошибки JWT
        raise InvalidCredentialsException

    # Проверяем существование пользователя
    result = await db.execute(select(User).where(User.user_id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise InvalidCredentialsException

    return user