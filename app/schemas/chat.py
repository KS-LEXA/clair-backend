from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ChatSessionCreateRequest(BaseModel):
    contract_id: Optional[int] = None
    title: Optional[str] = "새 대화"


class ContractSummary(BaseModel):
    # 채팅 세션에 연결된 계약서 요약 — 프론트 호환을 위해 파일명을 여러 키로 함께 제공
    id: int
    original_filename: Optional[str] = None
    file_name: Optional[str] = None
    title: Optional[str] = None
    contract_type: Optional[str] = None
    status: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: int
    contract_id: Optional[int] = None
    title: str
    total_message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # 계약서 연결 세션이면 채워지고, 일반 상담 세션이면 None
    contract: Optional[ContractSummary] = None
    model_config = {"from_attributes": True}


class ChatSessionListItem(ChatSessionResponse):
    # 목록 화면에서만 채워지는 메타데이터 — 미리보기 카드용
    first_question: Optional[str] = None    # 사용자가 처음 보낸 질문
    last_question: Optional[str] = None     # 사용자가 마지막으로 보낸 질문
    last_answer: Optional[str] = None       # AI 마지막 응답


class ChatSessionListResponse(BaseModel):
    total: int
    sessions: List[ChatSessionListItem]


class SendMessageRequest(BaseModel):
    content: str
    message_type: Optional[str] = "question"


class ChatMessageResponse(BaseModel):
    id: int
    sender: str
    message_type: str
    content: str
    metadata: Optional[Any] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatMessagesListResponse(BaseModel):
    session_id: int
    total: int
    messages: List[ChatMessageResponse]


class SendMessageResponse(BaseModel):
    user_message: ChatMessageResponse
    ai_message: ChatMessageResponse
