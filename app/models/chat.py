from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base


class MessageSender(str, enum.Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class MessageType(str, enum.Enum):
    TEXT = "text"
    FILE_UPLOAD = "file_upload"
    ANALYSIS_RESULT = "analysis_result"
    QUESTION = "question"
    ANSWER = "answer"


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False, default="새 대화")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="chat_sessions")
    contract = relationship("Contract", backref="chat_session")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(Enum(MessageSender), nullable=False)
    message_type = Column(Enum(MessageType), default=MessageType.TEXT, nullable=False)
    content = Column(Text, nullable=False)
    extra_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")
