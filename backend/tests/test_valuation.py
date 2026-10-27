"""Unit tests for the DEVICE VALUE valuation pipeline.

Covers normalization, the questionnaire -> condition feature
mapping, diagnostics -> diagnostic feature mapping, AI photo
results -> structured features, and the single-value prediction
flow.

No resale price and no exchange price: the platform produces one
number, and these tests assert that number is what comes back.
"""

import pytest

from app.services.valuation import (
    calculate_condition_score,
    collect_photo_features,
    condition_features_from_answers,
    diagnostic_features,
    get_condition_grade,
    normalize_brand,
    normalize_model,
    normalize_text,
    parse_storage,
    predict_device_value_for_device,
)
from ml.feature_schema import (
    CONDITION_FEATURES,
    FEATURES,
    SPEC_FEATURES,
    validate_feature_contract,
)


# ============================================================
# FEATURE CONTRACT
# ============================================================

class TestFeatureContract:
    def test_schema_is_internally_consistent(self):
        assert validate_feature_contract() is True

    def test_spec_and_condition_do_not_overlap(self):
        assert not set(SPEC_FEATURES) & set(CONDITION_FEATURES)

    def test_every_condition_feature_has_a_default(self):
        from ml.feature_schema import (
            DEFAULT_CONDITION_FEATURES,
        )

        for feature in CONDITION_FEATURES:
            assert feature in DEFAULT_CONDITION_FEATURES

    def test_no_resale_or_exchange_feature_exists(self):
        joined = " ".join(FEATURES).lower()

        assert "resale" not in joined
        assert "exchange" not in joined


# ============================================================
# NORMALIZATION
# ============================================================

class TestNormalizeText:
    def test_none_returns_empty(self):
        assert normalize_text(None) == ""

    def test_lowercases_and_strips(self):
        assert normalize_text("  HELLO  ") == "hello"

    def test_collapses_whitespace(self):
        assert normalize_text("a   b") == "a b"

    def test_underscores_become_spaces(self):
        assert normalize_text("minor_scratches") == "minor scratches"

    def test_underscores_and_spaces_combined(self):
        assert (
            normalize_text("  minor_scratches  ")
            == "minor scratches"
        )


class TestNormalizeBrand:
    def test_apple_alias(self):
        assert normalize_brand("apple") == "apple"

    def test_google_pixel_maps_to_google(self):
        assert normalize_brand("Google Pixel") == "google"

    def test_pixel_maps_to_google(self):
        assert normalize_brand("Pixel") == "google"

    def test_redmi_maps_to_xiaomi(self):
        assert normalize_brand("Redmi") == "xiaomi"

    def test_one_plus_maps_to_oneplus(self):
        assert normalize_brand("One Plus") == "oneplus"

    def test_unknown_brand_unchanged(self):
        assert normalize_brand("Sony") == "sony"


class TestNormalizeModel:
    def test_strips_leading_brand(self):
        assert normalize_model("Samsung Galaxy S23") == "galaxy s23"

    def test_apple_stripped(self):
        assert normalize_model("iPhone 14") == "iphone 14"

    def test_no_brand_prefix_unchanged(self):
        assert normalize_model("Galaxy S23") == "galaxy s23"


class TestParseStorage:
    def test_none(self):
        assert parse_storage(None) is None

    def test_tb(self):
        assert parse_storage("1 TB") == 1024

    def test_gb(self):
        assert parse_storage("128 GB") == 128

    def test_variant_string(self):
        assert parse_storage("6GB + 128GB") == 128

    def test_variant_string_takes_storage_not_ram(self):
        assert parse_storage("8GB + 256GB") == 256
        assert parse_storage("12GB + 512GB") == 512

    def test_multiple_tb(self):
        assert parse_storage("2TB") == 2048

    def test_numeric(self):
        assert parse_storage("256") == 256

    def test_bare_pair_takes_storage_not_ram(self):
        assert parse_storage("8 + 256") == 256
        assert parse_storage("8+256") == 256
        assert parse_storage("8/256") == 256
        assert parse_storage("6 128") == 128

    def test_unknown_returns_none(self):
        assert parse_storage("unknown") is None


# ============================================================
# CONDITION FEATURES FROM THE QUESTIONNAIRE
# ============================================================

