from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password, verify_password,
    create_share_access_token, decode_share_access_token,
)
from app.models.contract import Contract, ContractStatus
from app.models.contract_share import ContractShare


def _build_share_url(token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}{settings.share_path}/{token}"


def _to_aware_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ensure_owner_contract(contract_id: int, user_id: int, db: Session) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == user_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계약서를 찾을 수 없습니다.")
    return contract


# ── 소유자 액션 ────────────────────────────────────────────────────────────

def create_share(
    contract_id: int, user_id: int, password: str, expire_days: Optional[int], db: Session
) -> ContractShare:
    """공유 링크 생성. 분석 완료된 계약서에만 가능."""
    contract = _ensure_owner_contract(contract_id, user_id, db)
    if contract.status != ContractStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="분석이 완료된 계약서만 공유할 수 있습니다.")

    days = expire_days or settings.share_token_default_expire_days
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    token = secrets.token_urlsafe(32)

    share = ContractShare(
        contract_id=contract_id,
        token=token,
        password_hash=hash_password(password),
        expires_at=expires_at,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def list_shares(contract_id: int, user_id: int, db: Session) -> list[ContractShare]:
    _ensure_owner_contract(contract_id, user_id, db)
    return (
        db.query(ContractShare)
        .filter(ContractShare.contract_id == contract_id)
        .order_by(ContractShare.created_at.desc())
        .all()
    )


def revoke_share(share_id: int, contract_id: int, user_id: int, db: Session) -> None:
    _ensure_owner_contract(contract_id, user_id, db)
    share = db.query(ContractShare).filter(
        ContractShare.id == share_id, ContractShare.contract_id == contract_id
    ).first()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="공유 링크를 찾을 수 없습니다.")
    if share.revoked_at is None:
        share.revoked_at = datetime.now(timezone.utc)
        db.commit()


def is_share_active(share: ContractShare) -> bool:
    if share.revoked_at is not None:
        return False
    return datetime.now(timezone.utc) <= _to_aware_utc(share.expires_at)


# ── 공유받은 사람 액션 ─────────────────────────────────────────────────────

def verify_share_password(token: str, password: str, db: Session) -> Tuple[str, datetime]:
    """비밀번호 검증 후 임시 access token(JWT) 발급."""
    share = db.query(ContractShare).filter(ContractShare.token == token).first()
    if not share or not is_share_active(share):
        # 토큰 존재 여부와 관계없이 동일한 메시지 — 토큰 추측 공격 방지
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="유효하지 않거나 만료된 공유 링크입니다.")
    if not verify_password(password, share.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비밀번호가 올바르지 않습니다.")

    return create_share_access_token(token)


def get_shared_contract(share_access_token: str, db: Session) -> Tuple[ContractShare, Contract]:
    """share access token 검증 → 공유 행 + Contract 반환. 비로그인 진입 후 결과 조회용."""
    token = decode_share_access_token(share_access_token)
    share = db.query(ContractShare).filter(ContractShare.token == token).first()
    if not share or not is_share_active(share):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="유효하지 않거나 만료된 공유 링크입니다.")
    contract = db.query(Contract).filter(Contract.id == share.contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계약서를 찾을 수 없습니다.")
    return share, contract


def share_to_response_dict(share: ContractShare) -> dict:
    """ShareCreateResponse / ShareListItem 공통 변환 — share_url, is_active 부착."""
    return {
        "id": share.id,
        "token": share.token,
        "share_url": _build_share_url(share.token),
        "expires_at": share.expires_at,
        "revoked_at": share.revoked_at,
        "created_at": share.created_at,
        "is_active": is_share_active(share),
    }
