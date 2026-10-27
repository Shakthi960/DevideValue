"""Training-frame builder for the DEVICE VALUE model.

=================================================================
IMPORTANT / HONEST STATEMENT ABOUT THE TRAINING LABELS
=================================================================

The only committed dataset is `data/smartphones.csv`: ~758 rows
of device SPECIFICATIONS plus a `price_inr` column that
represents a MARKET / LISTING price. It contains:

  - no device age
  - no battery health
  - no physical condition
  - no diagnostic results
  - no repair history

So it cannot, on its own, teach a model how condition moves
price. To train a model that ACCEPTS condition features as
inputs we need rows where those features vary and the target
reflects them.

What this module does
---------------------
It expands each specification row into several synthetic
"condition scenarios" and derives each scenario's label from an
EXPLICIT, DOCUMENTED depreciation function of that scenario's
condition features.

This means:

  * The specification half of the model is learned from real
    data (real prices, real specs).
  * The condition half of the model is learned from a
    TRANSPARENT depreciation prior, not from observed
    second-hand transactions.

Consequences, stated plainly
----------------------------
  - This is NOT a validated second-hand price model.
  - The depreciation coefficients below are documented
    assumptions chosen to match common Indian used-phone
    market behaviour, not fitted values.
  - The model is real (a trained Random Forest that actually
    predicts from its input features). The LABELS are
    partially assumed. That is the honest description.

Replacing this with real data
-----------------------------
`load_training_frame()` is the single seam. If a genuine
used-phone transaction dataset becomes available, implement
`_load_real_used_dataset()` and return it instead. Nothing
downstream (training, inference, API) changes, because the
only contract is:

    a DataFrame containing every column in
    ml.feature_schema.FEATURES, plus the label column
    TARGET_COLUMN.

See TARGET_COLUMN below.
"""

import os

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from ml.feature_schema import (
    CONDITION_FEATURES as CONDITION_FEATURE_COLUMNS,
    FEATURES,
    validate_feature_contract,
)


logger = get_logger(__name__)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

SPEC_DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "smartphones.csv",
)

# Optional path to a real used-phone dataset. When this file
# exists it is preferred over synthetic scenario expansion.
#
# Expected columns: every column in ml.feature_schema.FEATURES
# plus `device_value_inr`. See README for the schema.
REAL_USED_DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "used_phones_real.csv",
)


# ============================================================
# LABEL
# ============================================================

# The regression target. One value in rupees. This is the whole
# point of the redesign: a single number, not a resale/exchange
# pair.
TARGET_COLUMN = "device_value_inr"


# ============================================================
# TRAINING SCENARIO SHAPES
# ============================================================