_PERFECT_ANSWERS = {
    "device_age": "less_than_6_months",
    "screen_condition": "excellent",
    "body_condition": "excellent",
    "battery_condition": "excellent",
    "functionality": "yes",
    "original_charger": "yes",
    "original_box": "yes",
    "repair_history": "no",
}


class TestConditionFeatures:
    def test_perfect_answers_map_to_best_values(self):
        features = condition_features_from_answers(
            _PERFECT_ANSWERS
        )

        assert features["device_age_months"] == 3.0
        assert features["battery_health_pct"] == 100.0
        assert features["screen_condition_score"] >= 95.0
        assert features["repair_history_code"] == 0.0
        assert features["accessories_code"] == 3.0
        assert features["functional_test_score"] >= 90.0

    def test_cracked_screen_lowers_screen_feature(self):
        features = condition_features_from_answers({
            "screen_condition": "cracked",
        })

        assert features["screen_condition_score"] == 18.0

    def test_age_increases_with_years_owned(self):
        young = condition_features_from_answers({
            "device_age": "less_than_6_months",
        })

        old = condition_features_from_answers({
            "device_age": "more_than_3_years",
        })

        assert young["device_age_months"] < old[
            "device_age_months"
        ]

    def test_worn_battery_lowers_health(self):
        features = condition_features_from_answers({
            "battery_condition": "below_70%",
        })

        assert features["battery_health_pct"] == 65.0

    def test_third_party_repair_codes_higher_than_none(self):
        never = condition_features_from_answers({
            "repair_history": "no",
        })

        third_party = condition_features_from_answers({
            "repair_history": "third_party",
        })

        authorized = condition_features_from_answers({
            "repair_history": "authorized",
        })

        assert never["repair_history_code"] == 0.0
        assert authorized["repair_history_code"] == 1.0
        assert third_party["repair_history_code"] == 2.0

    def test_accessories_code_distinguishes_bundle(self):
        both = condition_features_from_answers({
            "original_charger": "yes",
            "original_box": "yes",
        })

        neither = condition_features_from_answers({
            "original_charger": "no",
            "original_box": "no",
        })

        assert both["accessories_code"] == 3.0
        assert neither["accessories_code"] == 0.0

    def test_missing_answers_fall_back_to_neutral_defaults(self):
        """An unanswered question must not read as 'broken'."""

        features = condition_features_from_answers({})

        assert features["screen_condition_score"] > 50.0
        assert features["battery_health_pct"] > 50.0
        assert features["repair_history_code"] == 0.0

    def test_self_report_overrides_single_functionality_answer(self):
        features = condition_features_from_answers(
            {"functionality": "yes"},
            self_report={
                "battery": "poor",
                "charging": "no",
                "speaker": "poor",
                "buttons": "no",
                "connectivity": "nothing",
                "screen_touch": "no",
            },
        )

        assert features["functional_test_score"] < 40.0

    def test_only_condition_features_returned(self):
        features = condition_features_from_answers(
            _PERFECT_ANSWERS
        )

        for name in features:
            assert name in CONDITION_FEATURES


# ============================================================
# DISPLAY-ONLY CONDITION SCORE
#
# This number is shown in the UI. It must not influence the
# predicted value.
# ============================================================

class TestConditionScore:
    def test_perfect_condition_is_near_100(self):
        score = calculate_condition_score(_PERFECT_ANSWERS)
        assert score <= 100
        assert score >= 98

    def test_minor_scratches_apply_deduction(self):
        answers = dict(_PERFECT_ANSWERS)
        answers["screen_condition"] = "minor_scratches"
        answers["original_charger"] = "no"
        answers["original_box"] = "no"

        assert calculate_condition_score(answers) == 89

    def test_cracked_phone_scores_zero(self):
        answers = {
            "device_age": "2_to_3_years",
            "screen_condition": "cracked",
            "body_condition": "major_damage",
            "battery_condition": "below_80",
            "functionality": "no",
            "original_charger": "no",
            "original_box": "no",
            "repair_history": "third_party",
        }

        assert calculate_condition_score(answers) == 0


class TestConditionGrade:
    def test_a_plus(self):
        assert get_condition_grade(95) == "A+"

    def test_a(self):
        assert get_condition_grade(85) == "A"

    def test_b(self):
        assert get_condition_grade(75) == "B"

    def test_c(self):
        assert get_condition_grade(65) == "C"

    def test_d(self):
        assert get_condition_grade(50) == "D"


