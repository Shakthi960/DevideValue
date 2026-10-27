"""Feature schema for the DEVICE VALUE model.

This module is the single source of truth for the feature
contract shared by:

  - `ml/condition_dataset.py` (training-frame builder)
  - `ml/train_price_model.py` (training)
  - `ml/price_predictor.py` (inference)
  - `app/services/valuation/*` (feature construction from
    questionnaire / diagnostics / AI photos)

Design rule: feature ORDER and feature NAME live here only.
Both training and inference import these lists, so a column
can never silently drift between the two.

------------------------------------------------------------------
TWO FEATURE GROUPS
------------------------------------------------------------------

1. SPECIFICATION features ("spec_*" naming is implied)
   Static hardware facts about the phone. These come from
   `data/smartphones.csv`.

2. CONDITION features
   The state of THIS individual used unit: age, battery wear,
   screen/body/scratch/dent/crack/frame/camera condition,
   functional + diagnostic test results, repair history,
   accessories, warranty, and the AI photo inspection score.

   The redesign goal: condition is an INPUT to the model,
   not a hand-written percentage multiplied onto the output.
   The Random Forest learns how each condition signal moves
   value, jointly with the specification.

------------------------------------------------------------------
ENCODINGS
------------------------------------------------------------------

Ordinal severity (Gemini + questionnaire both map here):
    none = 0, minor = 1, moderate = 2, severe = 3

Yes/no flags are 1/0.

Warranty / accessories / repair are kept as ORDERED NUMERIC
codes rather than one-hot strings. Rationale: they have a
natural order, and a tree model can split on a single column
instead of an N-way one-hot expansion. The mappings live in
the *_CODES dicts below so they are explicit and auditable.
"""


# ============================================================
# SPECIFICATION FEATURES
# ============================================================

SPEC_FEATURES = [
    "smartphone_brand",
    "model",
    "rating_score",
    "processor_name",
    "processor_brand",
    "core_count",
    "clock_speed_ghz",
    "ram_gb",
    "storage_gb",
    "has_5g",
    "has_nfc",
    "has_ir_blaster",
    "display_inches",
    "res_width_px",
    "res_height_px",
    "refresh_rate_hz",
    "battery_mah",
    "fast_charging",
    "charging_watt",
    "rear_camera_count",
    "front_camera_count",
    "rear_camera_main_mp",
    "front_camera_main_mp",
    "os_name",
    "memory_card_supported",
    "memory_card_type",
]


# ============================================================
# CONDITION FEATURES
#
# Grouped by the evidence source that produces them, so the
# provenance of every column stays obvious.
# ============================================================

# --- Age / battery -------------------------------------------------

CONDITION_FEATURES = [
    # Ownership age in months (0 = brand new).
    "device_age_months",

    # Battery state of charge retained, 30..100 (% of design
    # capacity). 100 for a new cell.
    "battery_health_pct",

    # --- Physical condition, each 0..100 where 100 = flawless ---

    "screen_condition_score",
    "body_condition_score",
    "camera_condition_score",

    # --- Discrete physical damage, ordinal 0..3 ---
    # (none / minor / moderate / severe)

    "scratch_severity",
    "dent_severity",
    "crack_severity",
    "frame_damage_severity",

    # --- Test results, 0..100 ---

    # User-reported functional self-test aggregate.
    "functional_test_score",

    # Machine diagnostics: passed_tests / total_tests * 100.
    "diagnostic_score",

    # Count of individual hardware tests that failed.
    "diagnostics_failed_count",

    # Individual high-signal failures, 1 if that test failed.
    # These let the model price a dead camera differently from
    # a dead GPS chip, which a single average would hide.

    "diagnostic_camera_failed",
    "diagnostic_microphone_failed",
    "diagnostic_touch_failed",
    "diagnostic_sensor_failed",
    "diagnostic_connectivity_failed",

    # --- History / bundle ---

    # 0 = never repaired, 1 = authorized service,
    # 2 = third-party repair, 3 = unknown.
    "repair_history_code",

    # 0 = none, 1 = box only, 2 = charger only, 3 = box + charger.
    "accessories_code",

    # Months of original warranty remaining, 0..24.
    "warranty_months_remaining",

    # Aggregate AI physical-condition score from the photo
    # inspection, 0..100 (100 = no visible damage).
    "ai_condition_score",
]


# ============================================================
# FULL ORDERED FEATURE LIST
# ============================================================

