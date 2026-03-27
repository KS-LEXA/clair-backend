import os
import uuid
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.contract import Contract, ContractStatus


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