# Each scenario is a plausible, self-consistent used-phone
# profile: a coherent combination of age, wear, cosmetics,
# test results, repair history and bundle contents.
#
# The mix is deliberately weighted toward "good" units because
# that is roughly how phones reach a resale channel, while still
# spanning the full range so the model learns the shape of the
# curve rather than a single operating point.
#
# Fields map onto CONDITION FEATURES:
#   age_months, battery, screen, body, camera,
#   scratch, dent, crack, frame,
#   functional, diagnostics, failed, camera_failed,
#   mic_failed, touch_failed, sensor_failed, conn_failed,
#   repair, accessories, warranty, ai_score
TRAINING_SCENARIOS = [
    {
        "label": "new_unopened",
        "weight": 6.0,
        "age_months": 2.0,
        "battery": 100.0,
        "screen": 99.0,
        "body": 99.0,
        "camera": 99.0,
        "scratch": 0,
        "dent": 0,
        "crack": 0,
        "frame": 0,
        "functional": 100.0,
        "diagnostics": 100.0,
        "failed": 0,
        "camera_failed": 0,
        "mic_failed": 0,
        "touch_failed": 0,
        "sensor_failed": 0,
        "conn_failed": 0,
        "repair": 0,
        "accessories": 3,
        "warranty": 11,
        "ai_score": 97.0,
    },
    {
        "label": "excellent_light_use",
        "weight": 14.0,
        "age_months": 8.0,
        "battery": 96.0,
        "screen": 95.0,
        "body": 92.0,
        "camera": 96.0,
        "scratch": 0,
        "dent": 0,
        "crack": 0,
        "frame": 0,
        "functional": 96.0,
        "diagnostics": 100.0,
        "failed": 0,
        "camera_failed": 0,
        "mic_failed": 0,
        "touch_failed": 0,
        "sensor_failed": 0,
        "conn_failed": 0,
        "repair": 0,
        "accessories": 3,
        "warranty": 8,
        "ai_score": 93.0,
    },
    {
        "label": "good_typical_used",
        "weight": 22.0,
        "age_months": 16.0,
        "battery": 90.0,
        "screen": 88.0,
        "body": 82.0,
        "camera": 90.0,
        "scratch": 1,
        "dent": 0,
        "crack": 0,
        "frame": 0,
        "functional": 88.0,
        "diagnostics": 95.0,
        "failed": 0,
        "camera_failed": 0,
        "mic_failed": 0,
        "touch_failed": 0,
        "sensor_failed": 0,
        "conn_failed": 0,
        "repair": 0,
        "accessories": 2,
        "warranty": 3,
        "ai_score": 86.0,
    },
    {
        "label": "fair_visible_wear",
        "weight": 20.0,
        "age_months": 26.0,
        "battery": 82.0,
        "screen": 74.0,
        "body": 62.0,
        "camera": 82.0,
        "scratch": 2,
        "dent": 1,
        "crack": 0,
        "frame": 1,
        "functional": 74.0,
        "diagnostics": 88.0,
        "failed": 1,
        "camera_failed": 0,
        "mic_failed": 1,
        "touch_failed": 0,
        "sensor_failed": 0,
        "conn_failed": 0,
        "repair": 0,
        "accessories": 1,
        "warranty": 0,
        "ai_score": 70.0,
    },
    {
        "label": "poor_damaged",
        "weight": 14.0,
        "age_months": 38.0,
        "battery": 72.0,
        "screen": 45.0,
        "body": 35.0,
        "camera": 60.0,
        "scratch": 3,
        "dent": 2,
        "crack": 1,
        "frame": 2,
        "functional": 55.0,
        "diagnostics": 70.0,
        "failed": 2,
        "camera_failed": 1,
        "mic_failed": 0,
        "touch_failed": 1,
        "sensor_failed": 0,
        "conn_failed": 1,
        "repair": 1,
        "accessories": 0,
        "warranty": 0,
        "ai_score": 45.0,
    },
    {
        "label": "very_poor_cracked",
        "weight": 8.0,
        "age_months": 52.0,
        "battery": 62.0,
        "screen": 18.0,
        "body": 15.0,
        "camera": 35.0,
        "scratch": 3,
        "dent": 3,
        "crack": 3,
        "frame": 3,
        "functional": 30.0,
        "diagnostics": 45.0,
        "failed": 4,
        "camera_failed": 1,
        "mic_failed": 1,
        "touch_failed": 1,
        "sensor_failed": 1,
        "conn_failed": 1,
        "repair": 2,
        "accessories": 0,
        "warranty": 0,
        "ai_score": 18.0,
    },
]


# ============================================================
# COUNTERFACTUAL PROFILES
#
# The archetypes above are coherent bundles: a phone with a
# cracked screen also has a beaten-up body and a tired battery.
# That realism has a cost. In the training frame every damage
# flag is perfectly collinear with the other condition features,
# so a tree can attribute the entire condition effect to
# `screen_condition_score` (or to anything else) and the
# isolated flags end up with no measurable effect at all.
#
# Measured before this fix: raising `crack_severity` from 0 to
# 3 changed the prediction by zero rupees, and `accessories_code`
# was flat too.
#
# These profiles exist purely to break that collinearity. Each
# one starts from the same healthy reference unit and changes
# exactly ONE dimension, so the label-to-feature relationship is
# identifiable and the model can price a crack separately from
# a scratch. They are not meant to look like typical stock; they
# are a controlled experiment inside the training set.
# ============================================================

_REFERENCE_UNIT = {
    "age_months": 14.0,
    "battery": 94.0,
    "screen": 94.0,
    "body": 92.0,
    "camera": 94.0,
    "scratch": 0,
    "dent": 0,
    "crack": 0,
    "frame": 0,
    "functional": 96.0,
    "diagnostics": 100.0,
    "failed": 0,
    "camera_failed": 0,
    "mic_failed": 0,
    "touch_failed": 0,
    "sensor_failed": 0,
    "conn_failed": 0,
    "repair": 0,
    "accessories": 3,
    "warranty": 8,
    "ai_score": 92.0,
}

