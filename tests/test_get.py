from datetime import datetime

import pytest
from httpx import AsyncClient, ASGITransport
from srt.main import app


@pytest.mark.asyncio
async def test_logout(create_user, redis_session, db_session):
    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.get("/get_me", headers={"Authorization": f"Bearer {create_user['access_token']}"})
        assert response.status_code == 200

        result_response = response.json()

        assert create_user['user_id'] == result_response['user_id']
        assert create_user['username'] == result_response['username']
        assert create_user['full_name'] == result_response['full_name']
        assert create_user['created_at'] == datetime.fromisoformat(result_response['created_at'])


@pytest.mark.asyncio
async def test_logout(create_user, redis_session, db_session):
    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.get("/health", headers={"Authorization": f"Bearer {create_user['access_token']}"})
        assert response.status_code == 200


        # ПРИ ВХОДЕ ПРОВЕРИТЬ СОХРАНЕНИЕ ТОКЕНА В REDIS