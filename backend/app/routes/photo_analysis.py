from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.supabase import supabase

from app.models.inspection import Inspection
from app.models.inspection_photo import InspectionPhoto
from app.models.inspection_answer import InspectionAnswer

from app.models.device import Device

from app.services.photo_analyzer import analyze_image
from app.services.condition_analyzer import analyze_condition
from app.services.valuation import (
    predict_market_price,
    calculate_condition_score,
)

from app.schemas.inspection_answer import (
    InspectionAnswersRequest,
)


router = APIRouter(
    prefix="/api/inspections",
    tags=["Photo Analysis"]
)


BUCKET_NAME = "device-inspections"


@router.post("/{inspection_code}/analyze")
def analyze_photos(
    inspection_code: str,
    db: Session = Depends(get_db)
):
    # ---------------------------------------------------------
    # 1. Find inspection
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # 2. Get all photos
    # ---------------------------------------------------------

    photos = (
        db.query(InspectionPhoto)
        .filter(
            InspectionPhoto.inspection_id
            == inspection.id
        )
        .all()
    )

    # ---------------------------------------------------------
    # 3. Verify all six views exist
    # ---------------------------------------------------------

    required_types = {
        "front",
        "back",
        "left",
        "right",
        "top",
        "bottom"
    }

    captured_types = {
        photo.photo_type
        for photo in photos
    }

    missing = required_types - captured_types

    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "All six photos are required.",
                "missing": sorted(list(missing))
            }
        )

    # ---------------------------------------------------------
    # 4. Analyze every photo
    # ---------------------------------------------------------

    results = []

    for photo in photos:

        try:
            # Download image from Supabase
            image_bytes = (
                supabase.storage
                .from_(BUCKET_NAME)
                .download(photo.storage_path)
            )

            # -------------------------------------------------
            # A. Existing OpenCV + YOLO analysis
            # -------------------------------------------------

            photo_analysis = analyze_image(
                image_bytes
            )

            # -------------------------------------------------
            # B. Gemini physical-condition analysis
            # -------------------------------------------------

            condition_analysis = analyze_condition(
                image_bytes=image_bytes,
                photo_type=photo.photo_type
            )

            # -------------------------------------------------
            # C. Combine both results
            # -------------------------------------------------

            combined_analysis = {
                **photo_analysis,
                "physical_condition": condition_analysis
            }

            results.append({
                "photo_type": photo.photo_type,
                "analysis": combined_analysis
            })

        except Exception as error:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Unable to analyze "
                    f"{photo.photo_type}: {error}"
                )
            )

    # ---------------------------------------------------------
    # 5. Calculate overall photo quality
    # ---------------------------------------------------------

    scores = [
        item["analysis"]["quality_score"]
        for item in results
    ]

    overall_quality = round(
        sum(scores) / len(scores)
    )

    if overall_quality >= 80:
        overall_grade = "Excellent"

    elif overall_quality >= 60:
        overall_grade = "Good"

    elif overall_quality >= 40:
        overall_grade = "Fair"

    else:
        overall_grade = "Poor"

    # ---------------------------------------------------------
    # 6. Calculate overall physical-condition score
    # ---------------------------------------------------------

    damage_scores = []

    condition_confidences = []

    for item in results:

        condition = item["analysis"].get(
            "physical_condition",
            {}
        )

        damage_score = condition.get(
            "visible_damage_score"
        )

        confidence = condition.get(
            "confidence"
        )

        if isinstance(damage_score, (int, float)):
            damage_scores.append(
                float(damage_score)
            )

        if isinstance(confidence, (int, float)):
            condition_confidences.append(
                float(confidence)
            )

    if damage_scores:

        average_damage = (
            sum(damage_scores)
            / len(damage_scores)
        )

        physical_condition_score = round(
            100 - average_damage
        )

    else:

        physical_condition_score = None

    if physical_condition_score is not None:

        if physical_condition_score >= 90:
            physical_condition_grade = "Excellent"

        elif physical_condition_score >= 75:
            physical_condition_grade = "Good"

        elif physical_condition_score >= 50:
            physical_condition_grade = "Fair"

        else:
            physical_condition_grade = "Poor"

    else:

        physical_condition_grade = "Pending"

    # ---------------------------------------------------------
    # 7. Average Gemini confidence
    # ---------------------------------------------------------

    if condition_confidences:

        average_confidence = round(
            sum(condition_confidences)
            / len(condition_confidences),
            3
        )

    else:

        average_confidence = None

    # ---------------------------------------------------------
    # 8. Final response
    # ---------------------------------------------------------

    return {
        "inspection_code": inspection_code,

        "photos_analyzed": len(results),

        "overall_photo_quality": overall_quality,

        "overall_grade": overall_grade,

        "physical_condition_ai": {
            "status": "completed",

            "condition_score":
                physical_condition_score,

            "condition_grade":
                physical_condition_grade,

            "average_confidence":
                average_confidence
        },

        "photos": results
    }


# ============================================================
# COMBINED PHOTO VALUATION
# ============================================================

