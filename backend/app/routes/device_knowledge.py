from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.device_knowledge import search_devices


router = APIRouter(
    prefix="/api/knowledge",
    tags=["Device Knowledge"]
)


class DeviceSearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=500
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20
    )


@router.post("/search")
def search_device_knowledge(
    request: DeviceSearchRequest
):
    try:
        results = search_devices(
            query=request.query,
            top_k=request.top_k
        )

        return {
            "success": True,
            "query": request.query,
            "count": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge search failed: {str(e)}"
        )