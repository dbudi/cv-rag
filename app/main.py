import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import documents, query, summary
from app.config import settings
from app.db.models import Base
from app.db.session import engine

logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="CV RAG POC",
    description="RAG system for CV summarization & Q&A (HRD internal tool)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(documents.router)
app.include_router(summary.router)
app.include_router(query.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