# ============================================================
# DIAGNOSTICS -> FEATURES
# ============================================================

class TestDiagnosticFeatures:
    def test_all_passing_sensors_score_100(self):
        features = diagnostic_features(
            working="yes",
            sensor_results={
                "camera": "passed",
                "microphone": "passed",
                "touch": "passed",
                "motion": "passed",
                "location": "passed",
            },
        )

        assert features["diagnostic_score"] == 100.0
        assert features["diagnostics_failed_count"] == 0.0

    def test_score_is_passed_over_total(self):
        features = diagnostic_features(
            working="yes",
            sensor_results={
                "camera": "passed",
                "microphone": "passed",
                "touch": "failed",
                "motion": "passed",
            },
        )

        assert features["diagnostic_score"] == 75.0
        assert features["diagnostics_failed_count"] == 1.0

    def test_individual_failure_flags_are_set(self):
        features = diagnostic_features(
            working="yes",
            sensor_results={
                "camera": "failed",
                "microphone": "passed",
                "touch": "failed",
            },
        )

        assert features["diagnostic_camera_failed"] == 1.0
        assert features["diagnostic_touch_failed"] == 1.0
        assert features["diagnostic_microphone_failed"] == 0.0

    def test_unsupported_is_not_a_failure(self):
        """A browser that cannot test GPS must not fail it."""

        features = diagnostic_features(
            working="yes",
            sensor_results={
                "camera": "passed",
                "microphone": "passed",
                "motion": "unsupported",
                "location": "unsupported",
            },
        )

        assert features["diagnostic_score"] == 100.0
        assert features["diagnostics_failed_count"] == 0.0
        assert features["diagnostic_sensor_failed"] == 0.0

    def test_declared_not_working_zeroes_everything(self):
        features = diagnostic_features(
            working="no",
            sensor_results={
                "camera": "passed",
            },
        )

        assert features["diagnostic_score"] == 0.0
        assert features["diagnostic_camera_failed"] == 1.0
        assert features["diagnostic_touch_failed"] == 1.0

    def test_reported_score_used_when_no_sensors(self):
        features = diagnostic_features(
            working="yes",
            diagnostics_score=80.0,
        )

        assert features["diagnostic_score"] == 80.0

    def test_connectivity_failure_detected_in_self_report(self):
        features = diagnostic_features(
            working="yes",
            sensor_results={"camera": "passed"},
            self_report={"connectivity": "nothing"},
        )

        assert features[
            "diagnostic_connectivity_failed"
        ] == 1.0

    def test_report_json_string_is_parsed(self):
        import json

        features = diagnostic_features(
            working="yes",
            diagnostics_report=json.dumps({
                "sensorResults": {
                    "camera": "passed",
                    "microphone": "failed",
                },
            }),
        )

        assert features["diagnostic_score"] == 50.0
        assert features["diagnostic_microphone_failed"] == 1.0


# ============================================================
# AI PHOTOS -> STRUCTURED FEATURES
# ============================================================

def _photo_analysis(
    severity="minor",
    damage=10,
    confidence=0.9,
    detected=True
):
    return {
        "photos": [
            {
                "photo_type": view,
                "analysis": {
                    "quality_score": 90,
                    "phone_detection": {
                        "detected": detected
                    },
                    "physical_condition": {
                        "scratches": {
                            "detected": severity != "none",
                            "severity": severity,
                        },
                        "dents": {
                            "detected": False,
                            "severity": "none",
                        },
                        "cracks": {
                            "detected": severity == "severe",
                            "severity": (
                                "severe"
                                if severity == "severe"
                                else "none"
                            ),
                        },
                        "frame_damage": {
                            "detected": False,
                            "severity": "none",
                        },
                        "visible_damage_score": damage,
                        "confidence": confidence,
                    },
                },
            }
            for view in (
                "front", "back", "left",
                "right", "top", "bottom",
            )
        ]
    }


