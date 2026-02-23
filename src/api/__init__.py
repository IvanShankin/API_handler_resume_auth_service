from fastapi import APIRouter

from src.api.post import router

main_router = APIRouter()
main_router.include_router(router)

__all__ = ['main_router']