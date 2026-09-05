from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.price_oracle import lookup


router = APIRouter(
    prefix="/api/device-prices",
    tags=["Device Prices"]
)


@router.get("")
def device_price_check(
    brand: str = "",
    model: str = "",
    storage: str = "",
    db: Session = Depends(get_db),
):
    result = lookup(
        brand=brand,
        model=model,
        storage=storage,
        db=db,
    ) or {}

    exists = result.get("exists")

    if exists is True:
        resolution = "exists"
    elif exists is False:
        resolution = "not_found"
    else:
        resolution = "unknown"

    return {
        "resolution": resolution,

        "matched_model": result.get("matched_model"),

        "valid_variants": result.get("valid_variants") or [],

        "new_price_inr": result.get("new_price_inr"),

        "used_resale_price_inr": (
            result.get("used_resale_price_inr")
        ),

        "source": result.get("source"),

        "confidence": result.get("confidence"),
    }