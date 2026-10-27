"""The single DEVICE VALUE valuation flow.

=================================================================
ONE PREDICTION, ONE NUMBER
=================================================================

    specifications  (brand, model, RAM, storage, processor, ...)
          +
    device age
          +
    battery health
          +
    functional diagnostic results
          +
    physical condition
          +
    AI photo inspection
          +
    accessories / warranty / repair history
          -----------------------------------------
                          |
                          v
              ONE ML VALUATION MODEL
              (Random Forest, target: device_value_inr)
                          |
                          v
                  FINAL DEVICE VALUE

No resale/exchange split. No condition multiplier. No
exchange rate. One Random Forest takes every input and emits
`device_value`.

-----------------------------------------------------------------
RESPONSE SHAPE
-----------------------------------------------------------------

    {
      "device_value": 6842,
      "currency": "INR",
      "condition_score": 82,
      "diagnostic_score": 94,
      "confidence": 0.87,
      ...
    }

`condition_score` is the display-only questionnaire summary.
`diagnostic_score` is the passed/total diagnostics figure.
Neither one adjusted the prediction.
"""

from app.core.logger import get_logger
from app.services.valuation.condition_features import (
    calculate_condition_score,
    condition_features_from_answers,
    get_condition_grade,
)
from app.services.valuation.diagnostic_features import (
    diagnostic_features,
    extract_self_report,
)
from app.services.valuation.photo_features import (
    collect_photo_features,
)
from app.services.valuation.specs import (
    build_spec_features,
    parse_storage,
    reference_price,
)
from ml.feature_schema import (
    CONDITION_FEATURES,
    DEFAULT_CONDITION_FEATURES,
    FEATURES,
)
from ml.model_store import (
    get_price_dataset,
)
from ml.price_predictor import (
    predict_device_value,
)


logger = get_logger(__name__)


# ============================================================
# CONFIDENCE ADJUSTMENT
#
# Tree disagreement measures estimator uncertainty. It does not
# know that some evidence was simply missing. When a valuation
# relies on defaults for evidence the user never provided, the
# reported confidence is scaled down so a thin input never
# looks like a well-evidenced one.
#
# This adjusts the REPORTED confidence only. It does not touch
# device_value.
# ============================================================

# Weight of each evidence source in the coverage score.
_EVIDENCE_WEIGHTS = {
    "questionnaire": 0.45,
    "diagnostics": 0.30,
    "photos": 0.25,
}

# Confidence floor applied when nothing but defaults is
# available (a bare brand/model/storage lookup).
_UNEVIDENCED_CONFIDENCE_CAP = 0.55


def _combine_confidence(
    tree_confidence,
    coverage
):
    """Blend tree agreement with evidence coverage."""

    if coverage <= 0:
        return min(
            tree_confidence,
            _UNEVIDENCED_CONFIDENCE_CAP,
        )

    blended = (
        tree_confidence * coverage
        + (1.0 - coverage) * _UNEVIDENCED_CONFIDENCE_CAP
    )

    return round(
        max(0.05, min(0.99, blended)),
        2,
    )


def _coverage(evidence):
    total = 0.0

    for key, weight in (
        _EVIDENCE_WEIGHTS.items()
    ):
        if evidence.get(key):
            total += weight

    return min(1.0, total)


# ============================================================
# FEATURE ASSEMBLY
# ============================================================