# (field, value) pairs swept one at a time. Each sweep level
# gets its own weight so common, mild states dominate and rare,
# severe states stay present but rare.
_ISOLATED_SWEEPS = (
    ("scratch", (1, 2, 3), 1.0),
    ("dent", (1, 2, 3), 1.0),
    ("crack", (1, 2, 3), 1.0),
    ("frame", (1, 2, 3), 1.0),
    ("battery", (88.0, 80.0, 70.0, 60.0), 1.0),
    ("screen", (85.0, 70.0, 45.0, 25.0), 1.0),
    ("body", (85.0, 70.0, 45.0, 25.0), 1.0),
    ("camera", (85.0, 70.0, 45.0), 1.0),
    ("functional", (88.0, 70.0, 50.0), 1.0),
    ("diagnostics", (85.0, 65.0, 45.0), 1.0),
    ("failed", (1, 2, 3), 1.0),
    ("age_months", (2.0, 6.0, 30.0, 42.0, 54.0), 1.5),
    ("repair", (1, 2), 1.0),
    ("accessories", (0, 1, 2), 1.0),
    ("warranty", (0, 3, 18), 1.0),
    ("ai_score", (85.0, 70.0, 50.0), 1.0),
)

# Which individual failure flag to trip when sweeping the
# diagnostics score, so a lowered diagnostic score always has a
# matching failed-sensor feature.
_DIAGNOSTIC_FLAG_FOR_INDEX = (
    "touch_failed",
    "camera_failed",
    "conn_failed",
    "sensor_failed",
)


def _isolated_scenarios() -> list:
    """Build the one-dimension-at-a-time counterfactual set."""

    scenarios = []

    scenarios.append({
        "label": "iso_reference",
        "weight": 2.0,
        **_REFERENCE_UNIT,
    })

    for field, levels, weight in _ISOLATED_SWEEPS:

        for level in levels:

            scenario = {
                "label": (
                    f"iso_{field}_{level}"
                ),
                "weight": weight,
                **_REFERENCE_UNIT,
            }

            scenario[field] = level

            if field == "diagnostics":

                index = min(
                    len(_DIAGNOSTIC_FLAG_FOR_INDEX) - 1,
                    levels.index(level),
                )

                scenario[
                    _DIAGNOSTIC_FLAG_FOR_INDEX[index]
                ] = 1

                scenario["failed"] = 1

            if field == "functional":

                scenario["failed"] = 1
                scenario["touch_failed"] = 1

            scenarios.append(scenario)

    # One row per tripped sensor, again in isolation, so the
    # five individual failure flags are separately identifiable.
    for flag in _DIAGNOSTIC_FLAG_FOR_INDEX:

        scenario = {
            "label": f"iso_{flag}",
            "weight": 1.0,
            **_REFERENCE_UNIT,
        }

        scenario[flag] = 1
        scenario["failed"] = 1
        scenario["diagnostics"] = 80.0

        scenarios.append(scenario)

    return scenarios


# Every profile the expansion is built from: the realistic
# archetypes plus the counterfactual sweeps.
ALL_SCENARIOS = TRAINING_SCENARIOS + _isolated_scenarios()

# Fixed seed so training is reproducible.
TRAINING_SEED = 42

# Jittered variants per weight-unit. The counterfactual sweeps
# already spread each condition dimension across its levels, so
# extra jitter buys little resolution for a lot of training time.
# At 0 the set is 147 profiles x 758 devices = 111k rows, which
# keeps every device and every condition state.
SCENARIO_VARIANTS_PER_DEVICE = 0


# ============================================================
# DEPRECIATION PRIOR
#
# DOCUMENTED ASSUMPTIONS, NOT FITTED PARAMETERS.
#
# Each factor maps a condition signal to a multiplier on the
# device's reference price. Factors are multiplicative so a
# severe problem in one area cannot be cancelled out by a good
# score elsewhere. Every constant below is an explicit market
# assumption that a real used-transaction dataset should
# eventually replace.
# ============================================================

# Fraction of the reference price retained at 12 months,
# before any condition adjustment. Android phones in the
# Indian market are commonly assumed to lose roughly 20-25% of
# retail value in year one.
AGE_12M_RETENTION = 0.78

