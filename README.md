# clair-backend

CLAIR의 FastAPI 백엔드 (port 8000). 인증, 파일 관리, 계약서 CRUD, 채팅, 알림을 담당한다.

## 실행

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Swagger: http://localhost:8000/docs
```

### 초기 설정

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS clair_db DEFAULT CHARACTER SET utf8mb4;"
cp .env.example .env   # DB_PASSWORD, SECRET_KEY, GEMINI_API_KEY 수정

# DB 테이블 생성 (최초 1회)
alembic upgrade head
```

## API 엔드포인트

### 인증 (`/api/v1/auth`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/signup` | 회원가입 |
| POST | `/login/json` | 로그인 (JSON) |
| POST | `/refresh` | 토큰 갱신 |
| GET | `/me` | 내 정보 조회 |
| POST | `/email-verification/request` | 이메일 인증 코드 발송 |
| POST | `/email-verification/confirm` | 이메일 인증 확인 |
| POST | `/password-reset/request` | 비밀번호 재설정 메일 발송 |
| GET | `/google` `/naver` `/kakao` | 소셜 로그인 |

### 계약서 (`/api/v1/contracts`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/upload` | 계약서 파일 업로드 |
| GET | `/` | 계약서 목록 |
| GET | `/{id}` | 계약서 상세 + 분석 결과 + safety_score |
| DELETE | `/{id}` | 계약서 삭제 |
| POST | `/{id}/analyze` | 분석 요청 (202 Accepted, 백그라운드 실행) |
| GET | `/{id}/status` | 분석 상태 조회 |
| GET | `/{id}/clauses` | 조항 목록 |
| POST | `/{id}/share` | 공유 링크 생성 |
| GET | `/{id}/download/pdf` | 분석 결과 PDF 다운로드 |

### 채팅 (`/api/v1/chat`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/sessions` | 채팅 세션 생성 |
| GET | `/sessions` | 세션 목록 |
| POST | `/sessions/{id}/messages` | 메시지 전송 (Q&A) |
| GET | `/sessions/{id}/messages` | 대화 내역 |

### 기타
- `GET /api/v1/notifications` — 알림 목록
- `GET /api/v1/shares/{token}` — 공유 링크로 결과 조회

## 아키텍처

### 계약서 분석 상태 머신
`UPLOADED → PENDING → PROCESSING → COMPLETED / FAILED`

`POST /{id}/analyze` (202) → BackgroundTask 실행 → 독립 DB 세션 사용.  
프론트는 `GET /{id}` 또는 `GET /{id}/status`를 폴링하여 상태 확인.

BackgroundTask 예외는 로그에 출력되지 않으므로, PROCESSING에서 멈추면 직접 확인 필요.

### AI 연동 (`app/integrations/`)
- `ai_client.py` — `AIServiceClient` 싱글턴. 파일 경로를 clair-ai `/analyze`, `/qa`에 POST
- `ai_models.py` — clair-ai 응답 Pydantic 모델. **clair-ai가 새 필드를 추가하면 반드시 여기도 업데이트** (누락 시 validation 에러가 조용히 삼켜져 PROCESSING 상태에서 멈춤)
- `mappers.py` — AI 응답 → ORM 모델 변환

### 안전점수 (`app/services/scoring.py`)
`compute_safety_score(risk_clauses)` — 기본 100점에서 카테고리 가중치 × severity × confidence로 감점, 최솟값 25.  
`GET /{id}` 응답에 `safety_score`(int)와 `safety_score_detail`(dict) 포함.

### DB 마이그레이션 (Alembic)
```bash
alembic revision --autogenerate -m "설명"   # 마이그레이션 파일 자동 생성
alembic upgrade head                         # 적용
alembic downgrade -1                         # 롤백
```

## 환경 변수 (`.env`)

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=clair_db

UPLOAD_DIR=./uploads
SECRET_KEY=
GEMINI_API_KEY=
AI_SERVICE_URL=http://127.0.0.1:8001   # macOS는 localhost 대신 127.0.0.1
AI_SERVICE_TIMEOUT=300.0
CORS_ORIGINS=http://localhost:5173

# 소셜 로그인 (선택)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
```

> macOS에서 `localhost`가 IPv6(`::1`)로 resolve되어 uvicorn(IPv4) 연결 실패 가능. 모든 URL에 `127.0.0.1` 사용.
