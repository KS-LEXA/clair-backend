from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.init_db import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.app_name} 서버 시작")
    init_db()
    yield
    print("👋 서버 종료")


app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["인증"])
app.include_router(contracts_router, prefix="/api/v1/contracts", tags=["계약서"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["채팅"])


@app.get("/health", tags=["시스템"])
def healthcheck():
    return {"status": "ok", "service": settings.app_name}
