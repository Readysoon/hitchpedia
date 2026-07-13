"""FastAPI-App: bindet die Controller ein, initialisiert die DB beim Start."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .models import database
from .services import embeddings
from .controllers import info, search, contribute


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init()
    # Modell im HINTERGRUND laden, damit uvicorn sofort auf :8000 bindet.
    # Blockierender Warmup verzögerte das Binden um ~15-30s -> fly-proxy gab beim
    # Cold-Start auf (502). / und /e brauchen kein Modell; nur der erste /s wartet
    # ggf. kurz auf das Laden (per Lock gegen Doppel-Load abgesichert).
    app.state.warmup = asyncio.create_task(asyncio.to_thread(embeddings.warmup))
    yield
    app.state.warmup.cancel()
    database.pool.close()


app = FastAPI(title="hitchpedia", version="0.1.0", lifespan=lifespan)
app.include_router(info.router)
app.include_router(search.router)
app.include_router(contribute.router)
