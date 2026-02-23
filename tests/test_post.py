import pytest
from datetime import datetime
from fastapi import status
from sqlalchemy import select

from src.database.models import Users
from src.schemas.response import TokenResponse



@pytest.mark.asyncio
@pytest.mark.parametrize(
    'data_request, status_code',
    [
        ({"username": "test@example.com", "password": "string", "full_name": "string"}, 201),
        ({"username": "test@example.com", "password": "string", "full_name": "string"}, 409)
    ]
)
async def test_create_user(data_request, status_code, client_with_db, session_db, replace_producer):
    response = await client_with_db.post("/auth/register", json=data_request)

    if status_code == 201:
        assert response.status_code == status_code
        data_response = response.json()

        # данные с БД
        result_db = await session_db.execute(select(Users).where(Users.username == data_request['username']))
        data_db = result_db.scalar_one_or_none()

        assert replace_producer.all_message
        data_kafka = replace_producer.all_message[0].value

        assert data_db.user_id == data_response["user_id"] == data_kafka['user_id']
        assert data_db.username == data_request['username'] == data_response["username"] == data_kafka['username']
        assert data_request['full_name'] == data_response["full_name"] == data_kafka['full_name']
        assert datetime.fromisoformat(data_response["created_at"]) == datetime.fromisoformat(data_kafka['created_at'])

    elif 409: # создаём ещё одного юзера
        response = await client_with_db.post("/auth/register", json=data_request)
        assert response.status_code == status_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status_code',
    [
        200,
        401
    ]
)
async def test_login(
    status_code,
    client_with_db,
    user_service_fix,
):
    user_service = user_service_fix
    password = "strong_password"
    test_user = await user_service.register(
        username="test@mail.com",
        password=password,
        full_name="full_name"
    )

    if status_code == 200:
        response = await client_with_db.post(
            "/auth/login",
            data={
                'username': test_user.username,
                'password': password
            }
        )
        assert response.status_code == status_code

        # данные ответа сервера
        data_response = TokenResponse(**response.json())

        assert data_response.access_token
        assert data_response.refresh_token

    else:
        # запрос с неверными данными для входа
        response = await client_with_db.post(
            "/auth/login",
            data={
                'username': 'unfaithful_username',
                'password': 'unfaithful_password'
            }
        )
        assert response.status_code == status_code


        for i in range(15):
            response = await client_with_db.post(
                "/auth/login",
                data={
                    'username': 'unfaithful_username',
                    'password': 'unfaithful_password'
                }
            )
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        else:
            raise Exception("за 10 попыток входа так и не получили ошибку по количеству обращений к API")


@pytest.mark.asyncio
async def test_refresh_token(user_service_fix, client_with_db, fake_request):
    user_service = user_service_fix
    test_user = await user_service.register(
        username="test@mail.com",
        password="strong_password",
        full_name="full_name"
    )
    tokens = await user_service.login(
        request=fake_request(),
        username=test_user.username,
        password="strong_password"
    )

    response = await client_with_db.post(
        "/auth/refresh_token",
        json={
            'refresh_token': tokens.refresh_token
        }
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout(user_service_fix, fake_request, client_with_db):
    user_service = user_service_fix
    test_user = await user_service.register(
        username="test@mail.com",
        password="strong_password",
        full_name="full_name"
    )
    tokens = await user_service.login(
        request=fake_request(),
        username=test_user.username,
        password="strong_password"
    )

    response = await client_with_db.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens.access_token}"}
    )
    assert response.status_code == 200

    # с redis должны удалить
    result_witch_redis = await user_service.cache_repo.get_user(test_user.user_id)
    assert not result_witch_redis

    result_witch_db = await user_service.refresh_token_repo.validate_refresh_token(tokens.refresh_token)
    assert not result_witch_db
