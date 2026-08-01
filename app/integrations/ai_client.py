from __future__ import annotations

"""
clair-ai HTTP 서비스 클라이언트.

모든 AI 호출은 이 파일을 통해서만 이루어진다.
서비스 레이어는 httpx나 AI 관련 타입을 직접 import하지 않고,
이 클라이언트가 반환하는 ai_models.py 타입만 사용한다.
"""
import os
import httpx
from app.core.config import settings
from app.integrations.ai_models import AIAnalysisResponse, AIQAResponse


def _raise_for_status(resp: httpx.Response) -> None:
    """오류 응답을 clair-ai가 보낸 detail 문구와 함께 올린다.

    httpx의 raise_for_status()는 상태 코드만 담아 본문의 detail을 버린다.
    예산 소진(429) 같은 케이스에서 사용자가 원인을 알 수 있어야 하므로,
    detail이 있으면 그것을 예외 메시지로 쓴다. 이 메시지는 분석 실패 시
    contract.analysis_error와 알림에 그대로 노출된다.
    """
    if not resp.is_error:
        return
    detail = None
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            detail = payload.get("detail")
    except Exception:
        detail = None
    if detail:
        raise httpx.HTTPStatusError(str(detail), request=resp.request, response=resp)
    resp.raise_for_status()


class AIServiceClient:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout  # 분석은 OCR+LLM 합산 최대 2분 허용

    async def analyze_contract(
        self,
        contract_id: int,
        file_path: str,     # 서버 로컬 파일 경로 — clair-ai가 직접 읽음
        file_type: str,     # ex) ".pdf", ".png"
        document_id: str,   # str(contract.id) — AI 결과에 그대로 돌아옴
    ) -> AIAnalysisResponse:
        """계약서 전체 분석 요청. 응답까지 수십 초 걸릴 수 있음."""
        abs_file_path = os.path.abspath(file_path)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/analyze",
                json={
                    "contract_id": contract_id,
                    "file_path": abs_file_path,
                    "file_type": file_type,
                    "document_id": document_id,
                },
            )
            _raise_for_status(resp)
            return AIAnalysisResponse.model_validate(resp.json())

    async def answer_question(
        self,
        contract_id: int,
        question: str,
        clauses: list[dict],    # ContractClause 행을 dict로 직렬화한 것
                                # [{clause_id, title, text}] — clair-ai가 RAG 컨텍스트로 사용
    ) -> AIQAResponse:
        """
        QA 요청. clair-ai에 조항 목록을 함께 전달해서
        OCR 재실행 없이 빠르게 답변받는다 (보통 2~5초).
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/qa",
                json={
                    "contract_id": contract_id,
                    "question": question,
                    "clauses": clauses,
                },
            )
            _raise_for_status(resp)
            return AIQAResponse.model_validate(resp.json())

    async def health_check(self) -> bool:
        """clair-ai 서버가 살아있는지 확인. startup 검증이나 모니터링에 사용."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


# 모듈 레벨 싱글턴 — 서비스 레이어에서 이걸 import해서 사용
# ex) from app.integrations.ai_client import ai_client
ai_client = AIServiceClient(
    base_url=settings.ai_service_url,
    timeout=settings.ai_service_timeout,
)