# Fraction retained at 24 months (compounding on the above).
AGE_24M_RETENTION = 0.60

# Extra retention available while original warranty is live.
# Capped so warranty alone can never dominate the price.
WARRANTY_UPLIFT_MAX = 0.05

# Per-month warranty uplift before the cap.
WARRANTY_UPLIFT_PER_MONTH = 0.004

# Accessory bundle uplift (box + charger adds resale appeal).
ACCESSORIES_UPLIFT = {
    0: -0.03,
    1: 0.0,
    2: 0.02,
    3: 0.04,
}

# Repair history penalty.
REPAIR_PENALTY = {
    0: 0.0,
    1: -0.05,
    2: -0.12,
    3: -0.04,
}

# Battery health multiplier. Interpolated between these
# anchors; below 60% the penalty steepens because battery
# replacement cost is usually passed to the buyer.
BATTERY_ANCHORS = [
    (100.0, 1.00),
    (90.0, 0.97),
    (80.0, 0.93),
    (70.0, 0.88),
    (60.0, 0.80),
    (40.0, 0.65),
]

# Physical-damage severity penalty, per feature. A crack is
# worth far more than a scratch, so its coefficient is larger.
DAMAGE_PENALTIES = {
    "scratch": {0: 0.0, 1: -0.02, 2: -0.05, 3: -0.09},
    "dent": {0: 0.0, 1: -0.03, 2: -0.07, 3: -0.12},
    "crack": {0: 0.0, 1: -0.22, 2: -0.34, 3: -0.48},
    "frame": {0: 0.0, 1: -0.03, 2: -0.08, 3: -0.14},
}

# Weight of each 0..100 cosmetic score on the price.
# A cracked screen dominates; the camera matters less because
# it is the most commonly replaced module.
COSMETIC_WEIGHTS = {
    "screen": 0.55,
    "body": 0.30,
    "camera": 0.15,
}

# Test-result scoring. These produce a 0..1 sub-score, not a
# multiplier, because combining five independent multipliers
# multiplicatively drives almost every damaged phone into the
# same floor and destroys the model's ability to tell a
# cosmetically worn phone from a shattered one.
FUNCTIONAL_FLOOR = 0.30
DIAGNOSTIC_FLOOR = 0.45

# FUNCTIONAL_FLOOR / DIAGNOSTIC_FLOOR are retained as documented
# reference points for how much a failing phone loses, but the
# active scoring path uses weighted sub-scores (see
# condition_index) rather than chained multipliers.

# Penalty per failed individual hardware test, expressed in
# functional-score points before blending.
PER_FAILED_TEST_POINTS = 5.0

# Points deducted from the functional sub-score when a specific
# module failed.
MODULE_FAILURE_POINTS = {
    "camera_failed": 22.0,
    "mic_failed": 8.0,
    "touch_failed": 26.0,
    "sensor_failed": 10.0,
    "conn_failed": 14.0,
}

# How the four condition sub-scores are blended into one
# condition index. Physical damage dominates because it is
# what buyers discount hardest, but functioning hardware and
# battery wear both carry real weight.
CONDITION_INDEX_WEIGHTS = {
    "battery": 0.25,
    "cosmetic": 0.25,
    "damage": 0.30,
    "function": 0.20,
}

# Floor of the condition factor. Even a shattered, non-working
# phone retains residual value as a parts donor, so the factor
# never reaches zero.
CONDITION_FACTOR_FLOOR = 0.30

# Overall floor for the depreciation factor.
MIN_DEPRECIATION_FACTOR = 0.05

# Ranges used to normalize each sub-multiplier into 0..1.
_DAMAGE_SUB_SCORE_RANGE = (0.30, 1.00)
_TEST_SUB_SCORE_RANGE = (0.20, 1.00)
_COSMETIC_SUB_SCORE_RANGE = (0.45, 1.00)


# ============================================================
# FACTOR HELPERS
# ============================================================

