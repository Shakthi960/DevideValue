from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.ml_valuation import calculate_ml_valuation


router = APIRouter(
    prefix="/ml",
    tags=["Machine Learning"]
)


class DevicePredictionRequest(BaseModel):
    smartphone_brand: str
    model: str

    rating_score: Optional[float] = None

    processor_name: Optional[str] = None
    processor_brand: Optional[str] = None

    core_count: Optional[float] = None
    clock_speed_ghz: Optional[float] = None

    ram_gb: Optional[float] = None
    storage_gb: Optional[float] = None

    has_5g: Optional[bool] = None
    has_nfc: Optional[bool] = None
    has_ir_blaster: Optional[bool] = None

    display_inches: Optional[float] = None
    res_width_px: Optional[float] = None
    res_height_px: Optional[float] = None
    refresh_rate_hz: Optional[float] = None

    battery_mah: Optional[float] = None

    fast_charging: Optional[bool] = None
    charging_watt: Optional[float] = None

    rear_camera_count: Optional[float] = None
    front_camera_count: Optional[float] = None

    rear_camera_main_mp: Optional[float] = None
    front_camera_main_mp: Optional[float] = None

    os_name: Optional[str] = None

    memory_card_supported: Optional[bool] = None
    memory_card_type: Optional[str] = None

    condition_score: Optional[float] = 100.0


@router.post("/predict")
def predict_device_price(
    request: DevicePredictionRequest
):

    try:

        device_data = request.model_dump()

        condition_score = device_data.pop(
            "condition_score",
            100.0
        )

        result = calculate_ml_valuation(
            device_data,
            condition_score
        )

        return {
            "success": True,
            "valuation": result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )