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
    # status와 동일한 분석 생애주기 값(uploaded/pending/processing/completed/failed).
    # 프론트가 분석 완료 판단에 사용 — analysis 페이로드와 항상 일관되게 내려간다.
    analysis_status: str
    contract_type: str
    extracted_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # 분석 job 식별/신선도 — 재분석 시 프론트가 최신 결과 여부를 검증하는 데 사용.
    job_id: Optional[str] = None
    analysis_requested_at: Optional[datetime] = None
    analysis_updated_at: Optional[datetime] = None
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
    # status와 동일한 분석 생애주기 값 — 프론트 분석 완료 판단용
    analysis_status: str
    contract_type: str
    # 분석 완료(COMPLETED) 계약서만 0~100 정수, 그 외에는 null.
    # 상세 API(GET /contracts/{id})의 safety_score와 동일 기준(compute_safety_score)
    safety_score: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ContractListResponse(BaseModel):
    total: int
    contracts: List[ContractListItem]


class DeletedContractItem(BaseModel):
    id: int                              # 이력 행 id
    original_contract_id: int            # 삭제된 원본 계약서 id
    original_filename: str
    file_type: Optional[str] = None
    contract_type: Optional[str] = None
    status_at_deletion: Optional[str] = None
    contract_created_at: Optional[datetime] = None  # 원본 업로드 일시
    deleted_at: datetime
    model_config = {"from_attributes": True}


class DeletedContractListResponse(BaseModel):
    total: int
    deleted_contracts: List[DeletedContractItem]


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
    contract_id: int
    # 이번 분석 job 식별자 (contract_id + 요청 시각으로 파생). 재분석마다 새 값.
    job_id: Optional[str] = None
    analysis_requested_at: Optional[datetime] = None
    # 재분석 강제 요청 여부 (프론트가 보낸 force 플래그 에코)
    force: bool = False


class ContractStatusResponse(BaseModel):
    contract_id: int
    # 폴링 중인 상태가 어느 job의 것인지 식별 — analyze 응답의 job_id와 비교
    job_id: Optional[str] = None
    status: str
    contract_type: Optional[str] = None
    analysis_requested_at: Optional[datetime] = None
    analysis_started_at: Optional[datetime] = None
    # 마지막 상태 변경 시각 (Contract.updated_at). 진행 갱신 추적용.
    analysis_updated_at: Optional[datetime] = None
    # 재분석 중에는 None. status==completed 이고 이 값이 requested_at 이후일 때만 신뢰.
    analysis_completed_at: Optional[datetime] = None
    error: Optional[str] = None
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