class TestPhotoFeatures:
    def test_severities_become_ordinal_codes(self):
        features = collect_photo_features(
            _photo_analysis(severity="moderate")
        )

        assert features["scratch_severity"] == 2.0
        assert features["crack_severity"] == 0.0

    def test_severe_crack_codes_three(self):
        features = collect_photo_features(
            _photo_analysis(severity="severe")
        )

        assert features["crack_severity"] == 3.0

    def test_no_multiplier_is_returned(self):
        """The redesign forbids a 0.60-1.00 photo multiplier."""

        features = collect_photo_features(
            _photo_analysis(severity="none", damage=0)
        )

        assert "multiplier" not in features

    def test_damage_score_inverts_into_condition_score(self):
        clean = collect_photo_features(
            _photo_analysis(severity="none", damage=0)
        )

        wrecked = collect_photo_features(
            _photo_analysis(severity="severe", damage=90)
        )

        assert clean["ai_condition_score"] > wrecked[
            "ai_condition_score"
        ]

    def test_poor_capture_lowers_the_score(self):
        """Blurry, undetected photos must not read as pristine."""

        good = collect_photo_features(
            _photo_analysis(damage=10, detected=True)
        )

        bad = collect_photo_features(
            _photo_analysis(damage=10, detected=False)
        )

        assert bad["ai_condition_score"] < good[
            "ai_condition_score"
        ]

    def test_missing_photo_analysis_is_safe(self):
        features = collect_photo_features(None)

        assert features["ai_views_analyzed"] == 0
        assert "scratch_severity" in features


# ============================================================
# SINGLE DEVICE VALUE
# ============================================================

def _model_available():
    from app.services.valuation import PRICE_MODEL

    return PRICE_MODEL is not None


requires_model = pytest.mark.skipif(
    not _model_available(),
    reason="Device value model is not trained/loaded",
)


class TestDeviceValuePrediction:
    @requires_model
    def test_returns_single_value_and_supporting_scores(self):
        result = predict_device_value_for_device(
            brand="Apple",
            model="iPhone 15",
            storage="128GB",
            answers=_PERFECT_ANSWERS,
            working="yes",
            diagnostics_score=100.0,
        )

        assert "device_value" in result
        assert "condition_score" in result
        assert "diagnostic_score" in result
        assert "confidence" in result

        assert result["device_value"] > 0
        assert result["currency"] == "INR"
        assert 0.0 <= result["confidence"] <= 1.0
        assert 0 <= result["condition_score"] <= 100

    @requires_model
    def test_resale_and_exchange_are_absent(self):
        """The redesign removed these fields on purpose."""

        result = predict_device_value_for_device(
            brand="Apple",
            model="iPhone 15",
            storage="128GB",
            answers=_PERFECT_ANSWERS,
        )

        assert "resale_price" not in result
        assert "exchange_price" not in result
        assert "exchange_value" not in result

    @requires_model
    def test_worse_condition_lowers_the_value(self):
        good = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers=_PERFECT_ANSWERS,
        )

        bad_answers = {
            "device_age": "more_than_3_years",
            "screen_condition": "cracked",
            "body_condition": "major_damage",
            "battery_condition": "below_70%",
            "functionality": "no",
            "original_charger": "no",
            "original_box": "no",
            "repair_history": "third_party",
        }

        bad = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers=bad_answers,
        )

        assert bad["device_value"] < good["device_value"]

    @requires_model
    def test_failed_diagnostics_lower_the_value(self):
        passing = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers=_PERFECT_ANSWERS,
            working="yes",
            diagnostics_score=100.0,
        )

        failing = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers=_PERFECT_ANSWERS,
            working="no",
            diagnostics_score=0.0,
        )

        assert failing["device_value"] < passing["device_value"]

    @requires_model
    def test_unknown_device_still_predicts(self):
        result = predict_device_value_for_device(
            brand="NonexistentBrand",
            model="NonexistentModel 99",
            storage="128GB",
            answers={},
        )

        assert result["device_value"] > 0
        assert result["condition_grade"] in [
            "A+", "A", "B", "C", "D",
        ]

    @requires_model
    def test_missing_evidence_lowers_confidence(self):
        thin = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers={},
        )

        rich = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers=_PERFECT_ANSWERS,
            photo_analysis=_photo_analysis(),
            working="yes",
            diagnostics_score=100.0,
        )

        assert thin["confidence"] < rich["confidence"]
        assert thin["evidence_coverage"] < rich[
            "evidence_coverage"
        ]

    @requires_model
    def test_include_features_returns_the_vector(self):
        result = predict_device_value_for_device(
            brand="Samsung",
            model="Galaxy S24",
            storage="8GB + 256GB",
            answers=_PERFECT_ANSWERS,
            include_features=True,
        )

        assert set(result["input_features"]) == set(FEATURES)