@router.post("/{inspection_code}/valuate")
def photo_valuation(
    inspection_code: str,
    db: Session = Depends(get_db)
):
    # ---------------------------------------------------------
    # 1. Find inspection + device
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # 2. Run photo analysis pipele (reuse analyze logic)
    # ---------------------------------------------------------

    analysis = analyze_photos(
        inspection_code,
        db
    )

    physical_condition_score = (
        analysis["physical_condition_ai"]
        .get("condition_score")
    )

    if physical_condition_score is None:
        raise HTTPException(
            status_code=422,
            detail="Unable to determine physical condition."
        )

    # ---------------------------------------------------------
    # 3. ML market price
    # ---------------------------------------------------------

    try:
        market_price = predict_market_price(
            brand=device.brand,
            model=device.model,
            storage=device.storage
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    # ---------------------------------------------------------
    # 4. Condition multiplier (same range as valuation.py)
    # ---------------------------------------------------------

    condition_multiplier = 0.60 + (
        max(
            0.0,
            min(100.0, physical_condition_score)
        )
        / 100.0
    ) * 0.40

    if physical_condition_score >= 90:
        condition_grade = "A+"
    elif physical_condition_score >= 80:
        condition_grade = "A"
    elif physical_condition_score >= 70:
        condition_grade = "B"
    elif physical_condition_score >= 60:
        condition_grade = "C"
    else:
        condition_grade = "D"

    # ---------------------------------------------------------
    # 5. Final prices
    # ---------------------------------------------------------

    resale_price = round(
        market_price * condition_multiplier
    )

    exchange_price = round(
        resale_price * 0.88
    )

    # ---------------------------------------------------------
    # 6. Persist prices
    # ---------------------------------------------------------

    inspection.estimated_resale_price = resale_price
    inspection.estimated_exchange_price = exchange_price
    inspection.status = "valuated"

    db.commit()

    # ---------------------------------------------------------
    # 7. Response
    # ---------------------------------------------------------

    return {
        "inspection_code": inspection_code,

        "market_price": market_price,
        "resale_price": resale_price,
        "exchange_price": exchange_price,

        "condition_score": physical_condition_score,
        "condition_grade": condition_grade,
        "condition_multiplier": round(
            condition_multiplier,
            4
        ),

        "valuation_type": "AI Photo + ML Valuation",

        "overall_photo_quality":
            analysis["overall_photo_quality"],

        "physical_condition_ai":
            analysis["physical_condition_ai"],
    }


# ============================================================
# EXCHANGE INSPECTION (questionnaire + AI photos)
# ============================================================

@router.post("/{inspection_code}/exchange-valuate")
def exchange_inspection_valuation(
    inspection_code: str,
    data: InspectionAnswersRequest,
    db: Session = Depends(get_db)
):
    # ---------------------------------------------------------
    # 1. Find inspection + device
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # 2. Questionnaire condition score
    # ---------------------------------------------------------

    answer_dict = {
        item.question_key: item.answer_value
        for item in data.answers
    }

    questionnaire_score = calculate_condition_score(
        answer_dict
    )

    # ---------------------------------------------------------
    # 3. Save answers for the record
    # ---------------------------------------------------------

    for item in data.answers:
        db.add(
            InspectionAnswer(
                inspection_id=inspection.id,
                question_key=item.question_key,
                answer_value=item.answer_value
            )
        )

    # ---------------------------------------------------------
    # 4. Run photo analysis (AI physical condition)
    # ---------------------------------------------------------

    analysis = analyze_photos(
        inspection_code,
        db
    )

    ai_condition_score = (
        analysis["physical_condition_ai"]
        .get("condition_score")
    )

    if ai_condition_score is None:
        ai_condition_score = questionnaire_score

    # ---------------------------------------------------------
    # 5. Combine both condition signals (50/50 blend)
    # ---------------------------------------------------------

    combined_condition_score = round(
        (questionnaire_score + ai_condition_score) / 2
    )

    # ---------------------------------------------------------
    # 6. ML market price
    # ---------------------------------------------------------

    try:
        market_price = predict_market_price(
            brand=device.brand,
            model=device.model,
            storage=device.storage
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    # ---------------------------------------------------------
    # 7. Condition multiplier + grade
    # ---------------------------------------------------------

    condition_multiplier = 0.60 + (
        max(
            0.0,
            min(100.0, combined_condition_score)
        )
        / 100.0
    ) * 0.40

    if combined_condition_score >= 90:
        condition_grade = "A+"
    elif combined_condition_score >= 80:
        condition_grade = "A"
    elif combined_condition_score >= 70:
        condition_grade = "B"
    elif combined_condition_score >= 60:
        condition_grade = "C"
    else:
        condition_grade = "D"

    # ---------------------------------------------------------
    # 8. Final prices
    # ---------------------------------------------------------

    resale_price = round(
        market_price * condition_multiplier
    )

    exchange_price = round(
        resale_price * 0.88
    )

    # ---------------------------------------------------------
    # 9. Persist
    # ---------------------------------------------------------

    inspection.estimated_resale_price = resale_price
    inspection.estimated_exchange_price = exchange_price
    inspection.status = "valuated"

    db.commit()

    # ---------------------------------------------------------
    # 10. Response
    # ---------------------------------------------------------

    return {
        "inspection_code": inspection_code,

        "market_price": market_price,
        "resale_price": resale_price,
        "exchange_price": exchange_price,

        "condition_score": combined_condition_score,
        "condition_grade": condition_grade,
        "condition_multiplier": round(
            condition_multiplier,
            4
        ),

        "questionnaire_score": questionnaire_score,
        "ai_condition_score": ai_condition_score,

        "valuation_type": "Complete Exchange Inspection",
    }