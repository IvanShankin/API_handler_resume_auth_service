from pydantic import BaseModel


class ProducerMessage(BaseModel):
    topic: str
    key: str
    value: dict | str | bytes