from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.chat import ChatSession, ChatMessage, MessageSender, MessageType
from app.models.contract import Contract


def create_session(user_id: int, db: Session, contract_id: int = None, title: str = "새 대화") -> ChatSession:
    if contract_id:
        contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == user_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계약서를 찾을 수 없습니다.")
        if title == "새 대화":
            title = contract.original_filename
    session = ChatSession(user_id=user_id, contract_id=contract_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    welcome = ChatMessage(session_id=session.id, sender=MessageSender.SYSTEM, message_type=MessageType.TEXT, content="계약서를 업로드하거나 질문을 입력해주세요.")
    db.add(welcome)
    db.commit()
    return session


def get_session_by_id(session_id: int, user_id: int, db: Session) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="채팅 세션을 찾을 수 없습니다.")
    return session


def get_sessions_by_user(user_id: int, db: Session, skip: int = 0, limit: int = 20):
    query = db.query(ChatSession).filter(ChatSession.user_id == user_id)
    total = query.count()
    sessions = query.order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
    return total, sessions


def get_messages(session_id: int, user_id: int, db: Session, skip: int = 0, limit: int = 100):
    get_session_by_id(session_id, user_id, db)
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
    total = query.count()
    messages = query.order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    return total, messages


def send_message(session_id: int, user_id: int, content: str, message_type: str, db: Session) -> tuple:
    session = get_session_by_id(session_id, user_id, db)
    user_msg = ChatMessage(session_id=session_id, sender=MessageSender.USER,
                           message_type=MessageType(message_type) if message_type else MessageType.QUESTION, content=content)
    db.add(user_msg)
    # TODO: 조서현 파트 - Gemini API / LangChain RAG 호출
    ai_response = f"'{content}'에 대한 분석 결과입니다.\n\n(AI 모듈 연동 예정)"
    ai_msg = ChatMessage(session_id=session_id, sender=MessageSender.AI, message_type=MessageType.ANSWER,
                         content=ai_response, extra_data={"source_clauses": [], "note": "AI 연동 전 임시 응답"}
)
    db.add(ai_msg)
    session.updated_at = func.now()
    db.commit()
    db.refresh(user_msg)
    db.refresh(ai_msg)
    return user_msg, ai_msg


def delete_session(session_id: int, user_id: int, db: Session) -> None:
    session = get_session_by_id(session_id, user_id, db)
    db.delete(session)
    db.commit()
