from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


# ── 공유 생성 / 목록 / 해제 (소유자) ─────────────────────────────────────────

class ShareCreateRequest(BaseModel):
    password: str = Field(min_length=4, description="공유받은 사람이 입력할 비밀번호 (4자 이상)")
    expire_days: Optional[int] = Field(default=None, ge=1, le=30, description="만료일 (1~30일, 미지정 시 기본 7일)")


class ShareCreateResponse(BaseModel):
    id: int
    token: str
    share_url: str
    expires_at: datetime
    created_at: datetime
    model_config = {"from_attributes": True}


class ShareListItem(BaseModel):
    id: int
    token: str
    share_url: str
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    created_at: datetime
    is_active: bool
    model_config = {"from_attributes": True}


class ShareListResponse(BaseModel):
    contract_id: int
    total: int
    shares: List[ShareListItem]


# ── 공유받은 사람용 (비로그인) ──────────────────────────────────────────────

class ShareVerifyRequest(BaseModel):
    password: str


class ShareVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class SharedRiskClause(BaseModel):
    clause_number: Optional[str] = None
    risk_type: str
    risk_level: str
    explanation: Optional[str] = None
    evidence_clause_ids: Optional[List[str]] = None
    evidence_text: Optional[str] = None
    model_config = {"from_attributes": True}


class SharedAnalysisResult(BaseModel):
    key_info: Optional[Any] = None
    summary: Optional[str] = None


class SharedContractResponse(BaseModel):
    """공유받은 사람에게 노출되는 데이터 — 분석 결과 + 위험 조항 + 근거만."""
    contract_id: int
    original_filename: str
    contract_type: str
    analysis: Optional[SharedAnalysisResult] = None
    risk_clauses: List[SharedRiskClause] = []
