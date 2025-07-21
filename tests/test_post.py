import json
import os
import pytest

from datetime import datetime
from dotenv import load_dotenv
from confluent_kafka import KafkaError
from httpx import AsyncClient, ASGITransport
from fastapi import status
from sqlalchemy import select

from srt.data_base.models import User,RefreshToken
from srt.main import app
from tests.conftest import consumer


load_dotenv()  # Загружает переменные из .env
KAFKA_TOPIC_NAME= os.getenv('KAFKA_TOPIC_NAME')

@pytest.mark.asuncio
@pytest.mark.parametrize(
    'data_request, status_code',
    [
        ({"username": "test@example.com", "password": "string", "full_name": "string"}, 201),
        ({"username": "test@example.com", "password": "string", "full_name": "string"}, 409)
    ]
)
async def test_create_user(data_request, status_code, db_session, clearing_kafka):
    # подписка на топик
    consumer.subscribe([KAFKA_TOPIC_NAME])

    async with AsyncClient(
                transport=ASGITransport(app),
                base_url="http://test",
        ) as ac:
            response = await ac.post("/auth/register", json=data_request)

            if status_code == 201:
                assert response.status_code == status_code

                # данные с БД
                result_db = await db_session.execute(select(User).where(User.username == data_request['username']))
                data_db = result_db.scalar_one_or_none()

                # данные ответа сервера
                data_response = response.json()

                # данные с kafka
                data_kafka = None
                for i in range(40): # такой большой тайминг, ибо при пересоздании топика может быть большая задержка у первого сообщения
                    try:
                        msg = consumer.poll(timeout=1.0)
                        if msg is None:# если не успели отослать сообщение, а уже пытаемся его прочитать
                            if i == 39:
                                raise Exception("НЕ смогли получить сообщение от kafka!")
                            else:
                                continue

                        data_kafka = json.loads(msg.value().decode('utf-8'))
                        break
                    except KafkaError as e:
                        raise f"Ошибка Kafka: {e}"


                assert data_db.user_id == data_response["user_id"] == data_kafka['user_id']
                assert data_db.username == data_request['username'] == data_response["username"] == data_kafka['username']
                assert data_db.full_name == data_request['full_name'] == data_response["full_name"] == data_kafka['full_name']
                assert data_db.created_at == datetime.fromisoformat(data_response["created_at"]) == datetime.fromisoformat(data_kafka['created_at'])

            elif 409: # создаём ещё одного юзера
                response = await ac.post("/auth/register", json=data_request)
                assert response.status_code == status_code



@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status_code',
    [
        200,
        401
    ]

)
async def test_login(status_code, db_session, redis_session, create_user, clearing_redis):
    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        if status_code == 200:
            response = await ac.post("/auth/login", data={
                'username': create_user['username'],
                'password': create_user['password']
            })
            assert response.status_code == status_code

            # данные ответа сервера
            data_response = response.json()

            assert data_response['access_token']
            assert data_response['refresh_token']

        else:
            # запрос с неверными данными для входа
            response = await ac.post("/auth/login", data={
                'username': 'unfaithful_username',
                'password': 'unfaithful_password'
            })
            assert response.status_code == status_code

            # тест: много запросов на вход (тут проверяем работу redis)
            for i in range(10): # 10 раз будем пытаться войти в профиль
                response = await ac.post("/auth/login", data={
                    'username': 'incorrect_data',
                    'password': 'incorrect_data'
                })
                if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    break
            else:
                raise "за 10 попыток входа так и не получили ошибку по количеству обращений к API"


@pytest.mark.asyncio
async def test_refresh_token(create_user):
    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.post("/auth/refresh_token", json={
            'refresh_token': create_user['refresh_token']
        })
        assert response.status_code == 200



@pytest.mark.asyncio
async def test_logout(create_user, redis_session, db_session):
    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.post("/auth/logout", headers={"Authorization": f"Bearer {create_user['access_token']}"})
        assert response.status_code == 200

        result_witch_redis = await redis_session.get(f'user:{create_user['user_id']}')
        assert not result_witch_redis

        result_witch_db = await db_session.execute(select(RefreshToken)
        .where(
            RefreshToken.user_id == create_user['user_id']
        ))
        result_witch_db = result_witch_db.scalar_one_or_none()
        assert not result_witch_db
