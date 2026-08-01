# AI Integration Plan — clair-backend × clair-ai

## 연동 방식 결정: HTTP 마이크로서비스

clair-ai를 **별도 FastAPI 프로세스(localhost:8001)**로 띄우고, clair-backend가 `httpx`로 호출하는 구조.

**이유:**
- PaddleOCR + YOLOv8 + torch 의존성이 무거워 같은 프로세스에 직접 import하면 백엔드 startup 망가짐
- Celery는 Redis/RabbitMQ 인프라가 없어서 패스
- localhost HTTP는 사실상 함수 호출 수준의 레이턴시

---

## 전체 흐름

### 분석 흐름
```
POST /api/v1/contracts/{id}/analyze
  → 202 즉시 반환 (status: pending)
  → BackgroundTask: PENDING → PROCESSING → AI 호출 → DB 저장 → COMPLETED/FAILED

GET /api/v1/contracts/{id}/status   ← 프론트가 3-5초마다 폴링
GET /api/v1/contracts/{id}          ← COMPLETED 되면 전체 결과 조회
```

### 채팅 QA 흐름
```
POST /api/v1/chat/sessions/{id}/messages
  → DB에서 contract_clauses 조회
  → ai_client.answer_question(question, clauses)
  → evidence_clause_ids 포함 응답 저장 및 반환
```

---

## Phase 1 — DB 모델 수정

### 수정: `app/models/contract.py`

**ContractType enum 추가값:**
- `NDA = "nda"` — AI "nda"
- `SERVICE = "service"` — AI "service" (용역)
- `EMPLOYMENT = "employment"` — AI "employment" (근로)

**ContractStatus enum 추가값:**
- `PENDING = "pending"` — 분석 요청됨, 아직 시작 안 됨

**Contract 모델 추가 컬럼:**
```python
analysis_error = Column(Text, nullable=True)
analysis_started_at = Column(DateTime, nullable=True)
analysis_completed_at = Column(DateTime, nullable=True)
ocr_pages = Column(JSON, nullable=True)   # [{page_index, text}]
```

### 수정: `app/models/analysis.py`

**신규 모델 ContractClause (`contract_clauses` 테이블):**
```python
class ContractClause(Base):
    __tablename__ = "contract_clauses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    clause_id = Column(String(50), nullable=False)    # "clause-001" — AI가 생성하는 ID
    title = Column(String(500), nullable=True)
    text = Column(Text, nullable=False)
    page_refs = Column(JSON, nullable=True)           # [0, 1] 등 페이지 번호 리스트
    order = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

**RiskClause 추가 컬럼:**
```python
evidence_clause_ids = Column(JSON, nullable=True)   # ["clause-001", "clause-003"]
evidence_text = Column(Text, nullable=True)
```

**AnalysisResult 추가 컬럼:**
```python
raw_ocr_text = Column(Text, nullable=True)
analysis_duration_seconds = Column(Integer, nullable=True)
```

---

## Phase 2 — 연동 레이어 (신규 파일)

### `app/integrations/ai_models.py`
AI 서비스가 반환하는 JSON 구조를 Pydantic으로 정의.

### `app/integrations/ai_client.py`
```python
class AIServiceClient:
    async def analyze_contract(contract_id, file_path, file_type, document_id) -> AIAnalysisResponse
    async def answer_question(contract_id, question, clauses) -> AIQAResponse
    async def health_check() -> bool

ai_client = AIServiceClient(base_url=settings.ai_service_url)  # 싱글턴
```

### `app/integrations/mappers.py`
AI 출력 → ORM 변환 순수 함수들:
```python
def ai_contract_type_to_enum(ai_value: str) -> ContractType
def ai_analysis_to_analysis_result(ai_resp, contract_id) -> AnalysisResult
def ai_risks_to_risk_clauses(risks, contract_id) -> list[RiskClause]
def ai_clauses_to_contract_clauses(clauses, contract_id) -> list[ContractClause]
```

---

## Phase 3 — 서비스 레이어 수정

### `app/services/contract_service.py` 추가
- `trigger_analysis()` — status를 PENDING으로 바꾸고 반환
- `analyze_contract_background()` — **자체 SessionLocal()** 사용, AI 호출 후 결과 저장
- `get_analysis_status()` — 상태 폴링용

### `app/services/chat_service.py` 수정
- `send_message` → `async def`로 변경
- TODO 스텁 → 조항 조회 + `ai_client.answer_question()` 호출

---

## Phase 4 — API 레이어 수정

### `app/schemas/contract.py` 추가
- `AnalyzeAcceptedResponse` — 202 응답 (message, status, poll_url)
- `ContractStatusResponse` — 폴링 응답 (contract_id, status, error 등)
- `ClauseResponse`, `ClauseListResponse`
- `RiskClauseResponse` 확장 (evidence_clause_ids, evidence_text 추가)

### `app/api/v1/contracts.py` 수정
- `POST /{id}/analyze` → async, BackgroundTasks, 202 반환
- `GET /{id}/status` 신규 추가
- `GET /{id}/clauses` 신규 추가 (선택)

### `app/api/v1/chat.py` 수정
- `api_send_message` → `async def`

---

## Phase 5 — clair-ai 서버

### `clair-ai/src/api/main.py` 신규
```
POST /analyze   — 파일 경로 받아서 전체 분석 후 AIAnalysisResponse 반환
POST /qa        — 조항 리스트 + 질문 받아서 AIQAResponse 반환
GET  /health    — 상태 확인
```

### `clair-ai/pyproject.toml` 수정
- `fastapi`, `uvicorn[standard]` 의존성 추가

---

## Phase 6 — 환경변수 및 문서

- `.env`에 `AI_SERVICE_URL=http://localhost:8001` 추가
- `core/config.py`에 `ai_service_url` 설정 추가
- `CLAUDE.md` 업데이트

---

## 해결되는 문제 목록

| 문제 | 해결 방법 |
|------|-----------|
| ContractType enum 불일치 | NDA/SERVICE/EMPLOYMENT 추가, mapper 함수로 변환 |
| analyze가 동기 + 폴링 없음 | BackgroundTasks + PENDING 상태 + GET /{id}/status |
| 채팅 블로킹 | async send_message + await ai_client |
| RiskClause evidence 필드 없음 | evidence_clause_ids(JSON), evidence_text(Text) 추가 |
| Clause 테이블 없음 | contract_clauses 신규 테이블 |
| OCR 다중 페이지 미지원 | ocr_pages(JSON) 컬럼 추가 |
| integrations/ 비어있음 | ai_client.py + ai_models.py + mappers.py |

---

## 구현 순서 (파일 단위)

1. `app/models/contract.py` — enum 추가, 컬럼 추가
2. `app/models/analysis.py` — ContractClause 신규, RiskClause/AnalysisResult 컬럼 추가
3. `app/db/init_db.py` — ContractClause import
4. `app/core/config.py` — ai_service_url 추가
5. `app/integrations/ai_models.py` — 신규
6. `app/integrations/ai_client.py` — 신규
7. `app/integrations/mappers.py` — 신규
8. `app/services/contract_service.py` — 백그라운드 태스크 추가
9. `app/services/chat_service.py` — async 전환 + RAG 연결
10. `app/schemas/contract.py` — 스키마 추가
11. `app/api/v1/contracts.py` — 엔드포인트 수정/추가
12. `app/api/v1/chat.py` — async 전환
13. `clair-ai/src/api/main.py` — 신규
14. `clair-ai/pyproject.toml` — 의존성 추가
