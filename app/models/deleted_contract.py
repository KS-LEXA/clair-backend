from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.db.session import Base


# ──────────────────────────────────────────────────────────────────────────────
# DeletedContract: 계약서 삭제 이력
# DELETE /contracts/{id} 시 원본 계약서는 hard delete 되므로, 삭제 직전 메타데이터를
# 이 테이블에 1행 기록해 둔다. GET /contracts/deleted 가 이 테이블을 조회한다.
# (프론트가 localStorage로 임시 보관하던 삭제 이력을 서버로 이관 — 기기/브라우저 무관)
# ──────────────────────────────────────────────────────────────────────────────
class DeletedContract(Base):
    __tablename__ = "deleted_contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 소유자 — 사용자 탈퇴 시 함께 제거 (FK ON DELETE CASCADE)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 삭제된 원본 계약서의 id (프론트 이력 매칭용). 원본 행은 이미 삭제됐으므로 FK 아님.
    original_contract_id = Column(Integer, nullable=False, index=True)
    # 삭제 시점의 메타데이터 스냅샷 (원본 행이 사라져도 이력은 보존)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    contract_type = Column(String(50), nullable=True)        # 삭제 당시 ContractType 값
    status_at_deletion = Column(String(50), nullable=True)   # 삭제 당시 ContractStatus 값
    contract_created_at = Column(DateTime, nullable=True)     # 원본 업로드 일시
    deleted_at = Column(DateTime, server_default=func.now(), index=True)
