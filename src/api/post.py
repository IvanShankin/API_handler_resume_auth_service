from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, Depends, status, Request

from src.api.dependency_provider import get_current_user
from src.exeptions.service_exc import LoginIsBusy, UserBlockError, InvalidPassword, NotFoundRefreshToken, \
    UserNotFoundServ
from src.schemas.request import UserCreate, RefreshTokenRequest
from src.schemas.response import UserOut, TokenResponse
from src.service import get_user_service, UserService
from src.exeptions.http_exc import UserAlreadyRegistered, InvalidCredentialsException, InvalidTokenException, \
    UserNotFound, ToManyAttemptsEnter
from src.database.models import Users


router = APIRouter(prefix="/auth")


@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, user_service: UserService = Depends(get_user_service)):
    """
        Регистрация нового пользователя
        :raise UserAlreadyRegistered: code - 409
    """
    try:
        return await user_service.register(
            username=user.username,
            password=user.password,
            full_name=user.full_name
        )
    except LoginIsBusy:
        raise UserAlreadyRegistered()


@router.post('/login', response_model=TokenResponse, tags=["Authentication"],)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends(get_user_service)
):
    username = form_data.username
    password = form_data.password
    try:
        return await user_service.login(
            request=request,
            username=username,
            password=password
        )
    except UserBlockError:
        raise ToManyAttemptsEnter()
    except InvalidPassword:
        raise InvalidCredentialsException()


@router.post('/refresh_token', response_model=TokenResponse)
async def refresh_token(
    token: RefreshTokenRequest,
    user_service: UserService = Depends(get_user_service),
):
    """
        Обновление пары токенов по валидному refresh токен
        Требует:
        - refresh_token (из предыдущего успешного логина)
        Возвращает:
        - Новую пару access + refresh токенов
        :raise InvalidTokenException: Невалидный токен
        :raise UserNotFound: Пользователь не найден
    """
    try:
        return await user_service.refresh_token(
            old_refresh_token=token.refresh_token
        )
    except NotFoundRefreshToken:
        raise InvalidTokenException()
    except UserNotFoundServ:
        raise UserNotFound()


@router.post('/logout')
async def logout(
    current_user: Users = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Удаляет refresh токен у всех сессий"""
    await user_service.logout(current_user.user_id)

    return {"status": "success"}
