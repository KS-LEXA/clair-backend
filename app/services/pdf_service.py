from __future__ import annotations

"""
PDF 보고서 생성 서비스.

WeasyPrint(HTML→PDF)를 사용해 Jinja2 템플릿으로 한국어 분석 보고서를 만든다.

주의 (macOS):
  weasyprint은 시스템 라이브러리(pango, glib)를 동적 로드하는데,
  macOS SIP가 자식 프로세스에서 DYLD_* 환경변수를 제거한다.
  cffi/dlopen은 import 시점에 env를 읽으므로, weasyprint import 전에
  homebrew 라이브러리 경로를 명시 설정해야 한다.
"""
import os
import platform
from datetime import datetime
from pathlib import Path

# WeasyPrint import 전에 macOS 라이브러리 경로 설정 — 순서 중요
if platform.system() == "Darwin":
    for _hb in ("/opt/homebrew/lib", "/usr/local/lib"):  # Apple Silicon → Intel 순
        if os.path.exists(_hb):
            existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            if _hb not in existing:
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{_hb}:{existing}".rstrip(":")
            break

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.models.contract import Contract, ContractStatus
from app.models.analysis import ContractClause


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "pdf"


_RISK_LEVEL_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}

# 핵심 정보 테이블의 key를 PDF 표시용 한국어 라벨로 변환 (표시용 — 원본 데이터/API 응답은 그대로 유지)
KEY_INFO_LABELS = {
    "start_date": "계약 시작일",
    "end_date": "계약 종료일",
    "signing_date": "계약 체결일",
    "contract_type": "계약서 유형",
    "amount_text": "급여",
    "amount_value": "급여 금액",
    "hourly_wage": "시급",
    "monthly_wage": "월 급여",
    "monthly_wage_is_estimated": "월 급여 추정 여부",
    "weekly_work_days": "주당 근무일",
    "weekly_work_hours": "주당 근무시간",
    "counterparty_a": "당사자 A",
    "counterparty_b": "당사자 B",
}

# 위험 유형(risk_type)을 PDF 표시용 한국어로 변환
RISK_TYPE_LABELS = {
    "payment": "지급/급여",
    "liability": "책임",
    "termination": "해지",
    "confidentiality": "비밀유지",
    "penalty": "위약금",
    "renewal": "갱신",
    "ip": "지식재산권",
    "etc": "기타",
    "other": "기타",
}

# 계약서 유형(ContractType enum)을 PDF 표시용 한국어로 변환
CONTRACT_TYPE_LABELS = {
    "labor": "근로계약서",
    "employment": "근로계약서",
    "service": "용역계약서",
    "freelance": "프리랜서 계약서",
    "nda": "비밀유지계약서",
    "company_rule": "취업규칙",
    "other": "기타",
    "unknown": "미분류",
}


def format_key_info_label(key: str) -> str:
    """핵심 정보 key를 한국어 라벨로 변환. 매핑이 없으면 원래 key를 그대로 반환."""
    return KEY_INFO_LABELS.get(key, key)


def format_risk_type(risk_type) -> str:
    """위험 유형을 한국어로 변환. 매핑이 없으면 원래 값을 그대로 반환."""
    if risk_type is None:
        return "-"
    return RISK_TYPE_LABELS.get(str(risk_type).lower(), str(risk_type))


def format_contract_type(contract_type) -> str:
    """계약서 유형 enum 값을 한국어로 변환. 매핑이 없으면 원래 값을 그대로 반환."""
    if contract_type is None:
        return "-"
    return CONTRACT_TYPE_LABELS.get(str(contract_type).lower(), str(contract_type))


def format_pdf_value(value) -> str:
    """PDF 표시용 값 포맷팅: None은 '-', boolean은 예/아니오."""
    if value is None:
        return "-"
    if value is True:
        return "예"
    if value is False:
        return "아니오"
    return str(value)


_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)
_jinja_env.filters["key_info_label"] = format_key_info_label
_jinja_env.filters["risk_type_label"] = format_risk_type
_jinja_env.filters["contract_type_label"] = format_contract_type
_jinja_env.filters["pdf_value"] = format_pdf_value


def generate_contract_pdf(contract_id: int, user_id: int, db: Session) -> tuple[bytes, str]:
    """
    소유자용 PDF 다운로드. 분석 완료된 계약서만 생성 가능.
    반환: (PDF 바이트, 다운로드 파일명)
    """
    contract = db.query(Contract).filter(
        Contract.id == contract_id, Contract.user_id == user_id
    ).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계약서를 찾을 수 없습니다.")
    if contract.status != ContractStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="분석이 완료된 계약서만 PDF로 다운로드할 수 있습니다.")

    clauses = (
        db.query(ContractClause)
        .filter(ContractClause.contract_id == contract_id)
        .order_by(ContractClause.order)
        .all()
    )

    risk_clauses = [
        {
            "clause_number": rc.clause_number,
            "risk_type": rc.risk_type,
            "risk_level": rc.risk_level.value,
            "risk_level_label": _RISK_LEVEL_LABELS.get(rc.risk_level.value, rc.risk_level.value),
            "explanation": rc.explanation,
            "evidence_clause_ids": rc.evidence_clause_ids or [],
            "evidence_text": rc.evidence_text,
        }
        for rc in (contract.risk_clauses or [])
    ]

    analysis = contract.analysis_result
    template = _jinja_env.get_template("contract_report.html")
    html = template.render(
        original_filename=contract.original_filename,
        contract_type=contract.contract_type.value,
        analyzed_at=contract.analysis_completed_at or contract.updated_at,
        generated_at=datetime.now(),
        key_info=(analysis.key_info if analysis else None),
        summary=(analysis.summary if analysis else None),
        risk_clauses=risk_clauses,
        clauses=[{"clause_id": c.clause_id, "title": c.title, "text": c.text, "order": c.order} for c in clauses],
    )

    pdf_bytes: bytes = HTML(string=html).write_pdf()
    safe_name = (contract.original_filename or f"contract-{contract_id}").rsplit(".", 1)[0]
    download_filename = f"{safe_name}_분석보고서.pdf"
    return pdf_bytes, download_filename
