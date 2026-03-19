from fastapi import APIRouter

router = APIRouter()


@router.post("/{document_id}/qa")
def ask_question(document_id: int) -> dict[str, object]:
    return {"document_id": document_id, "answer": None}
