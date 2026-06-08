from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base

# ---------------------------
# 계약 상태(Enum)
# ---------------------------
class ContractStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PENDING = "pending"       # 분석 요청됨, 백그라운드 태스크 대기 중
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# ---------------------------
# 계약서 유형(Enum)
# ---------------------------
class ContractType(str, enum.Enum):
    LABOR = "labor"
    COMPANY_RULE = "company_rule"
    FREELANCE = "freelance"
    NDA = "nda"               # AI 출력값 "nda"
    SERVICE = "service"       # AI 출력값 "service" (용역계약서)
    EMPLOYMENT = "employment" # AI 출력값 "employment" (근로계약서)
    OTHER = "other"
    UNKNOWN = "unknown"


# ---------------------------
# Contract 테이블 정의
# ---------------------------
class Contract(Base):
    __tablename__ = "contracts" # 실제 DB 테이블 이름
    # 기본 키 (Primary Key)
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 사용자 ID (Foreign Key)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 원본 파일 이름, 저장된 파일 이름, 파일 경로, 크기, 유형 등
    original_filename = Column(String(500), nullable=False)
    # 서버에 저장된 파일 이름 (중복 방지용 rename)
    stored_filename = Column(String(500), nullable=False)
    # 파일 경로
    file_path = Column(String(1000), nullable=False)
    # 파일 크기
    file_size = Column(Integer, nullable=False)
    # 파일 유형
    file_type = Column(String(50), nullable=False)
    # MIME 유형
    mime_type = Column(String(100), nullable=True)
    # 계약 상태
    status = Column(Enum(ContractStatus), default=ContractStatus.UPLOADED, nullable=False)
    # 계약서 유형 (분석 결과로 결정, AI 모델 출력값 기반)
    contract_type = Column(Enum(ContractType), default=ContractType.UNKNOWN, nullable=False)
     # OCR 결과 (텍스트 전체)
    extracted_text = Column(Text, nullable=True)          # OCR normalized_text (하위 호환)
    # 페이지별 OCR 결과 (JSON 형태)
    ocr_pages = Column(JSON, nullable=True)               # [{page_index, text}] 페이지별 OCR 결과
    # 분석 오류
    analysis_error = Column(Text, nullable=True)          # 분석 실패 사유
    # 분석(재분석 포함) 요청 시각 — 새 분석 job의 기준 시각.
    # 재분석 신선도 판별의 앵커: 완료 시각이 이 값 이후여야 "이번 요청의 결과"다.
    analysis_requested_at = Column(DateTime, nullable=True)
    # 분석 시작 시간
    analysis_started_at = Column(DateTime, nullable=True)
    # 분석 완료 시간
    analysis_completed_at = Column(DateTime, nullable=True)
    # 생성 시간
    created_at = Column(DateTime, server_default=func.now())
    # 업데이트 시간
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # ---------------------------
    # 관계 설정 (ORM)
    # ---------------------------
    # User 모델과의 관계 (1:N)
    user = relationship("User", back_populates="contracts")
    # 분석 결과 (1:1 관계)
    analysis_result = relationship("AnalysisResult", back_populates="contract", uselist=False, cascade="all, delete-orphan")
    # 리스크 조항 (1:N 관계)
    risk_clauses = relationship("RiskClause", back_populates="contract", cascade="all, delete-orphan")
    # 계약 조항 (1:N 관계)
    clauses = relationship("ContractClause", back_populates="contract", cascade="all, delete-orphan")
    # 법령 준수 검사 결과 (1:N 관계)
    compliance_results = relationship("ComplianceResult", back_populates="contract", cascade="all, delete-orphan")

    @property
    def analysis_job_id(self):
        """현재 분석 job 식별자 — 별도 컬럼 없이 contract_id + 요청 시각으로 파생.

        매 분석 요청마다 analysis_requested_at이 갱신되므로 job_id도 새로 바뀐다.
        프론트가 "지금 폴링 중인 상태가 내가 방금 요청한 job의 것인지" 확인하는 데 사용.
        """
        if self.analysis_requested_at is None:
            return None
        return f"{self.id}-{int(self.analysis_requested_at.timestamp())}"
