from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.models.chat import ChatSession, ChatMessage, MessageSender, MessageType
from app.models.contract import Contract, ContractStatus
from app.models.analysis import ContractClause
from app.integrations.ai_client import ai_client


def _bump_session_counters(session: ChatSession, delta: int, at: datetime) -> None:
    session.total_message_count = (session.total_message_count or 0) + delta
    session.last_message_at = at


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
    _bump_session_counters(session, delta=1, at=datetime.now(timezone.utc))
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
    # 최신 대화 우선: last_message_at desc > updated_at desc > created_at desc.
    # (MySQL은 DESC 정렬에서 NULL을 마지막에 두므로 대화 없는 세션이 하단으로 내려감)
    # joinedload(contract): 목록 응답의 계약서 요약을 N+1 없이 함께 로드
    sessions = (
        query.options(joinedload(ChatSession.contract))
        .order_by(
            ChatSession.last_message_at.desc(),
            ChatSession.updated_at.desc(),
            ChatSession.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, sessions


def get_messages(session_id: int, user_id: int, db: Session, skip: int = 0, limit: int = 100):
    get_session_by_id(session_id, user_id, db)
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
    total = query.count()
    messages = query.order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    return total, messages


async def send_message(session_id: int, user_id: int, content: str, message_type: str, db: Session) -> tuple:
    session = get_session_by_id(session_id, user_id, db)

    # 사용자 메시지를 먼저 저장 — AI 호출 실패해도 사용자 입력은 기록됨
    user_msg = ChatMessage(
        session_id=session_id,
        sender=MessageSender.USER,
        message_type=MessageType(message_type) if message_type else MessageType.QUESTION,
        content=content,
    )
    db.add(user_msg)
    _bump_session_counters(session, delta=1, at=datetime.now(timezone.utc))
    db.commit()
    db.refresh(user_msg)

    # 계약서 연결 여부 및 분석 완료 여부 확인
    if not session.contract_id:
        # 계약서 없는 일반 채팅 — RAG 불가
        ai_content = "계약서가 연결되지 않은 세션입니다. 세션 생성 시 계약서를 지정해주세요."
        ai_extra = {}
    else:
        contract = db.query(Contract).filter(Contract.id == session.contract_id).first()
        if not contract or contract.status != ContractStatus.COMPLETED:
            # 분석 진행 중이거나 실패한 경우
            ai_content = "아직 계약서 분석이 완료되지 않았습니다. 분석 완료 후 질문해주세요."
            ai_extra = {}
        else:
            # 분석 완료 — clair-ai QA 호출
            ai_content, ai_extra = await _call_qa(contract.id, content, db)

    ai_msg = ChatMessage(
        session_id=session_id,
        sender=MessageSender.AI,
        message_type=MessageType.ANSWER,
        content=ai_content,
        extra_data=ai_extra,    # evidence_clause_ids, evidence_clauses 포함
    )
    db.add(ai_msg)
    _bump_session_counters(session, delta=1, at=datetime.now(timezone.utc))
    db.commit()
    db.refresh(ai_msg)
    return user_msg, ai_msg


async def _call_qa(contract_id: int, question: str, db: Session) -> tuple[str, dict]:
    """
    clair-ai QA 엔드포인트 호출.

    DB에서 조항 목록을 꺼내 AI에 함께 전달한다.
    AI는 이 조항들을 RAG 컨텍스트로 사용해 답변을 생성하므로
    OCR을 다시 실행할 필요가 없어 응답이 빠름 (보통 2~5초).

    실패 시 예외를 삼키고 fallback 메시지를 반환 —
    챗봇 오류로 전체 요청이 500으로 떨어지는 것을 방지.
    """
    # contract_clauses 테이블에서 해당 계약서 조항 전체 조회
    clauses = db.query(ContractClause).filter(
        ContractClause.contract_id == contract_id
    ).order_by(ContractClause.order).all()

    # AI에 전달할 형태로 직렬화 (clause_id가 evidence_clause_ids 반환에 사용됨)
    clause_dicts = [
        {"clause_id": c.clause_id, "title": c.title, "text": c.text}
        for c in clauses
    ]

    try:
        qa_resp = await ai_client.answer_question(
            contract_id=contract_id,
            question=question,
            clauses=clause_dicts,
        )

        # AI가 반환한 evidence_clause_ids로 실제 조항 텍스트 조회
        # 프론트에서 해당 조항을 하이라이트하거나 팝업으로 보여줄 때 사용
        evidence_rows = db.query(ContractClause).filter(
            ContractClause.contract_id == contract_id,
            ContractClause.clause_id.in_(qa_resp.evidence_clause_ids),
        ).all()

        evidence_data = [
            {"clause_id": c.clause_id, "title": c.title, "text": c.text[:300]}  # 300자 발췌
            for c in evidence_rows
        ]

        return qa_resp.answer, {
            "evidence_clause_ids": qa_resp.evidence_clause_ids,
            "evidence_clauses": evidence_data,      # ChatMessageResponse.metadata에 담겨 반환됨
        }

    except Exception as e:
        return "죄송합니다, 답변 생성 중 오류가 발생했습니다.", {"error": str(e)}


def delete_session(session_id: int, user_id: int, db: Session) -> None:
    session = get_session_by_id(session_id, user_id, db)
    db.delete(session)
    db.commit()
