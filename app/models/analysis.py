from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    key_info = Column(JSON, nullable=True)
    clauses = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    detected_objects = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    contract = relationship("Contract", back_populates="analysis_result")


class RiskClause(Base):
    __tablename__ = "risk_clauses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    clause_number = Column(String(50), nullable=True)
    original_text = Column(Text, nullable=False)
    risk_type = Column(String(100), nullable=False)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    contract = relationship("Contract", back_populates="risk_clauses")
