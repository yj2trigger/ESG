from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.machines import router as machines_router
from app.api.queue import router as queue_router
from app.api.ws import router as ws_router
from app.core.database import Base, SessionLocal, engine
from app.repositories import machine_repo
import app.models  # noqa: F401 — register all models with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        machine_repo.seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="ESG — 기숙사 세탁기 예약 서비스", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(machines_router)
app.include_router(queue_router)
app.include_router(ws_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
