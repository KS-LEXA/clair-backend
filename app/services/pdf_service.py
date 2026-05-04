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
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)


_RISK_LEVEL_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}


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
