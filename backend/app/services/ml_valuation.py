"""ML valuation service (thin wrapper over the pipeline).

The DEVICE VALUE model takes one prediction. This module keeps
`calculate_ml_valuation` as a compatibility entry point for the
`/ml/predict` route, but the arithmetic is no longer done here:
condition and diagnostics are passed straight through as model
inputs.

If the caller supplies only a flat `condition_score`, it is
expanded into the individual condition features using the
questionnaire mapping, so even the legacy request shape
influences the prediction through real features rather than a
multiplier.
"""

from app.core.logger import get_logger
from app.services.valuation.condition_features import (
    calculate_condition_score,
    condition_score_from_features,
    get_condition_grade,
)
from ml.feature_schema import (
    SPEC_FEATURES,
    validate_feature_contract,
)
from ml.price_predictor import (
    predict_device_value_with_details,
)


logger = get_logger(__name__)


def expand_condition_score(
    condition_score: float | None,
    features: dict
) -> dict:
    """Spread one flat condition score across the condition features.

    Used only by the raw `/ml/predict` endpoint, which accepts a
    single `condition_score` instead of a questionnaire. The
    questionnaire flow always produces individual features
    directly, so this path is the exception, not the rule.

    A `None` score means the caller is supplying individual
    features, so the neutral baseline starts at 1.0 (no
    assumed damage) and only the supplied features count.
    """

    validate_feature_contract()

    score = max(
        0.0,
        min(100.0, float(condition_score)),
    )

    ratio = score / 100.0

    # A condition score maps onto the same damage scale the
    # scenario generator uses: 100 -> no damage (severity 0),
    # low score -> severe damage (severity 3).
    damage_level = (
        0 if ratio >= 0.9
        else 1 if ratio >= 0.7
        else 2 if ratio >= 0.45
        else 3
    )

    row = {feature: None for feature in SPEC_FEATURES}

    row.update(
        {
            "device_age_months": round(
                4.0 + (1.0 - ratio) * 44.0, 2
            ),
            "battery_health_pct": round(
                35.0 + ratio * 65.0, 2
            ),
            "screen_condition_score": round(
                ratio * 100.0, 2
            ),
            "body_condition_score": round(
                ratio * 100.0, 2
            ),
            "camera_condition_score": round(
                60.0 + ratio * 40.0, 2
            ),
            "scratch_severity": float(
                damage_level
            ),
            "dent_severity": float(
                damage_level
            ),
            "crack_severity": (
                0.0
                if ratio >= 0.85
                else float(damage_level)
            ),
            "frame_damage_severity": float(
                damage_level
            ),
            "functional_test_score": round(
                ratio * 100.0, 2
            ),
            "diagnostic_score": round(
                ratio * 100.0, 2
            ),
            "diagnostics_failed_count": float(
                (1.0 - ratio) * 5.0
            ),
            "diagnostic_camera_failed": (
                0.0 if ratio >= 0.7 else 1.0
            ),
            "diagnostic_microphone_failed": (
                0.0 if ratio >= 0.6 else 1.0
            ),
            "diagnostic_touch_failed": (
                0.0 if ratio >= 0.75 else 1.0
            ),
            "diagnostic_sensor_failed": (
                0.0 if ratio >= 0.65 else 1.0
            ),
            "diagnostic_connectivity_failed": (
                0.0 if ratio >= 0.7 else 1.0
            ),
            "repair_history_code": (
                0.0 if ratio >= 0.85 else 1.0
            ),
            "accessories_code": float(
                3 if ratio >= 0.8
                else 2 if ratio >= 0.6
                else 1
            ),
            "warranty_months_remaining": round(
                ratio * 12.0, 2
            ),
            "ai_condition_score": round(
                ratio * 100.0, 2
            ),
        }
    )

    for feature, value in features.items():
        if feature in row and value is not None:
            row[feature] = value

    return row


def calculate_ml_valuation(
    device_data: dict,
    condition_score: float | None = 100.0,
    diagnostic_score: float | None = None,
) -> dict:
    """Raw ML valuation for the `/ml/predict` endpoint.

    Returns a single `device_value`. There is no
    `resale_price`, no `exchange_price` and no condition
    multiplier.

    Pass `condition_score=None` to say "I am describing the
    device with individual features instead of one number".
    """

    payload = dict(device_data or {})

    payload.pop("condition_score", None)
    payload.pop("diagnostic_score", None)

    score_was_given = condition_score is not None

    if score_was_given:

        score = max(
            0.0,
            min(100.0, float(condition_score)),
        )

    else:

        score = 100.0

    feature_row = expand_condition_score(
        score,
        payload,
    )

    if diagnostic_score is not None:

        ratio = max(
            0.0,
            min(100.0, float(diagnostic_score)),
        ) / 100.0

        feature_row["diagnostic_score"] = round(
            ratio * 100.0, 2
        )

    prediction = predict_device_value_with_details(
        feature_row
    )

    # The flat score is echoed back when the caller sent one.
    # Otherwise the reported score is derived from whatever
    # condition features the caller did send, so the response
    # never claims a perfect device alongside, say, a cracked
    # screen.
    if score_was_given:

        reported_score = round(score, 2)

    else:

        reported_score = condition_score_from_features(
            feature_row
        )

    return {
        "device_value": prediction["device_value"],
        "currency": prediction["currency"],
        "confidence": prediction["confidence"],
        "condition_score": reported_score,
        "diagnostic_score": (
            round(float(diagnostic_score), 2)
            if diagnostic_score is not None
            else feature_row["diagnostic_score"]
        ),
        "condition_grade": get_condition_grade(
            reported_score
        ),
        "prediction_interval": prediction[
            "prediction_interval"
        ],
        "tree_disagreement_pct": prediction[
            "tree_disagreement_pct"
        ],
        "prediction_source": prediction[
            "prediction_source"
        ],
        "model_type": prediction["model_type"],
        "input_features": prediction["input_features"],
    }


__all__ = [
    "calculate_ml_valuation",
    "expand_condition_score",
    "calculate_condition_score",
]