import random
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.device import Device
from app.models.inspection import Inspection
from app.models.inspection_answer import InspectionAnswer

from app.schemas.inspection import (
    InspectionCreate,
    InspectionResponse
)

from app.schemas.inspection_answer import (
    InspectionAnswersRequest,
    ValuationResponse
)

from app.services.valuation import (
    calculate_valuation
)


router = APIRouter(
    prefix="/api/inspections",
    tags=["Inspections"]
)


# ============================================================
# INSPECTION CODE
# ============================================================

def generate_inspection_code():

    characters = (
        string.ascii_uppercase
        + string.digits
    )

    code = "".join(
        random.choices(
            characters,
            k=6
        )
    )

    return (
        f"INS-{datetime.now().year}-{code}"
    )


# ============================================================
# CREATE INSPECTION
# ============================================================

@router.post(
    "",
    response_model=InspectionResponse
)
def create_inspection(
    data: InspectionCreate,
    db: Session = Depends(get_db)
):

    device = Device(
        brand=data.brand,
        model=data.model,
        storage=data.storage,
        created_at=datetime.now().isoformat()
    )

    db.add(device)

    db.flush()

    inspection_code = (
        generate_inspection_code()
    )

    inspection = Inspection(
        inspection_code=inspection_code,
        device_id=device.id,
        inspection_type=data.inspection_type,
        status="created"
    )

    db.add(inspection)

    db.commit()

    db.refresh(inspection)

    return InspectionResponse(
        inspection_code=inspection.inspection_code,
        brand=device.brand,
        model=device.model,
        storage=device.storage,
        inspection_type=inspection.inspection_type,
        status=inspection.status,
        estimated_resale_price=None,
        estimated_exchange_price=None
    )


# ============================================================
# SUBMIT ANSWERS + ML VALUATION
# ============================================================

@router.post(
    "/{inspection_code}/answers",
    response_model=ValuationResponse
)
def submit_answers(
    inspection_code: str,
    data: InspectionAnswersRequest,
    db: Session = Depends(get_db)
):

    inspection = (
        db.query(Inspection)
        .filter(
            Inspection.inspection_code
            == inspection_code
        )
        .first()
    )

    if not inspection:

        raise HTTPException(
            status_code=404,
            detail="Inspection not found"
        )

    device = (
        db.query(Device)
        .filter(
            Device.id
            == inspection.device_id
        )
        .first()
    )

    if not device:

        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    # --------------------------------------------------------
    # Convert answers to dictionary
    # --------------------------------------------------------

    answer_dict = {
        item.question_key:
        item.answer_value

        for item in data.answers
    }

    # --------------------------------------------------------
    # Save answers
    # --------------------------------------------------------

    for item in data.answers:

        answer = InspectionAnswer(
            inspection_id=inspection.id,
            question_key=item.question_key,
            answer_value=item.answer_value
        )

        db.add(answer)

    # --------------------------------------------------------
    # ML VALUATION
    # --------------------------------------------------------

    try:

        valuation = calculate_valuation(
            brand=device.brand,
            model=device.model,
            storage=device.storage,
            answers=answer_dict
        )

    except ValueError as e:

        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(e)
        )

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Valuation failed: {str(e)}"
        )

    # --------------------------------------------------------
    # Update inspection
    # --------------------------------------------------------

    inspection.estimated_resale_price = (
        valuation["resale_price"]
    )

    inspection.estimated_exchange_price = (
        valuation["exchange_price"]
    )

    inspection.status = "valuated"

    db.commit()

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return ValuationResponse(

        inspection_code=(
            inspection.inspection_code
        ),

        market_price=(
            valuation["market_price"]
        ),

        resale_price=(
            valuation["resale_price"]
        ),

        exchange_price=(
            valuation["exchange_price"]
        ),

        condition_score=(
            valuation["condition_score"]
        ),

        condition_grade=(
            valuation["condition_grade"]
        ),

        model_source=(
            valuation["model_source"]
        ),

        valuation_type=(
            valuation["valuation_type"]
        ),
    )