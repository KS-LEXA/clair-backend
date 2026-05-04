from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base


# ──────────────────────────────────────────────────────────────────────────────
# ContractShare: 계약서 분석 결과 외부 공유용 토큰 + 비번
#
# 발급 시 raw token은 응답으로 한 번만 반환되고, DB엔 token만 저장한다.
# password_hash는 bcrypt 해시 저장 — 검증 시 평문 비교 X.
# revoked_at이 채워져 있으면 만료 전이라도 접근 차단.
# ──────────────────────────────────────────────────────────────────────────────
class ContractShare(Base):
    __tablename__ = "contract_shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    contract = relationship("Contract", backref="shares")
