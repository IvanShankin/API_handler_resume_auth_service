import asyncio
import uvicorn
from fastapi import FastAPI
from srt.data_base.data_base import create_data_base
from srt.requests import main_router
from srt.dependencies import check_exists_topic
from config import KAFKA_TOPIC_NAME

app = FastAPI()

app.include_router(main_router)

if __name__ == '__main__':
    check_exists_topic(KAFKA_TOPIC_NAME)
    asyncio.run(create_data_base())
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=True
    )