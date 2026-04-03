"""
clair-ai HTTP 서비스 클라이언트.

모든 AI 호출은 이 파일을 통해서만 이루어진다.
서비스 레이어는 httpx나 AI 관련 타입을 직접 import하지 않고,
이 클라이언트가 반환하는 ai_models.py 타입만 사용한다.
"""
import httpx
from app.core.config import settings
from app.integrations.ai_models import AIAnalysisResponse, AIQAResponse


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
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/analyze",
                json={
                    "contract_id": contract_id,
                    "file_path": file_path,
                    "file_type": file_type,
                    "document_id": document_id,
                },
            )
            resp.raise_for_status()
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
            resp.raise_for_status()
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
