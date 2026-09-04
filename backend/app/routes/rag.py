from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag_answer import generate_rag_answer


router = APIRouter(
    prefix="/api/rag",
    tags=["RAG"]
)


# ============================================================
# REQUEST
# ============================================================

class RAGSearchRequest(BaseModel):

    query: str
    top_k: int = 5


# ============================================================
# AI RAG SEARCH
# ============================================================

@router.post("/search")
def rag_search(request: RAGSearchRequest):

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    if request.top_k < 1 or request.top_k > 20:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 20"
        )

    result = generate_rag_answer(
        query=query,
        top_k=request.top_k
    )

    return {
        "query": query,
        **result
    }