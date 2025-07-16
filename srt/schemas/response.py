from datetime import datetime
from pydantic import BaseModel, EmailStr

# Данные пользователя (GET /me)
class UserOut(BaseModel):
    user_id: int
    login: str
    full_name: str
    created_at: datetime

# Токены (POST /login, POST /refresh)
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

# Используются для совместимости с SQLAlchemy моделями
class UserInDB(UserOut):
    hashed_password: str  # Никогда не возвращаем в ответах!

    class Config:
        from_attributes = True  # Ранее orm_mode=True (для работы с ORM)