FEATURES = SPEC_FEATURES + CONDITION_FEATURES


# ============================================================
# CATEGORICAL VS NUMERIC SPLIT
#
# Used by the training script to build the ColumnTransformer.
# NOTE: `model` is categorical, but the categorical encoder
# uses handle_unknown="ignore" so a brand-new model name
# typed by a user does not crash the pipeline. At inference
# the matched dataset row supplies the model's true spec
# values (see app/services/valuation/specs.py).
# ============================================================

CATEGORICAL_FEATURES = [
    "smartphone_brand",
    "model",
    "processor_name",
    "processor_brand",
    "os_name",
    "memory_card_type",
]

NUMERIC_FEATURES = [
    feature
    for feature in FEATURES
    if feature not in CATEGORICAL_FEATURES
]


# ============================================================
# CODE TABLES (explicit, auditable mappings)
# ============================================================

SEVERITY_CODES = {
    "none": 0,
    "not_visible": 0,
    "clean": 0,
    "like new": 0,
    "excellent": 0,
    "minor": 1,
    "light": 1,
    "moderate": 2,
    "medium": 2,
    "severe": 3,
    "heavy": 3,
    "major": 3,
    "cracked": 3,
    "broken": 3,
}

REPAIR_CODES = {
    "no": 0,
    "none": 0,
    "no repairs": 0,
    "never": 0,
    "authorized": 1,
    "authorized service": 1,
    "yes authorized service": 1,
    "third party": 2,
    "third-party service": 2,
    "third party service": 2,
    "yes third party service": 2,
    "unknown": 3,
    "i don't know": 3,
    "not sure": 3,
}

# Battery health, from the questionnaire answer text.
BATTERY_HEALTH_PCT = {
    "excellent": 100.0,
    "new": 100.0,
    "100%": 100.0,
    "good": 90.0,
    "80-100%": 90.0,
    "90-100": 90.0,
    "average": 80.0,
    "below 80": 80.0,
    "70-80%": 75.0,
    "replaced": 95.0,
    "below 70%": 65.0,
    "poor": 60.0,
    "unknown": 85.0,
    "i don't know": 85.0,
}

# Device age in months, from the questionnaire answer text.
AGE_MONTHS = {
    "less than 6 months": 3.0,
    "less_than_6_months": 3.0,
    "0-6 months": 3.0,
    "6 to 12 months": 9.0,
    "6_to_12_months": 9.0,
    "6-12 months": 9.0,
    "1 year": 12.0,
    "1_to_2_years": 24.0,
    "1 to 2 years": 24.0,
    "1-2 years": 24.0,
    "2 years": 24.0,
    "2_to_3_years": 36.0,
    "2 to 3 years": 36.0,
    "2-3 years": 36.0,
    "more_than_3_years": 48.0,
    "more than 3 years": 48.0,
    "3+ years": 48.0,
}

# Screen / body / camera condition, 0..100 where 100 = flawless.
# These map questionnaire wording onto the same 0..100 scale the
# AI photo analyzer emits, so the two evidence sources are
# directly comparable as model inputs.
CONDITION_ANSWER_SCORES = {
    "excellent": 98.0,
    "like new": 95.0,
    "good": 88.0,
    "minor scratches": 72.0,
    "minor_scratches": 72.0,
    "scratched": 60.0,
    "multiple scratches": 48.0,
    "dents": 55.0,
    "minor dents": 65.0,
    "minor_dents": 65.0,
    "heavy damage": 25.0,
    "major damage": 22.0,
    "major_damage": 22.0,
    "cracked": 18.0,
    "broken": 8.0,
    "display problem": 10.0,
    "display_problem": 10.0,
    "unknown": 80.0,
    "not sure": 80.0,
}

# Functional self-test aggregate, 0..100.
FUNCTIONAL_ANSWER_SCORES = {
    "yes": 95.0,
    "everything works": 95.0,
    "fully working": 95.0,
    "good": 90.0,
    "not sure": 70.0,
    "some issues": 45.0,
    "no": 25.0,
    "major issues": 20.0,
    "not working": 5.0,
}

