from fastapi import APIRouter

router = APIRouter()


@router.get("/{document_id}/detections")
def get_detections(document_id: int) -> dict[str, object]:
    return {"document_id": document_id, "items": []}
