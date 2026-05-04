from fastapi import APIRouter, Depends, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from urllib.parse import quote
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.contract import (
    ContractUploadResponse, ContractDetailResponse, ContractListResponse, ContractListItem,
    AnalysisResultResponse, RiskClauseResponse, MessageResponse,
    AnalyzeAcceptedResponse, ContractStatusResponse, ClauseResponse, ClauseListResponse,
)
from app.schemas.share import (
    ShareCreateRequest, ShareCreateResponse,
    ShareListItem, ShareListResponse,
)
from app.services.contract_service import (
    upload_contract, get_contract_by_id, get_contracts_by_user, delete_contract,
    trigger_analysis, analyze_contract_background, get_clauses,
)
from app.services.share_service import (
    create_share, list_shares, revoke_share, share_to_response_dict,
)
from app.services.pdf_service import generate_contract_pdf

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
                                           risk_type=rc.risk_type, risk_level=rc.risk_level.value, explanation=rc.explanation,
                                           evidence_clause_ids=rc.evidence_clause_ids, evidence_text=rc.evidence_text)
                        for rc in contract.risk_clauses]
    return ContractDetailResponse(id=contract.id, original_filename=contract.original_filename, file_size=contract.file_size,
                                  file_type=contract.file_type, status=contract.status.value, contract_type=contract.contract_type.value,
                                  extracted_text=contract.extracted_text, created_at=contract.created_at, updated_at=contract.updated_at,
                                  analysis=analysis, risk_clauses=risk_clauses)


@router.delete("/{contract_id}", response_model=MessageResponse, summary="계약서 삭제")
def api_delete_contract(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_contract(contract_id, user.id, db)
    return MessageResponse(message="계약서가 삭제되었습니다.")


@router.post("/{contract_id}/analyze", response_model=AnalyzeAcceptedResponse, status_code=202, summary="계약서 분석 요청")
async def api_request_analysis(
    contract_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = trigger_analysis(contract_id, user.id, db)
    background_tasks.add_task(analyze_contract_background, contract.id)
    return AnalyzeAcceptedResponse(
        message=f"'{contract.original_filename}' 분석이 요청되었습니다.",
        status="pending",
        poll_url=f"/api/v1/contracts/{contract_id}/status",
    )


@router.get("/{contract_id}/status", response_model=ContractStatusResponse, summary="분석 상태 조회")
def api_get_analysis_status(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = get_contract_by_id(contract_id, user.id, db)
    return ContractStatusResponse(
        contract_id=contract.id,
        status=contract.status.value,
        contract_type=contract.contract_type.value,
        analysis_started_at=contract.analysis_started_at,
        analysis_completed_at=contract.analysis_completed_at,
        error=contract.analysis_error,
    )


@router.get("/{contract_id}/clauses", response_model=ClauseListResponse, summary="조항 목록 조회")
def api_get_clauses(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clauses = get_clauses(contract_id, user.id, db)
    return ClauseListResponse(
        contract_id=contract_id,
        total=len(clauses),
        clauses=[ClauseResponse(id=c.id, clause_id=c.clause_id, title=c.title, text=c.text,
                                page_refs=c.page_refs, order=c.order) for c in clauses],
    )


# ── 공유 (소유자 전용) ─────────────────────────────────────────────────────

@router.post("/{contract_id}/share", response_model=ShareCreateResponse, status_code=201, summary="공유 링크 생성")
def api_create_share(
    contract_id: int,
    body: ShareCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    share = create_share(
        contract_id=contract_id, user_id=user.id,
        password=body.password, expire_days=body.expire_days, db=db,
    )
    return ShareCreateResponse(**share_to_response_dict(share))


@router.get("/{contract_id}/shares", response_model=ShareListResponse, summary="공유 링크 목록")
def api_list_shares(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shares = list_shares(contract_id=contract_id, user_id=user.id, db=db)
    return ShareListResponse(
        contract_id=contract_id,
        total=len(shares),
        shares=[ShareListItem(**share_to_response_dict(s)) for s in shares],
    )


@router.delete("/{contract_id}/shares/{share_id}", response_model=MessageResponse, summary="공유 링크 해제")
def api_revoke_share(
    contract_id: int, share_id: int,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    revoke_share(share_id=share_id, contract_id=contract_id, user_id=user.id, db=db)
    return MessageResponse(message="공유 링크가 해제되었습니다.")


# ── PDF 다운로드 (소유자 전용) ─────────────────────────────────────────────

@router.get("/{contract_id}/download/pdf", summary="분석 결과 PDF 다운로드")
def api_download_pdf(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_bytes, filename = generate_contract_pdf(contract_id=contract_id, user_id=user.id, db=db)
    # 한글 파일명은 RFC 5987 형식(`filename*`)으로 인코딩 — Content-Disposition에서 안전
    content_disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition},
    )
