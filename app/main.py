"""FastAPI-App: bindet die Controller ein, initialisiert die DB beim Start."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .models import database
from .controllers import info, search, contribute


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init()
    yield
    database.pool.close()


app = FastAPI(title="hitchpedia", version="0.1.0", lifespan=lifespan)
app.include_router(info.router)
app.include_router(search.router)
app.include_router(contribute.router)
