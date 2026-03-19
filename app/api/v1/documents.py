from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_documents() -> dict[str, list]:
    return {"items": []}
