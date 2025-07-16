from pydantic import BaseModel, EmailStr

# Для регистрации нового пользователя (POST /register)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

# Для входа в систему (POST /login)
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Для обновления токена (POST /refresh)
class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Для смены пароля (POST /change-password)
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

