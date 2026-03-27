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
    analysis: Optional["AnalysisResultResponse"] = None
    risk_clauses: Optional[List["RiskClauseResponse"]] = None
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
    clause_number: Optional[str] = None
    original_text: str
    risk_type: str
    risk_level: str
    explanation: Optional[str] = None
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