def _age_retention(age_months: float) -> float:
    """Piecewise-linear retention curve by ownership age.

    Linear between the 12 and 24 month anchors, then continued
    at the same slope so very old devices keep losing value
    instead of flattening out at a floor.
    """

    if age_months <= 12:
        ratio = age_months / 12.0

        return 1.0 - (
            ratio * (1.0 - AGE_12M_RETENTION)
        )

    if age_months <= 24:
        span = (age_months - 12.0) / 12.0

        return AGE_12M_RETENTION + (
            span * (AGE_24M_RETENTION - AGE_12M_RETENTION)
        )

    extra_years = (age_months - 24.0) / 12.0

    slope = (
        (AGE_24M_RETENTION - AGE_12M_RETENTION)
    )

    retention = AGE_24M_RETENTION + (
        extra_years * slope
    )

    return max(0.12, retention)


def _interpolate_anchors(
    anchors,
    value
):
    """Piecewise-linear lookup over (x, y) anchor pairs.

    Handles anchors sorted in either direction, so callers do
    not have to care whether the table runs high-to-low
    (battery health) or low-to-high.
    """

    first_x, first_y = anchors[0]
    last_x, last_y = anchors[-1]

    if first_x <= last_x:
        ordered = anchors

    else:
        ordered = list(reversed(anchors))

    low_x, low_y = ordered[0]
    high_x, high_y = ordered[-1]

    if value <= low_x:
        return low_y

    if value >= high_x:
        return high_y

    for (x0, y0), (x1, y1) in zip(
        ordered,
        ordered[1:]
    ):
        if x0 <= value <= x1:

            if x1 == x0:
                return y1

            ratio = (value - x0) / (x1 - x0)

            return y0 + (ratio * (y1 - y0))

    return high_y


def _normalize(value, low, high):
    """Map a value from [low, high] onto 0..1, clamped."""

    if high <= low:
        return 0.0

    return max(
        0.0,
        min(1.0, (value - low) / (high - low)),
    )


def _battery_sub_score(battery_health_pct: float) -> float:
    """Battery wear as a 0..1 sub-score (1 = new cell)."""

    value = max(0.0, min(100.0, battery_health_pct))

    factor = _interpolate_anchors(
        BATTERY_ANCHORS,
        value
    )

    return _normalize(
        factor,
        BATTERY_ANCHORS[-1][1],
        BATTERY_ANCHORS[0][1],
    )


def _cosmetic_sub_score(
    screen,
    body,
    camera
) -> float:
    """Weighted cosmetic blend as a 0..1 sub-score."""

    weighted = (
        screen * COSMETIC_WEIGHTS["screen"]
        + body * COSMETIC_WEIGHTS["body"]
        + camera * COSMETIC_WEIGHTS["camera"]
    )

    blended = weighted / sum(
        COSMETIC_WEIGHTS.values()
    )

    # 100 -> 1.0, 0 -> 0.0
    return max(0.0, min(1.0, blended / 100.0))


def _damage_sub_score(scenario: dict) -> float:
    """Physical damage as a 0..1 sub-score (1 = no damage).

    Severities are combined additively (not multiplicatively)
    and normalized against the worst combined case, so a phone
    with one severe crack stays distinguishable from one that
    is damaged in every category.
    """

    total_penalty = 0.0

    for key, penalties in DAMAGE_PENALTIES.items():

        severity = max(
            0,
            min(3, int(scenario.get(key, 0))),
        )

        total_penalty += abs(penalties[severity])

    max_penalty = sum(
        abs(penalties[3])
        for penalties in DAMAGE_PENALTIES.values()
    )

    return max(
        0.0,
        1.0 - (total_penalty / max_penalty),
    )


def _function_sub_score(
    functional,
    diagnostics,
    failed,
    flags
) -> float:
    """Functionality as a 0..1 sub-score (1 = everything passes).

    The two aggregate scores are combined as an average, then
    reduced for each failed test and each failed module.
    """

    functional_ratio = (
        max(0.0, min(100.0, functional)) / 100.0
    )

    diagnostics_ratio = (
        max(0.0, min(100.0, diagnostics)) / 100.0
    )

    blended = (
        (functional_ratio + diagnostics_ratio) / 2.0
    )

    # Each failed test costs a share of the remaining score.
    blended -= (
        (PER_FAILED_TEST_POINTS / 100.0)
        * int(failed)
        * blended
    )

    for flag, points in (
        MODULE_FAILURE_POINTS.items()
    ):
        if int(flags.get(flag, 0)):
            blended -= points / 100.0

    return max(0.0, min(1.0, blended))


