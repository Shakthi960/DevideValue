import os

from fastapi import APIRouter
from sqlalchemy import text

from app import APP_VERSION
from app.core.database import engine
from app.services.valuation import PHONE_DATA, PRICE_MODEL


router = APIRouter(
    prefix="/api/health",
    tags=["Health"]
)


def check_database():
    """Return a one-word/one-line database connectivity status."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "connected"

    except Exception as exc:
        return f"error: {exc}"


@router.get("")
def health():
    """Sanity check used by the frontend Diagnostics page."""

    return {
        "status": "healthy",
        "version": APP_VERSION,
        "database": check_database(),
        "model_loaded": PRICE_MODEL is not None,
        "dataset_rows": len(PHONE_DATA),
        "gemini_configured": bool(
            os.getenv("GEMINI_API_KEY")
        ),
    }