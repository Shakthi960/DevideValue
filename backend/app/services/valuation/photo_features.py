"""AI photo inspection -> numeric model features.

=================================================================
PHOTO RESULTS ARE STRUCTURED FEATURES, NOT A MULTIPLIER
=================================================================

The old design took one AI number (`condition_score`) and
applied a hard-coded linear multiplier:

    100 -> 1.00
      0 -> 0.60

That threw away almost everything Gemini reports. The Gemini
condition analyzer already returns per-defect severities for
scratches, dents, cracks and frame damage, plus a
`visible_damage_score` and a per-view `confidence`. Those are
exactly the columns the valuation model wants.

This module maps them 1:1:

    scratch_severity         <- scratches.severity
    dent_severity            <- dents.severity
    crack_severity           <- cracks.severity
    frame_damage_severity    <- frame_damage.severity
    ai_condition_score       <- 100 - visible_damage_score,
                                averaged across views and
                                weighted by capture quality
    camera_condition_score   <- camera lens damage, when the
                                back view reported it

A view the AI could not analyse contributes nothing rather than
a neutral score, so missing evidence does not silently become
"no damage".

-----------------------------------------------------------------
NOTHING HERE MULTIPLIES A PRICE
-----------------------------------------------------------------

The outputs are feature values. The forest decides what they
are worth.
"""

from app.core.logger import get_logger
from ml.feature_schema import (
    SEVERITY_CODES,
    DEFAULT_CONDITION_FEATURES,
)


logger = get_logger(__name__)


# Severity ordering used to derive an overall AI condition score
# when a per-view visible_damage_score is unavailable.
_SEVERITY_DAMAGE_POINTS = {
    0: 0.0,
    1: 8.0,
    2: 22.0,
    3: 45.0,
}

# How much each damage class contributes to the fallback AI
# condition score. Cracks dominate, as they do in the market.
_SEVERITY_WEIGHTS = {
    "scratch": 0.15,
    "dent": 0.20,
    "crack": 0.40,
    "frame": 0.25,
}


