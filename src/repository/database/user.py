from typing import Optional

from pydantic import EmailStr
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Users, RefreshToken
from src.exeptions.infrastructure_exc import NotEnoughArguments
from src.service.config.schemas import Config


class UserRepository:

    def __init__(self, session_db: AsyncSession, config: Config):
        self.session_db = session_db
        self.conf = config

    async def get_quantity_tokens(self, user_id: int) -> int:
        """
        :return int: Число refresh токенов по указанному id
        """
        tokens_the_current_user = await self.session_db.execute(
            select(func.count(RefreshToken.refresh_token_id))
            .where(RefreshToken.user_id == user_id)
        )
        return tokens_the_current_user.scalar()

    async def delete_the_oldest_token(self, user_id: int):
        """Если имеется самый старый refresh токен, то удалит его"""
        oldest_token = await self.session_db.execute(
            select(RefreshToken.refresh_token_id)
            .where(RefreshToken.user_id == user_id)
            .order_by(RefreshToken.expires_at.asc())
            .limit(1)
        )

        oldest_token_id = oldest_token.scalar()
        if oldest_token_id:
            await self.session_db.execute(
                delete(RefreshToken)
                .where(RefreshToken.refresh_token_id == oldest_token_id)
            )


    async def get_user(self, user_id: Optional[int] = None, username: Optional[str | EmailStr] = None) -> Users | None:
        if user_id is None and username is None:
            raise NotEnoughArguments(["user_id", "username"])

        if user_id:
            user = await self.session_db.execute(select(Users).where(Users.user_id == user_id))
        else:
            user = await self.session_db.execute(select(Users).where(Users.username == username))

        return user.scalar_one_or_none()

    async def add_user(self, username: str | EmailStr, hashed_password: str) -> Users:
        new_user = Users(
            username=username,
            hashed_password=hashed_password,
        )

        self.session_db.add(new_user)
        await self.session_db.flush()

        return new_user

