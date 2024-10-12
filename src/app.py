from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .app_data import app_data
from .db import get_db
from .config import PREPARATORY_QUERIES_FILE
from .router import router


@asynccontextmanager
async def lifespan(app_: FastAPI):
    session = await get_db().__anext__()
    version_query = await session.execute(text('PRAGMA user_version;'))
    version = version_query.scalar()
    if version < 99:
        with open(PREPARATORY_QUERIES_FILE) as f:
            for stmt in f.read().split('\n\n'):
                await session.execute(text(stmt))
        await session.commit()

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
