# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLAIR Backend is a FastAPI-based AI contract analysis system (Korean-language app). It handles contract document upload, AI-powered analysis (Gemini), and chat-based Q&A (LangChain RAG). The backend uses MySQL with SQLAlchemy ORM and JWT-based authentication with social login support (Google, Naver, Kakao).

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database (MySQL required)
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS clair_db DEFAULT CHARACTER SET utf8mb4;"

# Run dev server
uvicorn app.main:app --reload --port 8000

# API docs
# Swagger: http://localhost:8000/docs
# ReDoc:   http://localhost:8000/redoc
# Health:  http://localhost:8000/health
```

There is currently no test runner configured. The `tests/` directory exists but is empty.

## Architecture

The app follows a layered architecture: **API → Services → Models/DB**.

- **[app/api/v1/](app/api/v1/)** — Route handlers only; no business logic. Three routers: `auth`, `contracts`, `chat`.
- **[app/services/](app/services/)** — All business logic lives here. Services receive a SQLAlchemy `db` session and current user as arguments.
- **[app/models/](app/models/)** — SQLAlchemy ORM models (`User`, `SocialAccount`, `Contract`, `AnalysisResult`, `RiskClause`, `ChatSession`, `ChatMessage`).
- **[app/schemas/](app/schemas/)** — Pydantic v2 request/response DTOs. Separate from models.
- **[app/core/config.py](app/core/config.py)** — Pydantic Settings loaded from `.env`. Single `settings` singleton used throughout.
- **[app/core/security.py](app/core/security.py)** — JWT creation/decoding, password hashing, and `get_current_user` FastAPI dependency.
- **[app/db/session.py](app/db/session.py)** — SQLAlchemy engine and `get_db()` dependency. `get_db()` is injected into every route that touches the DB.
- **[app/db/init_db.py](app/db/init_db.py)** — `init_db()` called on startup (via lifespan in `main.py`) to create all tables via `Base.metadata.create_all()`.
- **[app/integrations/](app/integrations/)** — clair-ai HTTP 연동 계층: `ai_client.py`(싱글턴 HTTP 클라이언트), `ai_models.py`(clair-ai 응답 Pydantic 스키마), `mappers.py`(AI 응답 → ORM 변환 순수 함수). **clair-ai 응답 포맷이 바뀌면 `ai_models.py`를 반드시 함께 갱신** — 그렇지 않으면 BackgroundTask 안에서 Pydantic 검증 에러가 조용히 삼켜져 계약서가 PROCESSING에서 멈춤.

## Key Design Patterns

**Authentication flow**: `OAuth2PasswordBearer` → `get_current_user` dependency extracts user from JWT Bearer token. Access tokens expire in 60 min, refresh tokens in 7 days. Social login (Google/Naver/Kakao) uses OAuth2 authorization code flow — the callback endpoints exchange the code for tokens via `httpx`, then call `_social_login()` in [app/services/auth_service.py](app/services/auth_service.py) which upserts `SocialAccount` + `User` records and issues app JWTs. Social users have `password_hash=None`.

**Contract file storage**: Uploaded files are stored under `UPLOAD_DIR` organized by date (`YYYY/MM/DD/`). The `stored_filename` in the DB is a UUID-based name; `original_filename` preserves the user-facing name. Allowed formats: `.pdf,.png,.jpg,.jpeg,.txt,.docx`; max size defaults to 20 MB (configurable via `MAX_FILE_SIZE_MB`).

**AI integration**: `POST /api/v1/contracts/{id}/analyze` (202) runs `analyze_contract_background()` as a FastAPI `BackgroundTask` with its own DB session (`PENDING → PROCESSING → COMPLETED/FAILED`); the frontend polls `GET /api/v1/contracts/{id}`. `chat_service.send_message()` calls clair-ai `/qa` with the contract's `ContractClause` rows. Both live in [app/services/contract_service.py](app/services/contract_service.py) and [app/services/chat_service.py](app/services/chat_service.py) and call clair-ai through [app/integrations/ai_client.py](app/integrations/ai_client.py).

**Safety Score**: `compute_safety_score(risk_clauses)` in [app/services/scoring.py](app/services/scoring.py) — 100점 기준 카테고리 가중치 × severity × confidence 감점. `GET /api/v1/contracts/{id}` 응답에 `safety_score`, `safety_score_detail`, 그리고 `clauses`·`compliance_results`(조항/법령 준수 결과)를 포함.

**Alembic** is configured ([alembic/env.py](alembic/env.py) injects `settings.database_url` and imports all models). 모델 컬럼 추가 시: `python -m alembic revision --autogenerate -m "설명"` → `python -m alembic upgrade head`. `python -m alembic check`로 모델-DB 동기화 확인. (`init_db()`의 `create_all()`도 여전히 startup에서 실행되므로 신규 테이블은 자동 생성됨)

## Environment Variables

Required in `.env`:
```
DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=20
SECRET_KEY
GEMINI_API_KEY
AI_SERVICE_URL=http://127.0.0.1:8001   # macOS: localhost 대신 반드시 127.0.0.1 (IPv6 resolve 회피)
AI_SERVICE_TIMEOUT=300.0
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Social login (optional — leave empty to disable)
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REDIRECT_URI
KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET, KAKAO_REDIRECT_URI
```

Default redirect URIs point to `http://localhost:8000/api/v1/auth/{provider}/callback`.
