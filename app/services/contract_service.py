from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.contract import Contract, ContractStatus
from app.models.analysis import AnalysisResult, RiskClause, ContractClause
from app.integrations.ai_client import ai_client
from app.integrations.mappers import (
    ai_contract_type_to_enum,
    ai_clauses_to_contract_clauses,
    ai_risks_to_risk_clauses,
    ai_analysis_to_analysis_result,
)
from app.models.notification import NotificationType
from app.services.notification_service import create_notification


def _validate_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="파일명이 없습니다.")
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"지원하지 않는 파일 형식입니다: {file_ext}")


def _get_mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mime_map = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".txt": "text/plain",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    return mime_map.get(ext, "application/octet-stream")


async def upload_contract(file: UploadFile, user_id: int, db: Session) -> Contract:
    _validate_file(file)
    upload_dir = Path(settings.upload_dir)
    today = datetime.now()
    date_dir = upload_dir / today.strftime("%Y") / today.strftime("%m") / today.strftime("%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix.lower()
    stored_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = date_dir / stored_filename

    file_size = 0
    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > settings.max_file_size_bytes:
                    f.close()
                    os.remove(file_path)
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"파일 크기가 {settings.max_file_size_mb}MB를 초과합니다.")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"파일 저장 중 오류: {str(e)}")

    contract = Contract(user_id=user_id, original_filename=file.filename, stored_filename=stored_filename,
                        file_path=str(file_path), file_size=file_size, file_type=file_ext,
                        mime_type=_get_mime_type(file.filename), status=ContractStatus.UPLOADED)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def get_contract_by_id(contract_id: int, user_id: int, db: Session) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == user_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계약서를 찾을 수 없습니다.")
    return contract


def get_contracts_by_user(user_id: int, db: Session, skip: int = 0, limit: int = 20):
    query = db.query(Contract).filter(Contract.user_id == user_id)
    total = query.count()
    contracts = query.order_by(Contract.created_at.desc()).offset(skip).limit(limit).all()
    return total, contracts


def delete_contract(contract_id: int, user_id: int, db: Session) -> None:
    contract = get_contract_by_id(contract_id, user_id, db)
    if os.path.exists(contract.file_path):
        os.remove(contract.file_path)
    db.delete(contract)
    db.commit()


def get_clauses(contract_id: int, user_id: int, db: Session) -> list[ContractClause]:
    """분석 완료된 계약서의 조항 목록 반환. 챗봇 RAG 및 프론트 조항 표시에 사용."""
    get_contract_by_id(contract_id, user_id, db)  # 소유권 검증
    return db.query(ContractClause).filter(
        ContractClause.contract_id == contract_id
    ).order_by(ContractClause.order).all()


def trigger_analysis(contract_id: int, user_id: int, db: Session) -> Contract:
    """
    분석 요청 수락 단계.
    상태를 PENDING으로 바꾸고 반환만 한다.
    실제 AI 호출은 analyze_contract_background()가 담당.
    """
    contract = get_contract_by_id(contract_id, user_id, db)
    if contract.status == ContractStatus.PROCESSING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 분석 중입니다.")
    contract.status = ContractStatus.PENDING
    contract.analysis_error = None  # 재분석 시 이전 오류 초기화
    db.commit()
    db.refresh(contract)
    return contract


async def analyze_contract_background(contract_id: int) -> None:
    """
    FastAPI BackgroundTasks로 실행되는 AI 분석 함수.

    주의: 이 함수는 HTTP 응답이 반환된 뒤 실행된다.
    request의 db 세션은 이미 닫혀 있으므로,
    SessionLocal()로 독립적인 DB 세션을 직접 열어야 한다.

    흐름:
      PENDING → PROCESSING → (AI 호출) → COMPLETED
                                        → FAILED (예외 발생 시)
    """
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return

        # PROCESSING 전환 — 폴링 중인 프론트에 "진행 중" 상태 노출
        contract.status = ContractStatus.PROCESSING
        contract.analysis_started_at = datetime.now(timezone.utc)
        db.commit()

        started_at = datetime.now(timezone.utc)

        # clair-ai 분석 요청 (OCR + 조항 분리 + 추출 + 요약 + 리스크)
        ai_resp = await ai_client.analyze_contract(
            contract_id=contract.id,
            file_path=contract.file_path,
            file_type=contract.file_type,
            document_id=str(contract.id),
        )
        duration = int((datetime.now(timezone.utc) - started_at).total_seconds())

        # 재분석 케이스: 이전 분석 데이터 삭제 후 새로 저장
        db.query(AnalysisResult).filter(AnalysisResult.contract_id == contract_id).delete()
        db.query(RiskClause).filter(RiskClause.contract_id == contract_id).delete()
        db.query(ContractClause).filter(ContractClause.contract_id == contract_id).delete()

        # 조항 먼저 저장 — RiskClause.evidence_clause_ids가 이 clause_id를 참조하므로 순서 중요
        clause_rows = ai_clauses_to_contract_clauses(ai_resp.clauses, contract_id)
        db.add_all(clause_rows)

        # 분석 결과 저장
        analysis = ai_analysis_to_analysis_result(ai_resp, contract_id, duration_seconds=duration)
        db.add(analysis)

        # 위험 조항 저장
        risk_rows = ai_risks_to_risk_clauses(ai_resp.risks, contract_id)
        db.add_all(risk_rows)

        # 계약서 상태 업데이트
        contract.status = ContractStatus.COMPLETED
        contract.contract_type = ai_contract_type_to_enum(ai_resp.extraction.contract_type.value or "unknown")
        contract.extracted_text = ai_resp.ocr_raw_text  # 하위 호환 — 단일 텍스트 필드
        contract.ocr_pages = ai_resp.ocr_pages          # 페이지별 OCR 결과
        contract.analysis_completed_at = datetime.now(timezone.utc)
        db.commit()

        # 분석 완료 알림
        create_notification(
            user_id=contract.user_id,
            title=f"'{contract.original_filename}' 분석이 완료되었습니다.",
            db=db,
            notification_type=NotificationType.ANALYSIS_COMPLETE,
            contract_id=contract.id,
        )

    except Exception as e:
        db.rollback()
        # 실패 사유를 DB에 기록 — 프론트가 GET /status로 확인 가능
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.status = ContractStatus.FAILED
            contract.analysis_error = str(e)
            db.commit()
            # 분석 실패 알림
            create_notification(
                user_id=contract.user_id,
                title=f"'{contract.original_filename}' 분석에 실패했습니다.",
                db=db,
                notification_type=NotificationType.ANALYSIS_FAILED,
                content=str(e),
                contract_id=contract.id,
            )
    finally:
        db.close()  # BackgroundTask는 request 생명주기 밖이므로 반드시 명시적으로 닫아야 함
