# clair-backend

CLAIR의 FastAPI 백엔드 (port 8000). 인증/소셜 로그인, 파일 관리, 계약서 CRUD·분석, 채팅 Q&A, 공유 링크, 알림을 담당한다.
AI 분석 자체는 별도 서비스(`clair-ai`, port 8001)가 수행하며, 이 백엔드는 LLM을 직접 호출하지 않고 clair-ai의 `/analyze`·`/qa`에 요청한다.

## 실행

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Swagger: http://localhost:8000/docs · ReDoc: /redoc · Health: /health
```

### 초기 설정

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS clair_db DEFAULT CHARACTER SET utf8mb4;"
cp .env.example .env   # DB_PASSWORD, SECRET_KEY, AI_SERVICE_URL 등 수정

# DB 테이블 생성 (최초 1회)
alembic upgrade head
```

> 런타임은 **Python 3.9** (venv). 테스트 러너는 설정돼 있지 않으므로(`tests/`는 비어 있음) 변경은 서버를 띄워 엔드포인트로 검증한다.

## API 엔드포인트

### 인증 (`/api/v1/auth`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/signup` | 회원가입 (사전 이메일 인증 필요) |
| POST | `/login` | 로그인 (Swagger 자물쇠 겸용, form) |
| POST | `/login/json` | 로그인 (JSON) |
| POST | `/refresh` | 토큰 갱신 |
| GET | `/me` | 내 정보 조회 |
| PATCH | `/me/nickname` | 닉네임 변경 |
| PATCH | `/me/password` | 비밀번호 변경 |
| DELETE | `/me` | 회원 탈퇴 (계정·연관 데이터 영구 삭제) |
| DELETE | `/me/profile-image` | 프로필 이미지 삭제 |
| POST | `/email-verification/request` | 이메일 인증 코드 발송 |
| POST | `/email-verification/confirm` | 이메일 인증 코드 확인 |
| POST | `/password-reset/request` | 비밀번호 재설정 메일 발송 |
| GET | `/password-reset/verify` | 재설정 토큰 유효성 검증 |
| POST | `/password-reset/confirm` | 비밀번호 재설정 확정 |
| GET | `/google` `/naver` `/kakao` | 소셜 로그인 시작 |
| GET | `/{provider}/callback` | 소셜 로그인 콜백 (프론트로 리다이렉트) |

### 계약서 (`/api/v1/contracts`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/upload` | 계약서 파일 업로드 (다중 이미지는 PDF로 병합) |
| GET | `/` | 계약서 목록 |
| GET | `/deleted` | 계약서 삭제 이력 조회 |
| GET | `/{id}` | 계약서 상세 + 분석 결과 + safety_score |
| DELETE | `/{id}` | 계약서 삭제 |
| POST | `/{id}/analyze` | 분석 요청 (202 Accepted, 백그라운드 실행) |
| POST | `/{id}/request-analysis` | `/analyze` 호환용 별칭 (동일 로직) |
| GET | `/{id}/status` | 분석 상태 조회 |
| GET | `/{id}/clauses` | 조항 목록 |
| POST | `/{id}/share` | 공유 링크 생성 |
| GET | `/{id}/shares` | 공유 링크 목록 |
| DELETE | `/{id}/shares/{share_id}` | 공유 링크 해제 |
| GET | `/{id}/download/pdf` | 분석 결과 PDF 다운로드 (COMPLETED만) |

### 채팅 (`/api/v1/chat`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/sessions` | 채팅 세션 생성 |
| GET | `/sessions` | 세션 목록 (이력) |
| GET | `/sessions/{id}` | 세션 상세 |
| DELETE | `/sessions/{id}` | 세션 삭제 |
| POST | `/sessions/{id}/messages` | 메시지 전송 (Q&A) |
| GET | `/sessions/{id}/messages` | 대화 내역 |

### 알림 (`/api/v1/notifications`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `` | 알림 전체 조회 |
| GET | `/grouped` | 그룹별 조회 (Today / This Week) |
| GET | `/unread-count` | 읽지 않은 알림 수 |
| PATCH | `/{id}/read` | 알림 읽음 처리 |
| PATCH | `/read-all` | 전체 읽음 처리 |

