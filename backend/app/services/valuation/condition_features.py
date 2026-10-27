"""Condition features from the questionnaire answers.

=================================================================
WHAT THIS MODULE DOES DIFFERENTLY FROM THE OLD DESIGN
=================================================================

The old `condition.py` produced a single `condition_score` by
subtracting hard-coded points, and `valuation/core.py` then
multiplied the ML price by a grade multiplier. Condition was
therefore a post-hoc percentage, applied outside the model.

Here the questionnaire is TRANSLATED into the individual
numeric features the forest actually consumes:

    device_age_months
    battery_health_pct
    screen_condition_score
    body_condition_score
    camera_condition_score
    functional_test_score
    repair_history_code
    accessories_code

Each mapping is an explicit lookup table in
`ml.feature_schema`. The score is not collapsed into one
number, because a collapsed number throws away exactly the
information the model needs: a phone with a perfect screen and
a dead battery must price differently from a phone with a
cracked screen and a new battery.

`calculate_condition_score` is retained, but ONLY as a
human-readable summary for display. It has no effect on the
predicted value.
"""

from app.core.logger import get_logger
from app.services.valuation.registry import (
    normalize_text,
)
from ml.feature_schema import (
    AGE_MONTHS,
    BATTERY_HEALTH_PCT,
    CONDITION_ANSWER_SCORES,
    FUNCTIONAL_ANSWER_SCORES,
    FUNCTIONAL_COMPONENT_SCORES,
    REPAIR_CODES,
    DEFAULT_CONDITION_FEATURES,
)


logger = get_logger(__name__)


# ============================================================
# ANSWER LOOKUP
#
# The frontend has used several key spellings over time
# ("age" / "device_age" / "purchase_age"), so each concept
# accepts a list of aliases.
# ============================================================

_AGE_KEYS = (
    "age",
    "device_age",
    "purchase_age",
)

_SCREEN_KEYS = (
    "screen",
    "screen_condition",
)

_BODY_KEYS = (
    "body",
    "body_condition",
)

_BATTERY_KEYS = (
    "battery",
    "battery_health",
    "battery_condition",
)

_FUNCTIONALITY_KEYS = (
    "functionality",
    "working_condition",
)

_CHARGER_KEYS = (
    "original_charger",
    "accessories",
    "charger_box",
    "charger",
)

_BOX_KEYS = (
    "original_box",
    "box",
)

_REPAIR_KEYS = (
    "repair_history",
    "repair",
    "repair_status",
)

_CAMERA_KEYS = (
    "camera",
    "camera_condition",
)

_WARRANTY_KEYS = (
    "warranty",
    "warranty_status",
    "warranty_remaining",
)


def _first_answer(answers, keys):
    """First non-empty answer among several accepted keys."""

    for key in keys:

        value = answers.get(key)

        if value not in (None, ""):
            return normalize_text(value)

    return ""


def _lookup(table, answer, default):
    """Look up an answer in a mapping, falling back cleanly."""

    if not answer:
        return default

    if answer in table:
        return table[answer]

    logger.debug(
        "Unrecognized answer '%s'; using default %s",
        answer,
        default,
    )

    return default


# ============================================================
# CONCEPT EXTRACTORS
# ============================================================

def extract_age_months(answers):
    answer = _first_answer(answers, _AGE_KEYS)

    return _lookup(
        AGE_MONTHS,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "device_age_months"
        ],
    )


def extract_battery_health(answers):
    answer = _first_answer(answers, _BATTERY_KEYS)

    return _lookup(
        BATTERY_HEALTH_PCT,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "battery_health_pct"
        ],
    )


def extract_screen_condition(answers):
    answer = _first_answer(answers, _SCREEN_KEYS)

    return _lookup(
        CONDITION_ANSWER_SCORES,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "screen_condition_score"
        ],
    )


def extract_body_condition(answers):
    answer = _first_answer(answers, _BODY_KEYS)

    return _lookup(
        CONDITION_ANSWER_SCORES,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "body_condition_score"
        ],
    )


def extract_camera_condition(answers):
    answer = _first_answer(answers, _CAMERA_KEYS)

    return _lookup(
        CONDITION_ANSWER_SCORES,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "camera_condition_score"
        ],
    )


def extract_repair_code(answers):
    answer = _first_answer(answers, _REPAIR_KEYS)

    return _lookup(
        REPAIR_CODES,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "repair_history_code"
        ],
    )