def condition_index(scenario: dict) -> float:
    """Blend the four condition sub-scores into one 0..1 index.

    This is a WEIGHTED AVERAGE, not a product. Multiplying
    independent factors drove every badly damaged phone to the
    same floor value, which removed the model's ability to
    distinguish a cosmetically worn phone from a shattered one.
    """

    scores = {
        "battery": _battery_sub_score(
            scenario["battery"]
        ),
        "cosmetic": _cosmetic_sub_score(
            scenario["screen"],
            scenario["body"],
            scenario["camera"],
        ),
        "damage": _damage_sub_score(scenario),
        "function": _function_sub_score(
            scenario["functional"],
            scenario["diagnostics"],
            scenario["failed"],
            {
                "camera_failed": scenario[
                    "camera_failed"
                ],
                "mic_failed": scenario["mic_failed"],
                "touch_failed": scenario[
                    "touch_failed"
                ],
                "sensor_failed": scenario[
                    "sensor_failed"
                ],
                "conn_failed": scenario["conn_failed"],
            },
        ),
    }

    total = sum(
        weight * scores[name]
        for name, weight in (
            CONDITION_INDEX_WEIGHTS.items()
        )
    )

    return max(
        0.0,
        min(1.0, total / sum(
            CONDITION_INDEX_WEIGHTS.values()
        )),
    )


def depreciation_factor(scenario: dict) -> float:
    """Full value factor for one condition scenario.

    Structure:

        core       = age_retention * condition_factor
        adjustment = 1 + repair_penalty
                        + accessories_uplift
                        + warranty_uplift
        factor     = core * adjustment

    Age and condition multiply: they are largely independent
    axes of depreciation.

    Repair, bundle contents and warranty multiply as a single
    relative adjustment. They were previously added directly
    to the core product, which pushed heavily damaged phones
    below zero and forced them all onto the same floor value -
    destroying the model's ability to tell a worn phone from a
    shattered one. As a relative adjustment they scale the
    price without ever overwhelming it.
    """

    index = condition_index(scenario)

    condition_factor = (
        CONDITION_FACTOR_FLOOR
        + (1.0 - CONDITION_FACTOR_FLOOR) * index
    )

    core = (
        _age_retention(float(scenario["age_months"]))
        * condition_factor
    )

    adjustment = 1.0

    adjustment += REPAIR_PENALTY.get(
        int(scenario["repair"]),
        0.0,
    )

    adjustment += ACCESSORIES_UPLIFT.get(
        int(scenario["accessories"]),
        0.0,
    )

    adjustment += min(
        WARRANTY_UPLIFT_MAX,
        float(scenario["warranty"])
        * WARRANTY_UPLIFT_PER_MONTH,
    )

    adjustment = max(0.40, adjustment)

    return max(
        MIN_DEPRECIATION_FACTOR,
        core * adjustment,
    )


# ============================================================
# FRAME ASSEMBLY
# ============================================================

def _scenario_row(scenario: dict) -> dict:
    """Map a scenario dict onto CONDITION FEATURE names."""

    return {
        "device_age_months": float(
            scenario["age_months"]
        ),
        "battery_health_pct": float(
            scenario["battery"]
        ),
        "screen_condition_score": float(
            scenario["screen"]
        ),
        "body_condition_score": float(
            scenario["body"]
        ),
        "camera_condition_score": float(
            scenario["camera"]
        ),
        "scratch_severity": float(
            scenario["scratch"]
        ),
        "dent_severity": float(scenario["dent"]),
        "crack_severity": float(scenario["crack"]),
        "frame_damage_severity": float(
            scenario["frame"]
        ),
        "functional_test_score": float(
            scenario["functional"]
        ),
        "diagnostic_score": float(
            scenario["diagnostics"]
        ),
        "diagnostics_failed_count": float(
            scenario["failed"]
        ),
        "diagnostic_camera_failed": float(
            scenario["camera_failed"]
        ),
        "diagnostic_microphone_failed": float(
            scenario["mic_failed"]
        ),
        "diagnostic_touch_failed": float(
            scenario["touch_failed"]
        ),
        "diagnostic_sensor_failed": float(
            scenario["sensor_failed"]
        ),
        "diagnostic_connectivity_failed": float(
            scenario["conn_failed"]
        ),
        "repair_history_code": float(
            scenario["repair"]
        ),
        "accessories_code": float(
            scenario["accessories"]
        ),
        "warranty_months_remaining": float(
            scenario["warranty"]
        ),
        "ai_condition_score": float(
            scenario["ai_score"]
        ),
    }


