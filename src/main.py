import asyncio
import uvicorn

from src.api.app import init_fastapi_app
from src.database.creating import create_database
from src.infrastructure.kafka import init_producer, shutdown_producer
from src.infrastructure.kafka.admin_client import init_admin_client, shutdown_admin_client
from src.infrastructure.kafka.topic_manager import check_exists_topic
from src.infrastructure.redis.core import init_redis, close_redis
from src.service.config import init_config


async def on_startup():
    init_fastapi_app()
    conf = init_config()

    await init_redis()
    await create_database()

    await init_admin_client()
    await init_producer()
    await check_exists_topic(conf.env.kafka_topic_producer_for_uploading_data)


async def on_shutdown():
    await close_redis()
    await shutdown_producer()
    await shutdown_admin_client()


if __name__ == '__main__':
    asyncio.run(on_startup())

    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )
    finally:
        asyncio.run(on_shutdown())
