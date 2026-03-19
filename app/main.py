from fastapi import FastAPI

from app.api.v1.documents import router as documents_router
from app.api.v1.qa import router as qa_router
from app.api.v1.detections import router as detections_router

app = FastAPI(title="Clair Backend")
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(qa_router, prefix="/api/v1/documents", tags=["qa"])
app.include_router(detections_router, prefix="/api/v1/documents", tags=["detections"])


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
