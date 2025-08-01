import asyncio
import uvicorn
import os
from dotenv import load_dotenv
from fastapi import FastAPI

from srt.data_base.data_base import create_data_base
from srt.requests import main_router
from srt.dependencies import check_exists_topic

load_dotenv()
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA = os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')

app = FastAPI()

app.include_router(main_router)

if __name__ == '__main__':
    check_exists_topic(KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA)
    asyncio.run(create_data_base())
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )