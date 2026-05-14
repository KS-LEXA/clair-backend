from __future__ import annotations

"""
AI 응답 → ORM 객체 변환 순수 함수 모음.

DB I/O 없음. 변환 로직만 담당.
서비스 레이어가 이 함수들을 호출해 ORM 객체를 만든 뒤 db.add()한다.
"""
from app.integrations.ai_models import AIAnalysisResponse, AIRiskResult, AIClause, AIComplianceResult
from app.models.contract import ContractType
from app.models.analysis import AnalysisResult, RiskClause, ContractClause, RiskLevel, ComplianceResult

# clair-ai가 반환하는 contract_type 문자열 → ContractType Enum 변환 테이블
# AI 출력값이 추가될 경우 여기에만 추가하면 됨
_AI_TYPE_MAP: dict[str, ContractType] = {
    "nda": ContractType.NDA,
    "service": ContractType.SERVICE,
    "employment": ContractType.EMPLOYMENT,
    "unknown": ContractType.UNKNOWN,
}

# AI severity 문자열 → RiskLevel Enum 변환 테이블
_AI_SEVERITY_MAP: dict[str, RiskLevel] = {
    "low": RiskLevel.LOW,
    "medium": RiskLevel.MEDIUM,
    "high": RiskLevel.HIGH,
}


def ai_contract_type_to_enum(ai_value: str) -> ContractType:
    """AI가 반환한 계약 유형 문자열을 ContractType Enum으로 변환. 미등록값은 UNKNOWN."""
    return _AI_TYPE_MAP.get(ai_value.lower(), ContractType.UNKNOWN)


def ai_clauses_to_contract_clauses(clauses: list[AIClause], contract_id: int) -> list[ContractClause]:
    """
    AIClause 리스트 → ContractClause ORM 객체 리스트.
    clause_id가 RiskClause.evidence_clause_ids의 참조 대상이 되므로
    반드시 RiskClause보다 먼저 DB에 저장해야 한다.
    """
    return [
        ContractClause(
            contract_id=contract_id,
            clause_id=c.clause_id,
            title=c.title,
            text=c.text,
            page_refs=c.page_refs,
            order=c.order,
        )
        for c in clauses
    ]


def ai_risks_to_risk_clauses(risks: list[AIRiskResult], contract_id: int) -> list[RiskClause]:
    """
    AIRiskResult 리스트 → RiskClause ORM 객체 리스트.
    clause_number에는 하위 호환을 위해 evidence_clause_ids[0]을 채운다.
    """
    rows = []
    for r in risks:
        rows.append(
            RiskClause(
                contract_id=contract_id,
                title=getattr(r, "title", None),
                clause_number=r.evidence_clause_ids[0] if r.evidence_clause_ids else None,
                original_text=r.evidence_text or getattr(r, "problematic_text", ""),
                risk_type=r.risk_type,
                risk_level=_AI_SEVERITY_MAP.get(r.severity, RiskLevel.MEDIUM),
                severity_score=getattr(r, "severity_score", 5),
                confidence=getattr(r, "confidence", 0.7),
                explanation=r.reason,
                evidence_clause_ids=r.evidence_clause_ids,
                evidence_text=r.evidence_text,
                problematic_text=getattr(r, "problematic_text", None),
            )
        )
    return rows


def ai_compliance_to_compliance_results(
    compliance: list[AIComplianceResult],
    contract_id: int,
) -> list[ComplianceResult]:
    """AIComplianceResult 리스트 → ComplianceResult ORM 객체 리스트."""
    return [
        ComplianceResult(
            contract_id=contract_id,
            clause_id=c.clause_id,
            clause_title=c.clause_title,
            clause_text=c.clause_text,
            status=c.status,
            reason=c.reason,
            law_references=[ref.model_dump() for ref in c.law_references],
        )
        for c in compliance
    ]


def ai_analysis_to_analysis_result(
    ai_resp: AIAnalysisResponse,
    contract_id: int,
    duration_seconds: int | None = None,
) -> AnalysisResult:
    """
    AIAnalysisResponse 전체 → AnalysisResult ORM 객체.
    clauses는 contract_clauses 테이블에 별도 저장되지만,
    하위 호환을 위해 JSON 스냅샷도 함께 기록한다.
    """
    return AnalysisResult(
        contract_id=contract_id,
        key_info=ai_resp.extraction.model_dump(),       # {field: {value, reason}} 구조 그대로
        clauses=[c.model_dump() for c in ai_resp.clauses],
        summary=ai_resp.summary,
        detected_objects=[o.model_dump() for o in ai_resp.detected_objects],
        raw_ocr_text=ai_resp.ocr_raw_text,
        analysis_duration_seconds=duration_seconds,
    )
