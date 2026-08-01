from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, Float, func, UniqueConstraint
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ──────────────────────────────────────────────────────────────────────────────
# ContractClause: AI가 조항 단위로 분리한 결과를 저장하는 테이블 (신규)
#
# 왜 별도 테이블인가?
#   챗봇 QA 응답에는 "몇 번 조항이 근거입니다" 같은 evidence_clause_ids가 딸려옴.
#   조항을 AnalysisResult.clauses JSON에 묻어두면 이 ID로 실제 텍스트를
#   JOIN 조회할 방법이 없다. 별도 행으로 분리해야 프론트에서 해당 조항을
#   하이라이트할 수 있고, RAG 근거 표시도 가능해짐.
# ──────────────────────────────────────────────────────────────────────────────
class ContractClause(Base):
    __tablename__ = "contract_clauses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 어떤 계약서에 속한 조항인지
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    # AI가 부여한 조항 식별자 ex) "clause-001" — RiskClause.evidence_clause_ids가 이 값을 참조함
    clause_id = Column(String(50), nullable=False)
    # 조항 제목 ex) "제1조 (목적)" — 없을 수도 있음
    title = Column(String(500), nullable=True)
    # 조항 본문 전체
    text = Column(Text, nullable=False)
    # 이 조항이 몇 페이지에 등장하는지 ex) [0, 1]
    page_refs = Column(JSON, nullable=True)
    # 문서 내 조항 순서 (정렬 기준)
    order = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    contract = relationship("Contract", back_populates="clauses")

    # 같은 계약서 안에서 clause_id는 유일해야 함
    __table_args__ = (
        UniqueConstraint("contract_id", "clause_id", name="uq_clause_per_contract"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# AnalysisResult: 계약서 1건당 분석 결과 1건 (1:1 관계)
# ──────────────────────────────────────────────────────────────────────────────
class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    # AI ExtractionResult 전체를 JSON으로 저장 — {value, reason} 구조 유지
    # ex) {"contract_type": {"value": "nda", "reason": null}, "counterparty_a": {...}, ...}
    key_info = Column(JSON, nullable=True)
    # ContractClause 테이블 도입 전 하위 호환용 스냅샷 — 조항 조회는 contract_clauses 테이블 사용 권장
    clauses = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    # YOLOv8 비전 탐지 결과 ex) [{page_index, label, confidence, bbox: {x1,y1,x2,y2}}]
    detected_objects = Column(JSON, nullable=True)
    # OCR 원문 (디버깅·재분석용) — normalized_text는 Contract.extracted_text에 저장
    raw_ocr_text = Column(Text, nullable=True)
    # 분석에 걸린 시간 (초) — 성능 모니터링용
    analysis_duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    contract = relationship("Contract", back_populates="analysis_result")


# ──────────────────────────────────────────────────────────────────────────────
# RiskClause: AI가 탐지한 위험 조항 1건 = 행 1개
# ──────────────────────────────────────────────────────────────────────────────
class RiskClause(Base):
    __tablename__ = "risk_clauses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    # 하위 호환용 — evidence_clause_ids[0] 값을 채워둠
    clause_number = Column(String(50), nullable=True)
    # AI가 위험하다고 판단한 조항 원문
    original_text = Column(Text, nullable=False)
    # 사용자 친화적 위험 조항명 (한국어, Gemini 산출)
    title = Column(String(200), nullable=True)
    # 위험 유형 — payment | liability | termination | confidentiality | renewal | penalty | ip | etc
    risk_type = Column(String(100), nullable=False)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)
    # 심각도 수치 1~10 (Gemini 산출)
    severity_score = Column(Integer, default=5, nullable=True)
    # 분석 신뢰도 0.0~1.0 (Gemini 산출)
    confidence = Column(Float, nullable=True)
    # AI가 생성한 위험 설명 (한국어)
    explanation = Column(Text, nullable=True)
    # 위험 판단 근거 원문
    problematic_text = Column(Text, nullable=True)
    # 근거가 된 조항 ID 목록 ex) ["clause-003", "clause-007"]
    # ContractClause.clause_id와 매핑 — 프론트에서 해당 조항 하이라이트에 사용
    evidence_clause_ids = Column(JSON, nullable=True)
    # AI가 추출한 근거 원문 발췌
    evidence_text = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    contract = relationship("Contract", back_populates="risk_clauses")


# ──────────────────────────────────────────────────────────────────────────────
# ComplianceResult: 조항별 법령 준수 검사 결과
# clair-ai /analyze 응답의 compliance[] 배열을 행 단위로 저장
# ──────────────────────────────────────────────────────────────────────────────
class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    # ContractClause.clause_id 참조 — 프론트에서 조항 하이라이트에 사용
    clause_id = Column(String(50), nullable=False)
    clause_title = Column(String(500), nullable=True)
    clause_text = Column(Text, nullable=False)
    # 준수 상태: 위반 | 주의 | 적합 | 검토불가
    status = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    # 근거 법령 목록 JSON ex) [{"law_name": "근로기준법", "article_no": "제56조", ...}]
    law_references = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    contract = relationship("Contract", back_populates="compliance_results")
