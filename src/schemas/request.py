from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    username: EmailStr
    password: str
    full_name: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

