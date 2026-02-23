from typing import Optional
from fastapi import FastAPI

from src.api import main_router


_app: Optional[FastAPI] = None


def _include_router(app: FastAPI):
    app.include_router(main_router)


def init_fastapi_app() -> FastAPI:
    global _app
    app = FastAPI(
        title="Auth Service"
    )
    _include_router(app)
    _app = app

    return app


def get_app():
    global _app
    if _app is None:
        raise RuntimeError("FastAPI App not initialized")
    return _app
