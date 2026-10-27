from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.ml_valuation import calculate_ml_valuation
from ml.feature_schema import (
    CONDITION_FEATURES,
    SPEC_FEATURES,
)


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

    # A flat 0..100 summary. Omit it (or send null) when you are
    # describing the device with the individual features below;
    # the reported score is then derived from those features.
    condition_score: Optional[float] = None

    diagnostic_score: Optional[float] = None

    # Individual condition inputs. When supplied they override
    # the values derived from the flat `condition_score`, so a
    # caller can be precise instead of guessing with one number.
    device_age_months: Optional[float] = None
    battery_health_pct: Optional[float] = None
    screen_condition_score: Optional[float] = None
    body_condition_score: Optional[float] = None
    camera_condition_score: Optional[float] = None
    scratch_severity: Optional[float] = None
    dent_severity: Optional[float] = None
    crack_severity: Optional[float] = None
    frame_damage_severity: Optional[float] = None
    functional_test_score: Optional[float] = None
    diagnostics_failed_count: Optional[float] = None
    repair_history_code: Optional[float] = None
    accessories_code: Optional[float] = None
    warranty_months_remaining: Optional[float] = None
    ai_condition_score: Optional[float] = None


@router.post("/predict")
def predict_device_value(
    request: DevicePredictionRequest
):
    """Raw DEVICE VALUE prediction.

    Returns a single `device_value`. There is no
    `resale_price` and no `exchange_price`.

    Accepts either:
      - individual condition features (preferred), or
      - a flat `condition_score`, which is expanded across the
        condition features as a fallback.

    Condition and diagnostics are model INPUTS here, not
    multipliers applied to a spec-only prediction.
    """

    try:

        payload = request.model_dump()

        condition_score = payload.pop(
            "condition_score",
            None,
        )

        diagnostic_score = payload.pop(
            "diagnostic_score",
            None,
        )

        # Any explicitly supplied condition feature overrides
        # the flat-score expansion.
        overrides = {
            key: value
            for key, value in payload.items()
            if key in CONDITION_FEATURES
            and value is not None
        }

        device_data = {
            key: value
            for key, value in payload.items()
            if key in SPEC_FEATURES
        }

        device_data.update(overrides)

        # `None` here means "no flat score supplied": the
        # service then reports the score the individual
        # features imply instead of assuming a perfect device.
        if (
            condition_score is None
            and not overrides
        ):
            condition_score = 100.0

        extra = {}

        if diagnostic_score is not None:
            extra["diagnostic_score"] = diagnostic_score

        result = calculate_ml_valuation(
            device_data,
            condition_score,
            **extra,
        )

        return {
            "success": True,
            "valuation": result,
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )