from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI

from src.api import main_router
from src.database.creating import create_database
from src.infrastructure.kafka import init_producer, shutdown_producer
from src.infrastructure.kafka.admin_client import init_admin_client, shutdown_admin_client
from src.infrastructure.kafka.topic_manager import check_exists_topic
from src.infrastructure.redis.core import init_redis, close_redis
from src.service.config import init_config
from src.service.utils.logger import setup_logging

_app: Optional[FastAPI] = None


def _include_router(app: FastAPI):
    app.include_router(main_router)


def init_fastapi_app() -> FastAPI:
    global _app
    app = FastAPI(
        title="Auth Service",
        lifespan=lifespan
    )
    _include_router(app)
    _app = app

    return app


def get_app():
    global _app
    if _app is None:
        raise RuntimeError("FastAPI App not initialized")
    return _app


@asynccontextmanager
async def lifespan(app: FastAPI):
    conf = init_config()
    setup_logging(conf.paths.log_file)

    await init_redis()
    await create_database()

    await init_admin_client()
    await init_producer()
    await check_exists_topic(conf.kafka_topics.all_topics)

    try:
        yield
    finally:
        await close_redis()
        await shutdown_producer()
        await shutdown_admin_client()