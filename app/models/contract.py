from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base


class ContractStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ContractType(str, enum.Enum):
    LABOR = "labor"
    COMPANY_RULE = "company_rule"
    FREELANCE = "freelance"
    OTHER = "other"
    UNKNOWN = "unknown"


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    mime_type = Column(String(100), nullable=True)
    status = Column(Enum(ContractStatus), default=ContractStatus.UPLOADED, nullable=False)
    contract_type = Column(Enum(ContractType), default=ContractType.UNKNOWN, nullable=False)
    extracted_text = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="contracts")
    analysis_result = relationship("AnalysisResult", back_populates="contract", uselist=False, cascade="all, delete-orphan")
    risk_clauses = relationship("RiskClause", back_populates="contract", cascade="all, delete-orphan")
