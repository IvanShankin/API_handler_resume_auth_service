from datetime import datetime
from pydantic import BaseModel, EmailStr

class UserForGetCurrentUser(BaseModel):
    user_id: int
    username: str

class UserOut(BaseModel):
    user_id: int
    username: str
    full_name: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
