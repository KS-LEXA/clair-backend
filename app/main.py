from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.init_db import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.chat import router as chat_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.shares import router as shares_router
from app.services.auth_service import PROFILE_IMAGE_SUBDIR


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

# 프로필 이미지만 정적 서빙 — 계약서 파일이 있는 UPLOAD_DIR 전체를 노출하지 않기 위해 하위 디렉토리만 마운트
_profile_image_dir = Path(settings.upload_dir) / PROFILE_IMAGE_SUBDIR
_profile_image_dir.mkdir(parents=True, exist_ok=True)
app.mount(f"/{PROFILE_IMAGE_SUBDIR}", StaticFiles(directory=str(_profile_image_dir)), name="profile-images")

app.include_router(auth_router, prefix="/api/v1/auth", tags=["인증"])
app.include_router(contracts_router, prefix="/api/v1/contracts", tags=["계약서"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["채팅"])
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["알림"])
app.include_router(shares_router, prefix="/api/v1/shares", tags=["공유 (외부 접근)"])


@app.get("/health", tags=["시스템"])
def healthcheck():
    return {"status": "ok", "service": settings.app_name}
