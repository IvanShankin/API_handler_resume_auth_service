from datetime import datetime

import pytest
from httpx import AsyncClient, ASGITransport
from srt.main import app


@pytest.mark.asyncio
async def test_health(create_user, redis_session, db_session):
    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.get("/health", headers={"Authorization": f"Bearer {create_user['access_token']}"})
        assert response.status_code == 200
