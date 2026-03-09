from datetime import datetime
from pydantic import BaseModel


class NewUser(BaseModel):
    user_id: int
    username: str
    full_name: str
    created_at: datetime