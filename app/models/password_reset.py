from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base


# ──────────────────────────────────────────────────────────────────────────────
# PasswordResetToken: 비밀번호 재설정용 1회성 토큰
#
# token_hash만 저장 — DB가 유출되더라도 raw 토큰은 알 수 없게 SHA-256 해시 저장.
# 사용자에게 메일로 발송하는 raw 토큰은 응답하는 순간 한 번만 존재한다.
# ──────────────────────────────────────────────────────────────────────────────
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", backref="password_reset_tokens")
