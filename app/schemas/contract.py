from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ContractUploadResponse(BaseModel):
    id: int
    original_filename: str
    file_size: int
    file_type: str
    status: str
    created_at: datetime
    message: str = "계약서가 성공적으로 업로드되었습니다."
    model_config = {"from_attributes": True}


class ContractDetailResponse(BaseModel):
    id: int
    original_filename: str
    file_size: int
    file_type: str
    status: str
    contract_type: str
    extracted_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    analysis_completed_at: Optional[datetime] = None
    analysis: Optional["AnalysisResultResponse"] = None
    risk_clauses: Optional[List["RiskClauseResponse"]] = None
    clauses: Optional[List["ClauseResponse"]] = None
    compliance_results: Optional[List["ComplianceResultResponse"]] = None
    safety_score: Optional[int] = None
    safety_score_detail: Optional[Any] = None
    model_config = {"from_attributes": True}


class ContractListItem(BaseModel):
    id: int
    original_filename: str
    file_type: str
    status: str
    contract_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ContractListResponse(BaseModel):
    total: int
    contracts: List[ContractListItem]


class AnalysisResultResponse(BaseModel):
    key_info: Optional[Any] = None
    clauses: Optional[List[Any]] = None
    summary: Optional[str] = None
    detected_objects: Optional[List[Any]] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class RiskClauseResponse(BaseModel):
    id: int
    title: Optional[str] = None
    clause_number: Optional[str] = None
    original_text: str
    risk_type: str
    risk_level: str
    severity_score: Optional[int] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    problematic_text: Optional[str] = None
    evidence_clause_ids: Optional[List[str]] = None
    evidence_text: Optional[str] = None
    model_config = {"from_attributes": True}


class ClauseResponse(BaseModel):
    id: int
    clause_id: str
    title: Optional[str] = None
    text: str
    page_refs: Optional[List[int]] = None
    order: int
    model_config = {"from_attributes": True}


class ClauseListResponse(BaseModel):
    contract_id: int
    total: int
    clauses: List[ClauseResponse]


class ComplianceResultResponse(BaseModel):
    id: int
    clause_id: str
    clause_title: Optional[str] = None
    clause_text: str
    status: str
    reason: str
    law_references: Optional[List[Any]] = None
    model_config = {"from_attributes": True}


class AnalyzeAcceptedResponse(BaseModel):
    message: str
    status: str
    poll_url: str


class ContractStatusResponse(BaseModel):
    contract_id: int
    status: str
    contract_type: Optional[str] = None
    analysis_started_at: Optional[datetime] = None
    analysis_completed_at: Optional[datetime] = None
    error: Optional[str] = None
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