def _load_spec_dataset():
    frame = pd.read_csv(SPEC_DATASET_PATH)

    logger.info(
        "Loaded specification dataset: %d rows from %s",
        len(frame),
        SPEC_DATASET_PATH,
    )

    return frame


def _jitter_scenario(
    scenario: dict,
    rng
) -> dict:
    """Perturb one scenario archetype into a nearby variant.

    Without this the training data contains only six fixed
    condition points per device. A tree model can only predict
    those exact points, so a real inspection that lands between
    two archetypes (a 30-month-old phone with one cracked
    corner) falls back to whatever the nearest archetype says.
    The result is a model that barely responds to small
    condition changes.

    Jittering produces a continuum of nearby profiles so the
    forest can interpolate between archetypes. The seed is
    fixed, so training stays reproducible.

    Only continuous quantities are jittered. Severity codes stay
    integral, because a fractional crack severity has no
    meaning and would teach the model that "severity 1.5"
    exists.
    """

    variant = dict(scenario)

    # Age: +/- 35% of the archetype's age.
    variant["age_months"] = max(
        1.0,
        float(scenario["age_months"])
        * float(rng.uniform(0.65, 1.35)),
    )

    # Battery: +/- 5 percentage points.
    variant["battery"] = float(
        np.clip(
            float(scenario["battery"])
            + rng.uniform(-5.0, 4.0),
            30.0,
            100.0,
        )
    )

    # Cosmetic scores: +/- 10 points.
    for key in ("screen", "body", "camera"):

        variant[key] = float(
            np.clip(
                float(scenario[key])
                + rng.uniform(-10.0, 8.0),
                0.0,
                100.0,
            )
        )

    # Test scores: +/- 10 points.
    for key in ("functional", "diagnostics"):

        variant[key] = float(
            np.clip(
                float(scenario[key])
                + rng.uniform(-10.0, 6.0),
                0.0,
                100.0,
            )
        )

    # AI score: +/- 12 points, kept below the cosine damage it
    # implies is measured against.
    variant["ai_score"] = float(
        np.clip(
            float(scenario["ai_score"])
            + rng.uniform(-12.0, 8.0),
            0.0,
            100.0,
        )
    )

    # Severities: occasionally nudged one step, with a low
    # probability so archetypes remain dominant.
    for key in ("scratch", "dent", "crack", "frame"):

        if rng.random() < 0.18:

            delta = int(
                rng.choice([-1, 1])
            )

            variant[key] = int(
                np.clip(
                    int(scenario[key]) + delta,
                    0,
                    3,
                )
            )

    # Repair: mostly unchanged.
    if rng.random() < 0.15:
        variant["repair"] = int(
            rng.choice([0, 0, 0, 1, 2])
        )

    # Accessories: mostly unchanged.
    if rng.random() < 0.20:
        variant["accessories"] = int(
            rng.choice([0, 1, 2, 3])
        )

    # Warranty decays with age.
    variant["warranty"] = int(
        np.clip(
            int(round(
                float(scenario["warranty"])
                * rng.uniform(0.3, 1.0)
            )),
            0,
            24,
        )
    )

    return variant


def _scenario_variants(
    scenario: dict,
    variants_per_device
):
    """Yield the archetype plus its jittered variants."""

    # `hash()` is salted per process for strings, so an
    # enumerate index is used instead to keep the seed stable
    # across runs.
    seed_offset = (
        TRAINING_SEED
        + ALL_SCENARIOS.index(scenario) * 977
    )

    rng = np.random.default_rng(seed_offset)

    yield scenario

    for _ in range(variants_per_device):
        yield _jitter_scenario(scenario, rng)


