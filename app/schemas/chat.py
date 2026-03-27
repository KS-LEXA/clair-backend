from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ChatSessionCreateRequest(BaseModel):
    contract_id: Optional[int] = None
    title: Optional[str] = "새 대화"


class ChatSessionResponse(BaseModel):
    id: int
    contract_id: Optional[int] = None
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None
    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    total: int
    sessions: List[ChatSessionResponse]


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
