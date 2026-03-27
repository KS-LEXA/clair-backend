from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.contract import ContractUploadResponse, ContractDetailResponse, ContractListResponse, ContractListItem, AnalysisResultResponse, RiskClauseResponse, MessageResponse
from app.services.contract_service import upload_contract, get_contract_by_id, get_contracts_by_user, delete_contract

router = APIRouter()


@router.post("/upload", response_model=ContractUploadResponse, status_code=201, summary="계약서 업로드")
async def api_upload_contract(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = await upload_contract(file=file, user_id=user.id, db=db)
    return ContractUploadResponse(id=contract.id, original_filename=contract.original_filename, file_size=contract.file_size,
                                  file_type=contract.file_type, status=contract.status.value, created_at=contract.created_at)


@router.get("/", response_model=ContractListResponse, summary="계약서 목록 조회")
def api_list_contracts(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total, contracts = get_contracts_by_user(user_id=user.id, db=db, skip=skip, limit=limit)
    return ContractListResponse(total=total, contracts=[
        ContractListItem(id=c.id, original_filename=c.original_filename, file_type=c.file_type,
                         status=c.status.value, contract_type=c.contract_type.value, created_at=c.created_at)
        for c in contracts])


@router.get("/{contract_id}", response_model=ContractDetailResponse, summary="계약서 상세 조회")
def api_get_contract(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = get_contract_by_id(contract_id, user.id, db)
    analysis = None
    if contract.analysis_result:
        analysis = AnalysisResultResponse(key_info=contract.analysis_result.key_info, clauses=contract.analysis_result.clauses,
                                          summary=contract.analysis_result.summary, detected_objects=contract.analysis_result.detected_objects,
                                          created_at=contract.analysis_result.created_at)
    risk_clauses = None
    if contract.risk_clauses:
        risk_clauses = [RiskClauseResponse(id=rc.id, clause_number=rc.clause_number, original_text=rc.original_text,
                                           risk_type=rc.risk_type, risk_level=rc.risk_level.value, explanation=rc.explanation)
                        for rc in contract.risk_clauses]
    return ContractDetailResponse(id=contract.id, original_filename=contract.original_filename, file_size=contract.file_size,
                                  file_type=contract.file_type, status=contract.status.value, contract_type=contract.contract_type.value,
                                  extracted_text=contract.extracted_text, created_at=contract.created_at, updated_at=contract.updated_at,
                                  analysis=analysis, risk_clauses=risk_clauses)


@router.delete("/{contract_id}", response_model=MessageResponse, summary="계약서 삭제")
def api_delete_contract(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_contract(contract_id, user.id, db)
    return MessageResponse(message="계약서가 삭제되었습니다.")


@router.post("/{contract_id}/analyze", response_model=MessageResponse, summary="계약서 분석 요청")
def api_request_analysis(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = get_contract_by_id(contract_id, user.id, db)
    # TODO: 조서현 파트 - AI 분석 파이프라인 호출
    return MessageResponse(message="분석 요청이 접수되었습니다.", detail=f"'{contract.original_filename}' 분석 시작 (AI 모듈 연동 예정)")