def extract_accessories_code(answers):
    """0 none, 1 box only, 2 charger only, 3 box + charger."""

    has_box = (
        _first_answer(answers, _BOX_KEYS)
        == "yes"
    )

    has_charger = (
        _first_answer(answers, _CHARGER_KEYS)
        == "yes"
    )

    if has_box and has_charger:
        return 3

    if has_charger:
        return 2

    if has_box:
        return 1

    return 0


def extract_warranty_months(answers):
    """Months of warranty remaining.

    Accepts a numeric string ("6") or a coarse bucket
    ("under 6 months", "6-12 months", "expired").
    """

    answer = _first_answer(answers, _WARRANTY_KEYS)

    if not answer:
        return 0.0

    numeric = answer.replace("months", "").strip()

    try:
        return max(
            0.0,
            min(24.0, float(numeric)),
        )

    except ValueError:
        pass

    buckets = {
        "expired": 0.0,
        "no": 0.0,
        "none": 0.0,
        "under 6 months": 3.0,
        "less than 6 months": 3.0,
        "6-12 months": 9.0,
        "6 to 12 months": 9.0,
        "1 year": 12.0,
        "12 months": 12.0,
        "active": 12.0,
        "valid": 12.0,
    }

    return _lookup(
        buckets,
        answer,
        0.0,
    )


def extract_functional_score(
    answers,
    self_report=None
):
    """Aggregate functional self-test score, 0..100.

    When the full-inspection flow supplied per-component
    self-reports (battery, charging, speaker, buttons,
    connectivity, touchscreen) they are averaged, because they
    are more informative than the single yes/no question.
    Otherwise the single functionality answer is mapped.
    """

    if self_report:

        scores = []

        for key, table in (
            FUNCTIONAL_COMPONENT_SCORES.items()
        ):

            value = self_report.get(key)

            if not value:
                continue

            scores.append(
                _lookup(
                    table,
                    normalize_text(value),
                    80.0,
                )
            )

        if scores:

            return round(
                sum(scores) / len(scores),
                2,
            )

    answer = _first_answer(
        answers,
        _FUNCTIONALITY_KEYS,
    )

    return _lookup(
        FUNCTIONAL_ANSWER_SCORES,
        answer,
        DEFAULT_CONDITION_FEATURES[
            "functional_test_score"
        ],
    )


# ============================================================
# PHASE 2: CONDITION FEATURES
# ============================================================

def condition_features_from_answers(
    answers,
    self_report=None
) -> dict:
    """Translate questionnaire answers into model features.

    Returns only the features the questionnaire can inform.
    Features owned by diagnostics or AI photos are left out and
    filled by their own modules.
    """

    answers = answers or {}

    return {
        "device_age_months": extract_age_months(
            answers
        ),
        "battery_health_pct": extract_battery_health(
            answers
        ),
        "screen_condition_score": (
            extract_screen_condition(answers)
        ),
        "body_condition_score": (
            extract_body_condition(answers)
        ),
        "camera_condition_score": (
            extract_camera_condition(answers)
        ),
        "repair_history_code": extract_repair_code(
            answers
        ),
        "accessories_code": extract_accessories_code(
            answers
        ),
        "warranty_months_remaining": (
            extract_warranty_months(answers)
        ),
        "functional_test_score": (
            extract_functional_score(
                answers,
                self_report=self_report,
            )
        ),
    }


# ============================================================
# DISPLAY-ONLY CONDITION SUMMARY
#
# Kept for the UI so the user still sees a single 0..100
# condition number. It is NOT used to adjust the predicted
# value in any way.
# ============================================================

