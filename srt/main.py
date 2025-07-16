import asyncio
import uvicorn
from fastapi import FastAPI
from srt.data_base.data_base import create_data_base
from srt.requests.post import router

app = FastAPI()

app.include_router(router)

if __name__ == '__main__':
    asyncio.run(create_data_base())
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=True
    )