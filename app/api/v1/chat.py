from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.chat import ChatSessionCreateRequest, ChatSessionResponse, ChatSessionListResponse, SendMessageRequest, SendMessageResponse, ChatMessageResponse, ChatMessagesListResponse
from app.schemas.contract import MessageResponse
from app.services.chat_service import create_session, get_session_by_id, get_sessions_by_user, get_messages, send_message, delete_session

router = APIRouter()


@router.post("/sessions", status_code=201, summary="채팅 세션 생성")
def api_create_session(body: ChatSessionCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = create_session(user_id=user.id, db=db, contract_id=body.contract_id, title=body.title or "새 대화")
    return ChatSessionResponse(id=session.id, contract_id=session.contract_id, title=session.title,
                               created_at=session.created_at, updated_at=session.updated_at)


@router.get("/sessions", response_model=ChatSessionListResponse, summary="채팅 세션 목록 (이력)")
def api_list_sessions(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total, sessions = get_sessions_by_user(user.id, db, skip, limit)
    session_list = []
    for s in sessions:
        last_msg = None
        if s.messages:
            last_msg = s.messages[-1].content[:50] + "..." if len(s.messages[-1].content) > 50 else s.messages[-1].content
        session_list.append(ChatSessionResponse(id=s.id, contract_id=s.contract_id, title=s.title,
                                                created_at=s.created_at, updated_at=s.updated_at, last_message=last_msg))
    return ChatSessionListResponse(total=total, sessions=session_list)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse, summary="채팅 세션 상세")
def api_get_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_by_id(session_id, user.id, db)
    return ChatSessionResponse(id=session.id, contract_id=session.contract_id, title=session.title,
                               created_at=session.created_at, updated_at=session.updated_at)


@router.delete("/sessions/{session_id}", response_model=MessageResponse, summary="채팅 세션 삭제")
def api_delete_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_session(session_id, user.id, db)
    return MessageResponse(message="채팅 세션이 삭제되었습니다.")


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse, summary="메시지 전송")
async def api_send_message(session_id: int, body: SendMessageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_msg, ai_msg = await send_message(session_id=session_id, user_id=user.id, content=body.content, message_type=body.message_type, db=db)
    return SendMessageResponse(
        user_message=ChatMessageResponse(id=user_msg.id, sender=user_msg.sender.value, message_type=user_msg.message_type.value,
                                         content=user_msg.content, metadata=user_msg.extra_data, created_at=user_msg.created_at),
        ai_message=ChatMessageResponse(id=ai_msg.id, sender=ai_msg.sender.value, message_type=ai_msg.message_type.value,
                                       content=ai_msg.content, metadata=ai_msg.extra_data, created_at=ai_msg.created_at))


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesListResponse, summary="대화 내역 조회")
def api_get_messages(session_id: int, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total, messages = get_messages(session_id, user.id, db, skip, limit)
    return ChatMessagesListResponse(session_id=session_id, total=total, messages=[
        ChatMessageResponse(id=m.id, sender=m.sender.value, message_type=m.message_type.value,
                            content=m.content, metadata=m.extra_data, created_at=m.created_at)
        for m in messages])