def _build_variant_table(
    variants_per_device=SCENARIO_VARIANTS_PER_DEVICE
) -> pd.DataFrame:
    """Flatten every archetype and jittered variant into one frame.

    Returns a frame with one row per condition profile, carrying
    the CONDITION FEATURE columns, the label multiplier and the
    archetype label. No specification columns are included.

    Doing this once, up front, keeps the expansion below to a
    single vectorised repeat instead of copying the 758-row
    specification frame hundreds of times.
    """

    rows = []

    for scenario in ALL_SCENARIOS:

        # `weight` says how common this profile is; the variant
        # count says how finely it is spread. They are separate
        # concerns and used to be multiplied together, which
        # meant `variants_per_device=0` silently erased every
        # weight and collapsed the whole set to one row per
        # scenario.
        repeats = max(
            1,
            int(round(scenario["weight"])),
        )

        row_count = repeats * (
            1 + max(0, variants_per_device)
        )

        for variant in _scenario_variants(
            scenario,
            row_count - 1,
        ):
            row = _scenario_row(variant)

            row["scenario"] = scenario["label"]

            # The depreciation prior is defined over the
            # scenario's own keys (age_months, crack, repair,
            # ...), not over the renamed feature columns.
            row["_factor"] = depreciation_factor(
                variant
            )

            rows.append(row)

    return pd.DataFrame(rows)


def _expand_with_scenarios(
    spec_frame,
    variants_per_device=SCENARIO_VARIANTS_PER_DEVICE
) -> pd.DataFrame:
    """Replicate each spec row across all condition profiles.

    Repetition is proportional to the scenario weight, so common
    used-phone profiles are better represented than rare broken
    ones while every profile still appears.

    Each archetype is additionally jittered (see
    `_jitter_scenario`) so the model learns a continuous
    condition-to-value relationship instead of six discrete
    points per device.

    Implemented as one vectorised repeat: every device row is
    repeated once per condition profile, then the profile
    columns are broadcast across those repeats.
    """

    profiles = _build_variant_table(
        variants_per_device
    )

    device_count = len(spec_frame)
    profile_count = len(profiles)

    # spec row i is repeated once for each condition profile,
    # in profile order.
    repeated = spec_frame.iloc[
        np.repeat(
            np.arange(device_count),
            profile_count,
        )
    ].reset_index(drop=True)

    for column in CONDITION_FEATURE_COLUMNS:

        repeated[column] = np.tile(
            profiles[column].to_numpy(),
            device_count,
        )

    repeated[TARGET_COLUMN] = (
        repeated["price_inr"].to_numpy()
        * np.tile(
            profiles["_factor"].to_numpy(),
            device_count,
        )
    )

    repeated["scenario"] = np.tile(
        profiles["scenario"].to_numpy(),
        device_count,
    )

    logger.info(
        "Expanded %d devices x %d profiles into %d rows",
        device_count,
        profile_count,
        len(repeated),
    )

    return repeated


def _load_real_used_dataset():
    """Load a genuine used-phone dataset when one exists.

    This is the extension point. Drop a CSV at
    `data/used_phones_real.csv` containing every column in
    `ml.feature_schema.FEATURES` plus `device_value_inr`, and
    it takes precedence over synthetic scenario expansion.
    """

    if not os.path.exists(REAL_USED_DATASET_PATH):
        return None

    frame = pd.read_csv(REAL_USED_DATASET_PATH)

    required = set(FEATURES) | {TARGET_COLUMN}

    missing = required - set(frame.columns)

    if missing:
        raise ValueError(
            "Real used-device dataset is missing required "
            f"columns: {sorted(missing)}"
        )

    logger.info(
        "Using real used-device dataset: %d rows from %s",
        len(frame),
        REAL_USED_DATASET_PATH,
    )

    return frame


def load_training_frame():
    """Build the DataFrame used to fit the DEVICE VALUE model.

    Returns a frame with every column in FEATURES plus
    TARGET_COLUMN and a `scenario` provenance column.
    """

    validate_feature_contract()

    real_frame = _load_real_used_dataset()

    if real_frame is not None:

        frame = real_frame.copy()

        frame["scenario"] = "real_transaction"

        return frame

    spec_frame = _load_spec_dataset()

    spec_frame["price_inr"] = pd.to_numeric(
        spec_frame["price_inr"],
        errors="coerce",
    )

    spec_frame = spec_frame.dropna(
        subset=["price_inr"]
    )

    spec_frame = spec_frame[
        spec_frame["price_inr"] > 0
    ]

    logger.info(
        "Building condition scenarios over %d devices",
        len(spec_frame),
    )

    return _expand_with_scenarios(spec_frame)