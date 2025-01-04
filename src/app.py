from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .app_data import app_data
from .db import get_db
from .repo import prepare_data
from .router import router


@asynccontextmanager
async def lifespan(app_: FastAPI):
    session = await get_db().__anext__()
    await prepare_data(session)
    await app_data.get_exchange_rates(session)
    await session.close()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