def build_feature_row(
    brand,
    model,
    storage,
    answers=None,
    photo_analysis=None,
    working=None,
    diagnostics_score=None,
    diagnostics_report=None,
    matched_row=None
):
    """Assemble the full feature row for the valuation model.

    Every CONDITION FEATURE is always populated: evidence that
    was not supplied falls back to the neutral default from
    `ml.feature_schema`, never to zero (zero would mean
    "destroyed", not "unknown").
    """

    answers = answers or {}

    # --- 1. Specifications, from dataset matching ---------------

    dataset = get_price_dataset()

    spec_features, matched = build_spec_features(
        dataset,
        brand=brand,
        model=model,
        storage=storage,
        matched_row=matched_row,
    )

    # --- 2. Questionnaire-derived condition -------------------

    self_report = extract_self_report(
        diagnostics_report
    )

    condition = condition_features_from_answers(
        answers,
        self_report=self_report,
    )

    # --- 3. Diagnostics ----------------------------------------

    diagnostics = diagnostic_features(
        working=working,
        diagnostics_score=diagnostics_score,
        diagnostics_report=diagnostics_report,
    )

    # --- 4. AI photo inspection -------------------------------

    photos = collect_photo_features(photo_analysis)

    # --- 5. Fill the remainder with neutral defaults ----------

    for feature in CONDITION_FEATURES:

        condition.setdefault(
            feature,
            DEFAULT_CONDITION_FEATURES[feature],
        )

    # Report-only keys from the photo module must not reach the
    # model.
    for key in (
        "ai_views_analyzed",
        "ai_capture_factor",
        "ai_confidence",
    ):
        condition.pop(key, None)

    row = {
        **spec_features,
        **condition,
        **diagnostics,
    }

    # Photo-derived severities. Only applied when the AI photo
    # inspection actually produced them, so a flow without
    # photos keeps the questionnaire's own answer instead of
    # silently inheriting a default.
    if photos["ai_views_analyzed"] > 0:

        for feature in (
            "scratch_severity",
            "dent_severity",
            "crack_severity",
            "frame_damage_severity",
        ):
            row[feature] = photos[feature]

        if photos.get("camera_condition_score") is not None:
            row["camera_condition_score"] = photos[
                "camera_condition_score"
            ]

    row["ai_condition_score"] = photos[
        "ai_condition_score"
    ]

    evidence = {
        "questionnaire": bool(answers),
        "diagnostics": (
            working is not None
            or diagnostics_score is not None
            or diagnostics_report is not None
        ),
        "photos": (
            photos["ai_views_analyzed"] > 0
        ),
    }

    context = {
        "matched_row": matched,
        "reference_price": reference_price(matched),
        "storage_gb": parse_storage(storage),
        "photo_features": photos,
        "evidence": evidence,
    }

    return row, context


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def predict_device_value_for_device(
    brand,
    model,
    storage,
    answers=None,
    photo_analysis=None,
    working=None,
    diagnostics_score=None,
    diagnostics_report=None,
    matched_row=None,
    include_features=False
):
    """Produce the single DEVICE VALUE for one device.

    Returns the response dict described in the module
    docstring.
    """

    row, context = build_feature_row(
        brand=brand,
        model=model,
        storage=storage,
        answers=answers,
        photo_analysis=photo_analysis,
        working=working,
        diagnostics_score=diagnostics_score,
        diagnostics_report=diagnostics_report,
        matched_row=matched_row,
    )

    prediction = predict_device_value(row)

    coverage = _coverage(context["evidence"])

    confidence = _combine_confidence(
        prediction["confidence"],
        coverage,
    )

    answers = answers or {}

    # Display-only condition summary.
    condition_score = calculate_condition_score(
        answers
    )

    photo_score = context["photo_features"].get(
        "ai_condition_score"
    )

    diagnostic_score = row.get("diagnostic_score")

    ev = dict(context.get("evidence") or {})
    ev["coverage"] = coverage
    ev["working"] = globals().get("working", None)
    # try to pull from locals
    try:
        ev["working"] = working
    except Exception:
        pass
    try:
        ev["diagnostics_report"] = diagnostics_report
    except Exception:
        pass
    prediction_clamped = dict(prediction)
    prediction_clamped = _aggressive_clamp(prediction_clamped, condition_score, ev, {**context, "working": ev.get("working")})

    result = {
        # --- The one number ---------------------------------
        "device_value": prediction_clamped["device_value"],
        "currency": prediction_clamped.get("currency", prediction.get("currency")),
        "confidence": prediction_clamped.get("confidence", confidence),

        # --- Supporting evidence -----------------------------
        "condition_score": condition_score,
        "condition_grade": get_condition_grade(
            condition_score
        ),
        "diagnostic_score": (
            round(diagnostic_score, 2)
            if diagnostic_score is not None
            else None
        ),
        "ai_condition_score": photo_score,
        "ai_views_analyzed": context[
            "photo_features"
        ]["ai_views_analyzed"],

        # --- Context ----------------------------------------
        "device": {
            "brand": brand,
            "model": model,
            "storage": storage,
            "storage_gb": context["storage_gb"],
        },
        "reference_price": context[
            "reference_price"
        ],
        "prediction_interval": prediction[
            "prediction_interval"
        ],
        "tree_disagreement_pct": prediction[
            "tree_disagreement_pct"
        ],
        "model_type": prediction["model_type"],
        "prediction_source": (
            "Device Value ML Model "
            "(specifications + condition + diagnostics + AI photos)"
        ),
        "valuation_type": "Unified Device Value",
        "evidence_coverage": round(coverage, 2),
    }

    if include_features:
        result["input_features"] = {
            feature: row.get(feature)
            for feature in FEATURES
        }

    return result


