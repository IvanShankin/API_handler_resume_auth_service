from typing import Optional

from pydantic import BaseModel


class ProducerMessage(BaseModel):
    topic: str
    value: dict | str | bytes
    key: Optional[str] = None