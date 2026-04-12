from __future__ import annotations

import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class NotificationType(str, enum.Enum):
    ANALYSIS_COMPLETE = "analysis_complete"
    ANALYSIS_FAILED = "analysis_failed"
    SYSTEM = "system"
    MARKETING = "marketing"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False, default=NotificationType.SYSTEM)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, server_default="0")
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", backref="notifications")