### 공유 (`/api/v1/shares`) — 비로그인 접근
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/{token}` | 공유받은 계약서 분석 결과 조회 (법령 준수 검사 결과 포함) |
| POST | `/{token}/verify` | 공유 비밀번호 검증 |

## 아키텍처

레이어 구조: **API (`app/api/v1/`) → Services (`app/services/`) → Models/DB (`app/models/`, `app/db/`)**.
라우트 핸들러는 얇게 유지하고 비즈니스 로직은 서비스에 둔다. Pydantic v2 DTO(`app/schemas/`)는 ORM 모델과 분리.

### 계약서 분석 상태 머신
`UPLOADED → PENDING → PROCESSING → COMPLETED / FAILED`

`POST /{id}/analyze` (202) → `analyze_contract_background`를 BackgroundTask로 실행 → **독립 `SessionLocal()` 사용**(요청 스코프 `db`는 이미 닫힘).
프론트는 `GET /{id}` 또는 `GET /{id}/status`를 폴링하여 상태 확인.

> BackgroundTask 예외는 요청으로 전파되지 않고 삼켜진다. PROCESSING에서 멈추면 백그라운드 작업의 미처리 예외 또는 AI 응답 스키마 불일치를 의심할 것.

### AI 연동 (`app/integrations/`)
- `ai_client.py` — `AIServiceClient` 싱글턴. clair-ai와 통신하는 **유일한** 지점. 서버 로컬 파일 경로를 `/analyze`에, 직렬화된 조항 dict를 `/qa`에 전달
- `ai_models.py` — clair-ai 응답 Pydantic 모델. **clair-ai가 새 필드를 추가하면 반드시 여기도 업데이트** (누락 시 validation 에러가 백그라운드에서 조용히 삼켜져 PROCESSING 상태에서 멈춤)
- `mappers.py` — AI 응답 → ORM 모델 변환

### 안전점수 (`app/services/scoring.py`)
`compute_safety_score(risk_clauses)` — 기본 100점에서 `CATEGORY_WEIGHTS[risk_type] × severity × confidence`로 감점, 최솟값 25. 백엔드에서 계산(AI가 아님).
`GET /{id}` 응답에 `safety_score`(int)와 `safety_score_detail`(dict) 포함.

### PDF 보고서 (`app/services/pdf_service.py`)
WeasyPrint(HTML→PDF)로 Jinja2 템플릿(`app/templates/pdf/contract_report.html`)을 렌더링. 위험도·영문 값 등은 렌더 시점에 한글 라벨로 변환(데이터/응답은 변형하지 않음).
> macOS: WeasyPrint가 pango/glib를 dlopen하나 SIP가 자식 프로세스의 `DYLD_*`를 제거하므로, weasyprint import **전에** `DYLD_FALLBACK_LIBRARY_PATH`를 설정한다(모듈 상단 순서 유지).

### 파일 저장
업로드 계약서는 `UPLOAD_DIR/YYYY/MM/DD/`에 UUID 파일명으로 저장(원본명 보존). 허용: `.pdf,.png,.jpg,.jpeg,.txt,.docx`, 최대 20MB.
프로필 이미지는 `UPLOAD_DIR/profile_images/`에 별도 저장되며 **정적 서빙되는 유일한 경로**(계약서 파일은 웹 노출 안 됨). 허용: `.png,.jpg,.jpeg,.webp`, 최대 5MB.

### DB 스키마 / 마이그레이션
스키마는 세 갈래로 관리됨 — `create_all`(부팅 시 누락 테이블 생성), **Alembic(소스 오브 트루스)**, `scripts/`의 수동 SQL(공유/운영 DB에 직접 적용). 스키마 변경 시 항상 Alembic 마이그레이션을 작성한다.

```bash
alembic revision --autogenerate -m "설명"   # 마이그레이션 파일 자동 생성
alembic upgrade head                         # 적용
alembic downgrade -1                         # 롤백
```
> 새 모델은 `app/db/init_db.py`에서 import해야 `create_all`/autogenerate가 인식한다.

## 환경 변수 (`.env`)

전체 목록과 기본값은 `.env.example` 및 `app/core/config.py` 참고. 핵심만 발췌:

```
# DB (필수)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=clair_db

# 파일 / 인증 (필수)
UPLOAD_DIR=./uploads
SECRET_KEY=                               # openssl rand -hex 32
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# clair-ai 연동 (분석/채팅)
AI_SERVICE_URL=http://127.0.0.1:8001      # macOS는 localhost 대신 127.0.0.1
AI_SERVICE_TIMEOUT=600.0                  # OCR+다단계 LLM 분석 최대 ~5분

# CORS / 베이스 URL
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
BACKEND_BASE_URL=http://localhost:8000    # 프로필 이미지 절대 URL 생성
FRONTEND_BASE_URL=http://localhost:5173   # 메일 링크 / 공유 링크

# 이메일 (선택, 인증/비번 재설정 메일)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=

# 소셜 로그인 (선택, 비우면 비활성화)
GOOGLE_CLIENT_ID=  GOOGLE_CLIENT_SECRET=  GOOGLE_REDIRECT_URI=
NAVER_CLIENT_ID=   NAVER_CLIENT_SECRET=   NAVER_REDIRECT_URI=
KAKAO_CLIENT_ID=   KAKAO_CLIENT_SECRET=   KAKAO_REDIRECT_URI=

# 공유
SHARE_PATH=/share
SHARE_TOKEN_DEFAULT_EXPIRE_DAYS=7
SHARE_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> macOS에서 `localhost`가 IPv6(`::1`)로 resolve되어 uvicorn(IPv4) 연결 실패 가능. 백엔드↔clair-ai URL에는 `127.0.0.1` 사용.
