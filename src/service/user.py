from datetime import timezone, datetime, timedelta, UTC
from typing import Optional
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Users
from src.exeptions.service_exc import UserBlockError, LoginIsBusy, InvalidPassword, NotFoundRefreshToken, \
    UserNotFoundServ, InvalidJWTToken
from src.infrastructure.kafka.producer import ProducerKafka
from src.repository.database import UserRepository, RefreshTokenRepository
from src.repository.redis.user_cache import UserCacheRepository
from src.schemas.response import UserOut, TokenResponse
from src.service.config import get_config
from src.service.config.schemas import Config
from src.service.utils.logger import get_logger


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    scheme_name="OAuth2PasswordBearer",
    scopes={"read": "Read access", "write": "Write access"}
)

class UserService:

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        cache_repo: UserCacheRepository,
        producer: ProducerKafka,
        session_db: AsyncSession,
        config: Config,
    ):
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo
        self.cache_repo = cache_repo
        self.producer = producer
        self.session_db = session_db
        self.conf = config

        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto",  bcrypt__ident="2b")

    async def _get_user(self, user_id: int) -> Users | None:
        user_redis = await self.cache_repo.get_user(user_id)
        if not user_redis:
            user_db = await self.user_repo.get_user(user_id=user_id)
            if user_db:
                await self.cache_repo.set_user(user_db)

            return user_db

        return user_redis

    def _create_access_token(self, data: dict, expires_delta: timedelta = None):
        conf = get_config()
        to_encode = data.copy()

        # Установка времени истечения токена
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(minutes=conf.tokens.access_token_expire_minutes)

        # Добавляем поле с временем истечения
        to_encode.update({"exp": expire})

        # Кодируем данные в JWT токен
        return jwt.encode(
            to_encode,  # Данные для кодирования
            conf.env.secret_key,
            algorithm=conf.tokens.algorithm
        )

    async def _check_login_attempts(
        self,
        ip_address: str,
        username: str,
    ):
        """
        Проверяет количество неудачных попыток входа, если превышает лимит, то вызывает исключение
        :raise UserBlockError:
        """
        conf = get_config()

        if await self.cache_repo.get_login_block(ip_address, username):
            raise UserBlockError()

        # Логируем попытку
        attempts = await self.cache_repo.incr_login_attempt(ip_address, username)

        if attempts > conf.max_attempts_enter:
            await self.cache_repo.set_block_user(ip_address, username)
            raise UserBlockError()

    def _get_hash_password(self, password: str) -> str:
        """Преобразует пароль в хеш
        :return: хэш пароля"""
        return self.pwd_context.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Проверяет, совпадает ли пароль с хешем
        :param plain_password: простой пароль (qwerty)
        :param hashed_password: хэш пароля (gfdjkjvzvxccxa)
        :return: результат совпадения
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    async def get_current_user(self, token: str) -> Users:
        """
        :raise InvalidJWTToken: Невалидный токен
        :raise UserNotFoundServ: Пользователь не найден
        """
        try:
            # Декодируем токен
            payload = jwt.decode(
                token,
                self.conf.env.secret_key,
                algorithms=[self.conf.tokens.algorithm],
                options={"verify_exp": True}
            )

            # Извлекаем ID пользователя
            user_id: int = int(payload.get("sub"))
            if user_id is None:
                raise InvalidJWTToken()

            user = await self._get_user(user_id)
        except JWTError:  # Ловим все ошибки JWT
            raise InvalidJWTToken()

        if user is None:
            raise UserNotFoundServ()

        return user

    async def register(
        self,
        username: EmailStr | str,
        password: str,
        full_name: Optional[str] = None
    ) -> UserOut:
        """
            Регистрация нового пользователя. Вызовет исключение если данный логин занят
            :raise LoginIsBusy:
        """
        if await self.user_repo.get_user(username=username):
            raise LoginIsBusy()

        # Хэшируем пароль
        hashed_password = self._get_hash_password(password)

        new_user = await self.user_repo.add_user(username=username, hashed_password=hashed_password)
        await self.session_db.commit()

        data_create = datetime.now(timezone.utc)

        await self.producer.create_new_user(
            user_id=int(new_user.user_id),
            username=new_user.username,
            full_name=full_name,
            data_create=data_create
        )

        return UserOut(
            user_id=int(new_user.user_id),
            username=new_user.username,
            full_name=full_name,
            created_at=data_create
        )

    async def login(
        self,
        request: Request,
        username: str | EmailStr,
        password: str
    ) -> TokenResponse:
        """
        :raise UserBlockError: Если привешено количество попыток входа
        :raise InvalidPassword: Неверный пароль
        """
        username = username
        password = password
        client_ip = request.headers.get("x-forwarded-for", request.client.host)

        await self._check_login_attempts(client_ip, str(username))

        user = await self.user_repo.get_user(username=username)

        # если нет такого пользователя или пароль не совпадает
        if not user or not self._verify_password(password, user.hashed_password):
            raise InvalidPassword()

        quantity_tokens = await self.user_repo.get_quantity_tokens(user.user_id)

        if quantity_tokens and quantity_tokens >= get_config().max_active_sessions:  # если есть токены и их количество больше возможно
            await self.user_repo.delete_the_oldest_token(user.user_id)

        access_token = self._create_access_token(data={"sub": str(user.user_id)})

        refresh_token = None
        for _ in range(5):
            try:
                refresh_token = await self.refresh_token_repo.add_refresh_token(user.user_id)
                await self.session_db.commit()
                break
            except IntegrityError:
                await self.session_db.rollback()
        else:
            raise Exception("Failed to generate token")

        get_logger(__name__).info(f"User {user.user_id} logged in from IP {client_ip}")
        return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

    async def refresh_token(self, old_refresh_token: str) -> TokenResponse:
        """
        :raise NotFoundRefreshToken: Если токен не найден
        :raise UserNotFoundServ: Если пользователь не найден
        """
        old_refresh_token_obj = await self.refresh_token_repo.validate_refresh_token(old_refresh_token)
        if not old_refresh_token_obj:
            raise NotFoundRefreshToken()

        user = await self._get_user(old_refresh_token_obj.user_id)
        if not user:
            raise UserNotFoundServ()

        new_access_token = self._create_access_token(data={"sub": str(user.user_id)})

        new_refresh_token = None
        for _ in range(5):
            try:
                new_refresh_token = await self.refresh_token_repo.update_refresh_token(old_refresh_token)
                await self.session_db.commit()
                break
            except IntegrityError:
                await self.session_db.rollback()
        else:
            raise Exception("Failed to generate token")

        return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token.token, token_type="bearer")

    async def logout(self, user_id: int) -> bool:
        await self.cache_repo.delete_user(user_id)

        await self.refresh_token_repo.delete(user_id)
        await self.session_db.commit()

        return True


