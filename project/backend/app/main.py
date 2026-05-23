from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 테이블 생성 (프로토타입용 — 추후 alembic으로 교체)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ESG — 기숙사 세탁기 예약 서비스", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
