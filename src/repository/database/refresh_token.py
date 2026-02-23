import secrets
from datetime import timedelta, UTC, datetime
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import RefreshToken
from src.service.config.schemas import Config


class RefreshTokenRepository:

    def __init__(self, session_db: AsyncSession, config: Config):
        self.session_db = session_db
        self.conf = config

    def _generate_unique_token(self) -> str:
        return secrets.token_urlsafe(64)

    async def add_refresh_token(self, user_id: int) -> str:
        expires_at = datetime.now(UTC) + timedelta(
            days=self.conf.tokens.refresh_token_expire_days
        )

        token = self._generate_unique_token()

        db_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        self.session_db.add(db_token)

        return token


    async def validate_refresh_token(self, refresh_token: str) -> Optional[RefreshToken | None]:
        """
        :return int: user_id по указанному токену если он действителен
        """
        result = await self.session_db.execute(
            select(RefreshToken)
            .where(RefreshToken.token == refresh_token)
            .where(RefreshToken.expires_at >= datetime.now(UTC))
        )
        db_token: RefreshToken | None = result.scalar_one_or_none()
        return db_token

    async def update_refresh_token(self, old_token: str, expires_at: Optional[datetime] = None) -> RefreshToken | None:
        token = self._generate_unique_token()

        if expires_at is None:
            expires_at = datetime.now(UTC) + timedelta(
                days=self.conf.tokens.refresh_token_expire_days
            )

        result_db = await self.session_db.execute(
            update(RefreshToken)
            .where(RefreshToken.token == old_token)
            .values(
                token=token,
                expires_at=expires_at,
                created_at=datetime.now(UTC),
            )
            .returning(RefreshToken)
        )

        return result_db.scalar_one_or_none()

    async def delete(self, user_id):
        """Удалит все токены связанный с указанным ID"""

        await self.session_db.execute(
            delete(RefreshToken)
            .where(RefreshToken.user_id == user_id)
        )