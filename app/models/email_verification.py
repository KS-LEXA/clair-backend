from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.session import Base


# ──────────────────────────────────────────────────────────────────────────────
# EmailVerification: 회원가입 전 단계의 이메일 코드 인증
#
# 이메일당 활성 레코드 1개 (UNIQUE) — 코드 재요청 시 같은 행을 갱신.
# code_hash만 저장: DB 유출 시에도 raw 6자리 코드는 알 수 없음.
# attempt_count로 confirm 무차별 대입 방어 — 5회 실패 시 코드 무효.
# verified_at 채워진 레코드는 회원가입 시 1회용으로 소비된 뒤 삭제됨.
# ──────────────────────────────────────────────────────────────────────────────
class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
