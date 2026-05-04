from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.share import (
    ShareVerifyRequest, ShareVerifyResponse,
    SharedContractResponse, SharedAnalysisResult, SharedRiskClause,
)
from app.services.share_service import verify_share_password, get_shared_contract


router = APIRouter()


@router.post("/{token}/verify", response_model=ShareVerifyResponse, summary="공유 비밀번호 검증")
def api_verify_share(token: str, body: ShareVerifyRequest, db: Session = Depends(get_db)):
    access_token, expires_at = verify_share_password(token=token, password=body.password, db=db)
    return ShareVerifyResponse(access_token=access_token, expires_at=expires_at)


def _bearer_token(authorization: str = Header(default="")) -> str:
    """Authorization 헤더에서 Bearer 토큰만 뽑아내는 헬퍼."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="공유 access token이 필요합니다.")
    return authorization.split(" ", 1)[1].strip()


@router.get("/{token}", response_model=SharedContractResponse, summary="공유받은 계약서 분석 결과 조회")
def api_get_shared_contract(
    token: str,  # URL의 토큰은 검증 토큰과 일치해야 함
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
):
    """
    헤더 'Authorization: Bearer <access_token>' 필요.
    /verify로 받은 access_token을 그대로 사용.
    공유받은 사람에게 노출되는 데이터: 분석 결과 + 위험 조항 + 근거.
    """
    access_token = _bearer_token(authorization)
    share, contract = get_shared_contract(access_token, db)

    # URL의 token과 access_token에 담긴 share_token이 일치하는지 추가 검증
    if share.token != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="토큰 불일치")

    analysis = None
    if contract.analysis_result:
        analysis = SharedAnalysisResult(
            key_info=contract.analysis_result.key_info,
            summary=contract.analysis_result.summary,
        )

    risk_clauses = [
        SharedRiskClause(
            clause_number=rc.clause_number,
            risk_type=rc.risk_type,
            risk_level=rc.risk_level.value,
            explanation=rc.explanation,
            evidence_clause_ids=rc.evidence_clause_ids,
            evidence_text=rc.evidence_text,
        )
        for rc in (contract.risk_clauses or [])
    ]

    return SharedContractResponse(
        contract_id=contract.id,
        original_filename=contract.original_filename,
        contract_type=contract.contract_type.value,
        analysis=analysis,
        risk_clauses=risk_clauses,
    )
