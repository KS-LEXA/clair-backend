from __future__ import annotations

"""
clair-ai 서비스가 반환하는 JSON 응답 구조를 Pydantic으로 정의.

clair-ai의 AI_DEVELOPMENT_PLAN.md §5 "최소 인터페이스 정의" 기준.
이 파일의 타입들은 ai_client.py가 파싱에 사용하고,
mappers.py가 ORM 객체로 변환할 때 입력으로 받는다.
"""
from typing import Any, Optional
from pydantic import BaseModel


# AI가 분리한 조항 1개
class AIClause(BaseModel):
    clause_id: str          # ex) "clause-001" — ContractClause.clause_id와 1:1 대응
    title: Optional[str] = None
    text: str
    page_refs: list[int] = []   # 등장 페이지 번호 목록
    order: int                  # 문서 내 순서


# AI 추출 필드 공통 래퍼 — 값이 없을 때 null + 사유를 함께 반환하는 구조
# ex) {"value": null, "reason": "날짜 패턴 미검출"}
class AIFieldValue(BaseModel):
    value: Optional[Any] = None
    reason: Optional[str] = None


# 계약서 핵심 정보 추출 결과
class AIExtractionResult(BaseModel):
    contract_type: AIFieldValue     # "nda" | "service" | "employment" | "unknown"
    counterparty_a: AIFieldValue    # 갑 (계약 당사자 A)
    counterparty_b: AIFieldValue    # 을 (계약 당사자 B)
    signing_date: AIFieldValue      # 서명일 "YYYY-MM-DD" or null
    start_date: AIFieldValue        # 계약 시작일
    end_date: AIFieldValue          # 계약 종료일
    amount_text: AIFieldValue       # 금액 원문 ex) "5,000만원"
    amount_value: AIFieldValue      # 금액 숫자 ex) 50000000.0


# 위험 조항 탐지 결과 1건
class AIRiskResult(BaseModel):
    risk_type: str                      # auto_renewal | termination | liability | payment | other
    severity: str                       # low | medium | high
    reason: str                         # 위험한 이유 설명
    evidence_clause_ids: list[str] = [] # 근거 조항 ID 목록 — ContractClause.clause_id 참조
    evidence_text: str = ""             # 해당 조항에서 발췌한 원문


# YOLOv8 비전 탐지 결과 1건 (인감·서명·체크 표식)
class AIVisionObject(BaseModel):
    page_index: int
    label: str          # seal | signature | checkmark
    confidence: float   # 0.0 ~ 1.0
    bbox: dict          # {x1, y1, x2, y2} 픽셀 좌표


# POST /analyze 전체 응답 — clair-ai가 반환하는 최상위 구조
class AIAnalysisResponse(BaseModel):
    document_id: str
    clauses: list[AIClause] = []
    extraction: AIExtractionResult
    risks: list[AIRiskResult] = []
    summary: str = ""
    detected_objects: list[AIVisionObject] = []
    ocr_raw_text: str = ""              # OCR 원문 (정제 전)
    ocr_pages: list[dict] = []          # [{page_index, text}] 페이지별 텍스트


# POST /qa 응답 — 질의응답 결과
class AIQAResponse(BaseModel):
    question: str
    answer: str
    evidence_clause_ids: list[str] = [] # 답변 근거가 된 조항 ID 목록