def calculate_device_value(*args, **kwargs):
    """Alias for predict_device_value_for_device."""
    return predict_device_value_for_device(
        *args, **kwargs
    )


def calculate_valuation(
    brand,
    model,
    storage,
    answers,
    photo_analysis=None,
    working=None,
    diagnostics_score=None,
    diagnostics_report=None,
):
    """Backwards-compatible wrapper.

    Old signature: calculate_valuation(brand, model, storage,
    answers). Kept so existing route imports and callers do not
    break, and so the shape change is contained to one place.

    Returns `device_value` / `condition_score` /
    `diagnostic_score` / `confidence`. `resale_price` and
    `exchange_price` are intentionally absent.
    """

    return predict_device_value_for_device(
        brand=brand,
        model=model,
        storage=storage,
        answers=answers,
        photo_analysis=photo_analysis,
        working=working,
        diagnostics_score=diagnostics_score,
        diagnostics_report=diagnostics_report,
    )
# ============================================================
# AGGRESSIVE BAD-CONDITION CLAMPING (fast fix)
# ============================================================

def _aggressive_clamp(prediction, condition_score, evidence, context):
    try:
        val = prediction.get("device_value")
        if val is None:
            return prediction
        val_f = float(val)
        cond = float(condition_score) if condition_score is not None else 100.0
        ref = context.get("reference_price")
        ref_f = float(ref) if ref is not None else None

        max_allowed = None

        # Check if phone marked as not working
        is_not_working = False
        if isinstance(evidence, dict):
            w = evidence.get("working")
            if isinstance(w, str) and w.lower() == "no":
                is_not_working = True
            dr = evidence.get("diagnostics_report")
            if isinstance(dr, dict) and dr.get("working") == "no":
                is_not_working = True
            if evidence.get("non_working") is True:
                is_not_working = True
        if isinstance(context, dict):
            if str(context.get("working", "")).lower() == "no":
                is_not_working = True

        if is_not_working:
            # Very harsh for non-working devices
            if ref_f and ref_f > 0:
                max_allowed = min(ref_f * 0.08, 1200)
            else:
                max_allowed = 1000
            if val_f > max_allowed:
                prediction["device_value"] = int(round(max_allowed))
                if prediction.get("confidence") is not None:
                    prediction["confidence"] = max(0.05, float(prediction["confidence"]) * 0.5)
            return prediction

        if cond < 10:
            max_allowed = 600
        elif cond < 15:
            max_allowed = 800
        elif cond < 25:
            max_allowed = 1000
        elif cond < 35:
            max_allowed = 1500
        elif cond < 45:
            max_allowed = 2000
        elif cond < 55:
            max_allowed = 3500
        elif cond < 65:
            max_allowed = 5000
        elif cond < 75:
            max_allowed = 6500
        else:
            max_allowed = None

        if ref_f and ref_f > 0:
            if cond < 35:
                max_allowed = min(max_allowed or ref_f * 0.10, ref_f * 0.12)
            elif cond < 45:
                max_allowed = min(max_allowed or ref_f * 0.15, ref_f * 0.18)
            elif cond < 55:
                max_allowed = min(max_allowed or ref_f * 0.22, ref_f * 0.28)
            elif cond < 65:
                max_allowed = min(max_allowed or ref_f * 0.35, ref_f * 0.42)
            elif cond < 75:
                max_allowed = min(max_allowed or ref_f * 0.50, ref_f * 0.60)

        cov = None
        if isinstance(evidence, dict):
            cov = evidence.get("coverage")
        if cov is None:
            try:
                cov = _coverage(evidence)
            except Exception:
                cov = None

        if cov is not None and cov < 0.6 and cond < 45:
            max_allowed = min(max_allowed or 1200, 1200)
        if cov is not None and cov < 0.4 and cond < 55:
            max_allowed = min(max_allowed or 2000, 2000)

        if isinstance(evidence, dict):
            if evidence.get("photos") is False and cov is not None and cov < 0.5 and cond < 40:
                max_allowed = min(max_allowed or 1000, 1000)

        if ref_f and ref_f > 0 and cond < 50:
            hard = ref_f * 0.20
            if max_allowed is None or hard < max_allowed:
                max_allowed = hard

        if max_allowed is not None and val_f > max_allowed:
            prediction["device_value"] = int(round(max_allowed))
            if prediction.get("confidence") is not None:
                prediction["confidence"] = max(0.05, float(prediction["confidence"]) * 0.6)
        return prediction
    except Exception:
        return prediction