def severity_to_code(value):
    """Map a Gemini severity string onto 0..3.

    Unknown or missing values return None so the caller can tell
    "no damage reported" apart from "not analysed".
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return max(0, min(3, int(value)))

    text = str(value).strip().lower()

    if not text:
        return None

    if text in SEVERITY_CODES:
        return SEVERITY_CODES[text]

    logger.debug(
        "Unrecognized severity '%s'", text
    )

    return None


def _damage_block(condition, key):
    """Extract {detected, severity} from a Gemini damage block."""

    block = condition.get(key)

    if not isinstance(block, dict):
        return None, None

    severity = severity_to_code(
        block.get("severity")
    )

    detected = block.get("detected")

    if isinstance(detected, str):
        detected = detected.strip().lower() == "true"

    # A detected defect with no severity stated is at least
    # minor, never "none".
    if detected and severity is None:
        severity = 1

    if severity is None and detected is False:
        severity = 0

    return severity, detected


def _visible_damage(condition):
    value = condition.get("visible_damage_score")

    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))

    return None


def _camera_damage(condition):
    """Camera lens damage, when the analyzer mentioned it."""

    for key in (
        "camera_condition",
        "camera",
    ):
        block = condition.get(key)

        if isinstance(block, dict):
            severity = severity_to_code(
                block.get("severity")
            )
            if severity is not None:
                return severity

    score = condition.get("camera_score")

    if isinstance(score, (int, float)):
        return severity_to_code(
            max(0, min(3, round((100 - float(score)) / 34)))
        )

    return None


def collect_photo_features(
    analysis,
    photo_types=None
) -> dict:
    """Turn an `analyze_photos` result into condition features.

    analysis:
        The dict returned by
        app.routes.photo_analysis.analyze_photos, i.e.
        {"photos": [{"photo_type", "analysis"}], ...}.

        A raw list of per-photo results is also accepted.

    Returns:
        The photo-derived condition features plus two extra keys
        used only for reporting:
          "ai_views_analyzed": int
          "ai_capture_factor": float
    """

    photos = _normalize_photos(analysis, photo_types)

    # `analyze_photos` nests the per-photo payload under an
    # "analysis" key. Unwrap it here so callers can pass the
    # endpoint response straight through.
    normalized = []

    for item in photos:

        if not isinstance(item, dict):
            continue

        payload = item.get("analysis")

        if not isinstance(payload, dict):
            payload = item

        normalized.append(
            {
                "photo_type": item.get("photo_type"),
                "physical_condition": payload.get(
                    "physical_condition"
                ),
                "phone_detection": payload.get(
                    "phone_detection"
                ) or {},
                "quality_score": payload.get(
                    "quality_score"
                ),
            }
        )

    photos = normalized

    severities = {
        "scratch": [],
        "dent": [],
        "crack": [],
        "frame": [],
    }

    camera_severities = []

    damage_scores = []

    confidences = []

    capture_factors = []

    analyzed_views = 0

    for item in photos:

        condition = item.get("physical_condition")

        if not isinstance(condition, dict):
            continue

        analyzed_views += 1

        for target, key in (
            ("scratch", "scratches"),
            ("dent", "dents"),
            ("crack", "cracks"),
            ("frame", "frame_damage"),
        ):
            severity, _ = _damage_block(
                condition,
                key,
            )

            if severity is not None:
                severities[target].append(severity)

        camera = _camera_damage(condition)

        if camera is not None:
            camera_severities.append(camera)

        damage = _visible_damage(condition)

        if damage is not None:
            damage_scores.append(damage)

        confidence = condition.get("confidence")

        if isinstance(confidence, (int, float)):
            confidences.append(float(confidence))

        detection = item.get("phone_detection") or {}

        detected = bool(
            detection.get("detected", False)
        )

        quality = item.get("quality_score")

        quality_ratio = (
            max(0.0, min(100.0, float(quality))) / 100.0
            if isinstance(quality, (int, float))
            else 0.5
        )

        capture_factors.append(
            quality_ratio * (1.0 if detected else 0.4)
        )

    defaults = DEFAULT_CONDITION_FEATURES

    features = {}

    for target, column in (
        ("scratch", "scratch_severity"),
        ("dent", "dent_severity"),
        ("crack", "crack_severity"),
        ("frame", "frame_damage_severity"),
    ):
        values = severities[target]

        # Worst severity across views, not the average: damage
        # is not diluted by the other five angles.
        features[column] = (
            float(max(values))
            if values
            else defaults[column]
        )

    if camera_severities:
        features["camera_condition_score"] = (
            100.0 - (max(camera_severities) * 20.0)
        )

    capture_factor = (
        sum(capture_factors) / len(capture_factors)
        if capture_factors
        else 0.5
    )

    features["ai_condition_score"] = _ai_condition_score(
        damage_scores,
        severities,
        capture_factor,
    )

    features["ai_views_analyzed"] = analyzed_views

    features["ai_capture_factor"] = round(
        capture_factor,
        3,
    )

    features["ai_confidence"] = (
        round(
            sum(confidences) / len(confidences),
            3,
        )
        if confidences
        else None
    )

    return features


def _ai_condition_score(
    damage_scores,
    severities,
    capture_factor
):
    """Aggregate AI physical condition, 0..100.

    Primary path: 100 - mean visible_damage_score.

    Fallback path (when Gemini reported severities but no
    numeric damage score): build a damage estimate from the
    weighted severities.

    In both paths the score is scaled by capture reliability, so
    a phone that was barely photographed yields a lower (less
    trustworthy) condition reading rather than a falsely
    optimistic one.
    """

    if damage_scores:

        average_damage = (
            sum(damage_scores) / len(damage_scores)
        )

        base = 100.0 - average_damage

    else:

        total_weight = 0.0

        weighted = 0.0

        for target, weight in (
            _SEVERITY_WEIGHTS.items()
        ):
            values = severities.get(target) or []

            if not values:
                continue

            worst = max(values)

            weighted += (
                worst
                * _SEVERITY_DAMAGE_POINTS[worst]
                * weight
            )

            total_weight += weight

        if total_weight == 0:
            return DEFAULT_CONDITION_FEATURES[
                "ai_condition_score"
            ]

        base = 100.0 - (
            weighted / total_weight
        )

    reliability = 0.4 + 0.6 * capture_factor

    return round(
        max(0.0, min(100.0, base * reliability)),
        2,
    )


def _normalize_photos(analysis, photo_types):
    """Accept either the analyze_photos dict or a plain list."""

    if analysis is None:
        return []

    if isinstance(analysis, list):
        return analysis

    photos = analysis.get("photos")

    if not isinstance(photos, list):
        return []

    if photo_types:

        wanted = {
            str(item).lower()
            for item in photo_types
        }

        photos = [
            item
            for item in photos
            if str(
                item.get("photo_type", "")
            ).lower() in wanted
        ]

    return photos