# Self-reported per-component scores, folded into the functional
# aggregate. These mirror the SELF_REPORT questions in the
# full-inspection frontend flow.
FUNCTIONAL_COMPONENT_SCORES = {
    # battery life
    "battery": {
        "excellent": 100.0,
        "good": 85.0,
        "average": 65.0,
        "poor": 35.0,
    },
    # charging
    "charging": {
        "yes": 100.0,
        "slow": 60.0,
        "no": 10.0,
    },
    # speaker / mic
    "speaker": {
        "excellent": 100.0,
        "good": 82.0,
        "poor": 45.0,
        "not_working": 5.0,
    },
    # hardware buttons
    "buttons": {
        "yes": 100.0,
        "partial": 55.0,
        "no": 10.0,
    },
    # connectivity
    "connectivity": {
        "yes": 100.0,
        "wifi_only": 60.0,
        "frequent": 40.0,
        "nothing": 5.0,
    },
    # touchscreen responsiveness
    "screen_touch": {
        "yes": 100.0,
        "dead_zones": 50.0,
        "no": 10.0,
    },
}

# Sensor test ids reported in the diagnostics report.
# Mapped to the individual-failure feature columns.
SENSOR_TEST_KEYS = [
    "camera",
    "microphone",
    "touch",
    "motion",
    "location",
]

SENSOR_FAILURE_FEATURES = {
    "camera": "diagnostic_camera_failed",
    "microphone": "diagnostic_microphone_failed",
    "touch": "diagnostic_touch_failed",
    "motion": "diagnostic_sensor_failed",
    "location": "diagnostic_sensor_failed",
}

SENSOR_CONNECTIVITY_KEYS = [
    "connectivity",
    "wifi",
    "bluetooth",
    "network",
]


# ============================================================
# DEFAULTS
#
# Used when an evidence source is unavailable (e.g. a quick-value
# flow with no photos). Defaults are deliberately NEUTRAL-GOOD,
# not zero: an unanswered question must not be encoded as "this
# phone is broken", it must be encoded as "condition unknown".
# `app/services/valuation/pipeline.py` also downgrades the
# reported confidence when defaults are used.
# ============================================================

DEFAULT_CONDITION_FEATURES = {
    "device_age_months": 12.0,
    "battery_health_pct": 90.0,
    "screen_condition_score": 88.0,
    "body_condition_score": 88.0,
    "camera_condition_score": 90.0,
    "scratch_severity": 0.0,
    "dent_severity": 0.0,
    "crack_severity": 0.0,
    "frame_damage_severity": 0.0,
    "functional_test_score": 90.0,
    "diagnostic_score": 90.0,
    "diagnostics_failed_count": 0.0,
    "diagnostic_camera_failed": 0.0,
    "diagnostic_microphone_failed": 0.0,
    "diagnostic_touch_failed": 0.0,
    "diagnostic_sensor_failed": 0.0,
    "diagnostic_connectivity_failed": 0.0,
    "repair_history_code": 0.0,
    "accessories_code": 0.0,
    "warranty_months_remaining": 0.0,
    "ai_condition_score": 88.0,
}


# ============================================================
# VALIDATION
# ============================================================

def validate_feature_contract():
    """Fail loudly if the schema is internally inconsistent.

    Called at import time of the training and inference paths so
    a schema mistake surfaces immediately instead of producing a
    silently mis-ordered feature vector.
    """

    errors = []

    if len(FEATURES) != len(set(FEATURES)):
        errors.append("duplicate feature names in FEATURES")

    if set(SPEC_FEATURES) & set(CONDITION_FEATURES):
        errors.append(
            "SPEC_FEATURES and CONDITION_FEATURES overlap"
        )

    for feature in CONDITION_FEATURES:
        if feature not in DEFAULT_CONDITION_FEATURES:
            errors.append(
                f"condition feature '{feature}' has no default"
            )

    for feature in DEFAULT_CONDITION_FEATURES:
        if feature not in CONDITION_FEATURES:
            errors.append(
                f"default '{feature}' is not a condition feature"
            )

    for categorical in CATEGORICAL_FEATURES:
        if categorical not in FEATURES:
            errors.append(
                f"categorical '{categorical}' not in FEATURES"
            )

    if set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) != set(
        FEATURES
    ):
        errors.append(
            "NUMERIC + CATEGORICAL does not cover FEATURES"
        )

    if FEATURES != SPEC_FEATURES + CONDITION_FEATURES:
        errors.append("FEATURES order is not spec-then-condition")

    if errors:
        raise ValueError(
            "Feature schema is invalid:\n- "
            + "\n- ".join(errors)
        )

    return True