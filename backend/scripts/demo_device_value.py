"""Demonstration: DEVICE VALUE for one example device.

Shows the full pipeline: input features, predicted device
value, condition score, diagnostic score, and confidence.

    cd backend
    python -m scripts.demo_device_value
"""

import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.services.valuation import (
    build_feature_row,
    predict_device_value_for_device,
)
from ml.feature_schema import CONDITION_FEATURES
from ml.price_predictor import (
    predict_device_value_with_details,
)


# ============================================================
# EXAMPLE DEVICE
#
# A mid-range phone, 16 months old, light cosmetic wear, one
# failed sensor test, no repair history, no warranty.
# ============================================================

BRAND = "samsung"
MODEL = "galaxy m"
STORAGE = "6GB + 128GB"

ANSWERS = {
    "device_age": "1 to 2 years",
    "screen_condition": "minor_scratches",
    "body_condition": "multiple_scratches",
    "battery_condition": "good",
    "functionality": "yes",
    "original_charger": "no",
    "original_box": "no",
    "repair_history": "no",
}

DIAGNOSTICS_REPORT = {
    "sensorResults": {
        "camera": "passed",
        "microphone": "passed",
        "touch": "passed",
        "motion": "passed",
        "location": "failed",
    },
    "selfReport": {
        "battery": "good",
        "charging": "yes",
        "speaker": "good",
        "buttons": "yes",
        "connectivity": "yes",
        "screen_touch": "yes",
    },
}

# Stand-in for Gemini/YOLO photo analysis. Real flows pass the
# dict returned by /api/inspections/{code}/analyze.
PHOTO_ANALYSIS = {
    "photos": [
        {
            "photo_type": view,
            "analysis": {
                "quality_score": 88,
                "phone_detection": {"detected": True},
                "physical_condition": {
                    "screen_condition": "good",
                    "body_condition": "good",
                    "scratches": {
                        "detected": True,
                        "severity": "minor",
                    },
                    "dents": {
                        "detected": False,
                        "severity": "none",
                    },
                    "cracks": {
                        "detected": False,
                        "severity": "none",
                    },
                    "frame_damage": {
                        "detected": True,
                        "severity": "minor",
                    },
                    "visible_damage_score": 14,
                    "confidence": 0.88,
                },
            },
        }
        for view in (
            "front", "back", "left", "right", "top", "bottom"
        )
    ]
}


def main():
    valuation = predict_device_value_for_device(
        brand=BRAND,
        model=MODEL,
        storage=STORAGE,
        answers=ANSWERS,
        photo_analysis=PHOTO_ANALYSIS,
        working="yes",
        diagnostics_score=80.0,
        diagnostics_report=DIAGNOSTICS_REPORT,
        include_features=True,
    )

    print("\n" + "=" * 66)
    print("DEVICE VALUE - END TO END EXAMPLE")
    print("=" * 66)

    print(f"\nDevice            : {BRAND} {MODEL} {STORAGE}")
    print(f"Matched reference : Rs.{valuation['reference_price']:,.0f}"
          "  (dataset market price, context only)")

    print("\n" + "-" * 66)
    print("INPUT FEATURES")
    print("-" * 66)

    features = valuation["input_features"]

    print("\nCondition / diagnostic features:")
    for name in CONDITION_FEATURES:
        print(f"  {name:<34} {features[name]}")

    print("\n" + "-" * 66)
    print("RESULT")
    print("-" * 66)

    print(f"\n  device_value     : Rs.{valuation['device_value']:,}")
    print(f"  currency         : {valuation['currency']}")
    print(f"  confidence       : {valuation['confidence']}")
    print(
        f"  prediction range : Rs.{valuation['prediction_interval']['low']:,}"
        f" - Rs.{valuation['prediction_interval']['high']:,}"
    )
    print(f"  condition_score  : {valuation['condition_score']}/100"
          f"  (grade {valuation['condition_grade']})")
    print(f"  diagnostic_score : {valuation['diagnostic_score']}/100")
    print(f"  ai_condition     : {valuation['ai_condition_score']}/100"
          f"  ({valuation['ai_views_analyzed']} views)")
    print(f"  evidence coverage: {valuation['evidence_coverage']}")

    print("\n  Response JSON:")
    print(json.dumps(
        {
            "device_value": valuation["device_value"],
            "currency": valuation["currency"],
            "condition_score": valuation["condition_score"],
            "diagnostic_score": valuation["diagnostic_score"],
            "confidence": valuation["confidence"],
        },
        indent=2,
    ))

    # Same device, worse condition: the single number must fall.
    print("\n" + "-" * 66)
    print("CONDITION SENSITIVITY (same device)")
    print("-" * 66)

    row, _ = build_feature_row(
        brand=BRAND,
        model=MODEL,
        storage=STORAGE,
        answers=ANSWERS,
        photo_analysis=PHOTO_ANALYSIS,
        working="yes",
        diagnostics_score=80.0,
        diagnostics_report=DIAGNOSTICS_REPORT,
    )

    baseline = row.copy()

    variants = [
        ("as assessed above", {}),
        ("screen cracked", {"crack_severity": 3.0,
                            "screen_condition_score": 18.0}),
        ("camera dead", {"diagnostic_camera_failed": 1.0,
                         "diagnostics_failed_count": 2.0}),
        ("4 years old", {"device_age_months": 48.0}),
        ("third-party repair",
         {"repair_history_code": 2.0}),
    ]

    for label, override in variants:

        probe = dict(baseline)
        probe.update(override)

        result = predict_device_value_with_details(probe)

        print(f"  {label:<22} Rs.{result['device_value']:>9,}")

    print()


if __name__ == "__main__":
    main()