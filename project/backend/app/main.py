from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.iot import router as iot_router
from app.api.auth import router as auth_router
from app.api.machines import router as machines_router
from app.api.queue import router as queue_router
from app.api.ws import router as ws_router
from app.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.limiter import limiter
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(machines_router)
app.include_router(queue_router)
app.include_router(ws_router)
app.include_router(admin_router)
app.include_router(iot_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
