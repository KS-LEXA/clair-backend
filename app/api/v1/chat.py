from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.chat import ChatMessage, MessageSender
from app.schemas.chat import ChatSessionCreateRequest, ChatSessionResponse, ChatSessionListItem, ChatSessionListResponse, SendMessageRequest, SendMessageResponse, ChatMessageResponse, ChatMessagesListResponse
from app.schemas.contract import MessageResponse
from app.services.chat_service import create_session, get_session_by_id, get_sessions_by_user, get_messages, send_message, delete_session

router = APIRouter()


def _contract_summary(contract) -> Optional[dict]:
    """연결된 계약서를 프론트가 쓰기 쉬운 요약 dict로. 미연결(또는 계약서 삭제)이면 None."""
    if contract is None:
        return None
    name = contract.original_filename
    return {
        "id": contract.id,
        "original_filename": name,
        "file_name": name,
        "title": name.rsplit(".", 1)[0] if name else None,
        "contract_type": contract.contract_type.value if contract.contract_type else None,
        "status": contract.status.value if contract.status else None,
    }


def _session_to_response_dict(session) -> dict:
    return {
        "id": session.id,
        "contract_id": session.contract_id,
        "title": session.title,
        "total_message_count": session.total_message_count or 0,
        "last_message_at": session.last_message_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "contract": _contract_summary(session.contract),
    }


def _fetch_message_extreme(db: Session, session_ids: list[int], sender: MessageSender, *, latest: bool) -> dict[int, str]:
    """
    세션 ID 리스트 → {session_id: 메시지 content}.
    latest=True면 가장 최근, False면 가장 오래된 메시지를 sender 기준으로 1건씩 가져옴.
    서브쿼리로 (session_id, MIN/MAX(created_at))을 묶고 본 테이블에 JOIN — 쿼리 1회.
    """
    if not session_ids:
        return {}
    agg = func.max(ChatMessage.created_at) if latest else func.min(ChatMessage.created_at)
    sub = (
        db.query(
            ChatMessage.session_id.label("sid"),
            agg.label("ts"),
        )
        .filter(
            ChatMessage.session_id.in_(session_ids),
            ChatMessage.sender == sender,
        )
        .group_by(ChatMessage.session_id)
        .subquery()
    )
    rows = (
        db.query(ChatMessage)
        .join(sub, and_(ChatMessage.session_id == sub.c.sid, ChatMessage.created_at == sub.c.ts))
        .all()
    )
    return {m.session_id: m.content for m in rows}


@router.post("/sessions", status_code=201, summary="채팅 세션 생성")
def api_create_session(body: ChatSessionCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = create_session(user_id=user.id, db=db, contract_id=body.contract_id, title=body.title or "새 대화")
    return ChatSessionResponse(**_session_to_response_dict(session))


@router.get("/sessions", response_model=ChatSessionListResponse, summary="채팅 세션 목록 (이력)")
def api_list_sessions(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total, sessions = get_sessions_by_user(user.id, db, skip, limit)
    session_ids = [s.id for s in sessions]

    # 페이지에 담긴 세션들의 첫 user 질문 / 마지막 user 질문 / 마지막 ai 응답을 각각 1쿼리로
    first_q = _fetch_message_extreme(db, session_ids, MessageSender.USER, latest=False)
    last_q = _fetch_message_extreme(db, session_ids, MessageSender.USER, latest=True)
    last_a = _fetch_message_extreme(db, session_ids, MessageSender.AI, latest=True)

    items = [
        ChatSessionListItem(
            **_session_to_response_dict(s),
            first_question=first_q.get(s.id),
            last_question=last_q.get(s.id),
            last_answer=last_a.get(s.id),
        )
        for s in sessions
    ]
    return ChatSessionListResponse(total=total, sessions=items)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse, summary="채팅 세션 상세")
def api_get_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_by_id(session_id, user.id, db)
    return ChatSessionResponse(**_session_to_response_dict(session))


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