_DISPLAY_DEDUCTIONS = {
    "age": {
        "less than 6 months": 0,
        "0-6 months": 0,
        "6 to 12 months": 5,
        "6-12 months": 5,
        "1 year": 8,
        "1 to 2 years": 12,
        "1-2 years": 12,
        "2 years": 18,
        "2 to 3 years": 25,
        "2-3 years": 25,
        "3+ years": 32,
        "more than 3 years": 32,
    },
    "screen": {
        "excellent": 0,
        "like new": 0,
        "good": 5,
        "minor scratches": 8,
        "scratched": 12,
        "cracked": 30,
        "broken": 40,
        "display problem": 40,
    },
    "body": {
        "excellent": 0,
        "like new": 0,
        "good": 5,
        "minor scratches": 8,
        "scratches": 10,
        "multiple scratches": 10,
        "dents": 18,
        "minor dents": 18,
        "heavy damage": 30,
        "major damage": 30,
        "broken": 40,
    },
    "battery": {
        "excellent": 0,
        "good": 3,
        "80-100%": 3,
        "70-80%": 8,
        "below 80": 8,
        "below 70%": 15,
        "poor": 15,
        "replaced": 5,
    },
    "functionality": {
        "fully working": 0,
        "everything works": 0,
        "good": 0,
        "yes": 0,
        "minor issues": 10,
        "not sure": 5,
        "some issues": 15,
        "no": 15,
        "major issues": 30,
        "not working": 50,
    },
}


def condition_score_from_features(
    features: dict
) -> float:
    """Derive a display-only 0..100 score from feature values.

    The `/ml/predict` endpoint lets a caller send individual
    condition features (and skip the flat `condition_score`).
    Without this, the reported score would stay at its 100
    default while the features described a scuffed phone, which
    is misleading in the response.

    This is a DISPLAY value only. The predicted value is
    produced by the model from the features themselves, and
    this function never feeds back into it.
    """

    score = 100.0

    weighted = (
        ("screen_condition_score", 2.0),
        ("body_condition_score", 1.5),
        ("camera_condition_score", 0.5),
        ("functional_test_score", 2.0),
        ("battery_health_pct", 1.0),
        ("diagnostic_score", 2.0),
    )

    total_weight = 0.0

    for name, weight in weighted:

        value = features.get(name)

        if value is None:
            continue

        value = max(0.0, min(100.0, float(value)))

        score -= (100.0 - value) / 100.0 * weight * 20.0

        total_weight += weight

    # Flat damage severities, 0 = none ... 3 = severe.
    for name in (
        "scratch_severity",
        "dent_severity",
        "crack_severity",
        "frame_damage_severity",
    ):

        value = features.get(name)

        if value is None:
            continue

        score -= max(0.0, min(3.0, float(value))) * 4.0

    if features.get("repair_history_code"):
        score -= 3.0 * float(
            features["repair_history_code"]
        )

    if not total_weight and not any(
        features.get(name)
        for name, _ in weighted
    ):
        return 100.0

    return round(max(0.0, min(100.0, score)), 2)


def calculate_condition_score(answers) -> int:
    """Display-only 0..100 condition summary.

    Retained verbatim in behaviour from the previous
    implementation so the UI number does not jump around. The
    pipeline deliberately does not feed this into the model.
    """

    answers = answers or {}

    score = 100

    score -= _DISPLAY_DEDUCTIONS["age"].get(
        _first_answer(answers, _AGE_KEYS),
        0,
    )

    score -= _DISPLAY_DEDUCTIONS["screen"].get(
        _first_answer(answers, _SCREEN_KEYS),
        0,
    )

    score -= _DISPLAY_DEDUCTIONS["body"].get(
        _first_answer(answers, _BODY_KEYS),
        0,
    )

    score -= _DISPLAY_DEDUCTIONS["battery"].get(
        _first_answer(answers, _BATTERY_KEYS),
        0,
    )

    score -= _DISPLAY_DEDUCTIONS["functionality"].get(
        _first_answer(answers, _FUNCTIONALITY_KEYS),
        0,
    )

    has_box = (
        _first_answer(answers, _BOX_KEYS) == "yes"
    )

    has_charger = (
        _first_answer(answers, _CHARGER_KEYS) == "yes"
    )

    if has_box and has_charger:
        score += 2
    elif not has_box and not has_charger:
        score -= 3

    repair = _first_answer(answers, _REPAIR_KEYS)

    if repair in (
        "authorized",
        "authorized service",
        "yes authorized service",
    ):
        score -= 5

    elif repair in (
        "third party",
        "third-party service",
        "third party service",
        "yes third party service",
    ):
        score -= 12

    elif repair in ("unknown", "i don't know"):
        score -= 3

    return max(0, min(100, score))


def get_condition_grade(score) -> str:
    """Display-only letter grade for a condition summary."""

    if score >= 90:
        return "A+"

    if score >= 80:
        return "A"

    if score >= 70:
        return "B"

    if score >= 60:
        return "C"

    return "D"