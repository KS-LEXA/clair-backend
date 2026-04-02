from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(20), nullable=False)    # 'google' | 'naver' | 'kakao'
    provider_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="social_accounts")

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_social_provider"),
    )
