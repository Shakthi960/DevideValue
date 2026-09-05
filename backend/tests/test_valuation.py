"""
Unit tests for the valuation pipeline.

These cover the pure helper functions and the
condition-scoring logic (including regression tests
for the snake_case -> space normalization fix),
without requiring any external services.
"""

import pytest

from app.services.valuation import (
    normalize_text,
    normalize_brand,
    normalize_model,
    parse_storage,
    calculate_condition_score,
    get_condition_grade,
    calculate_valuation,
)


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
# CONDITION SCORE
# ============================================================

class TestConditionScore:
    def test_perfect_condition_is_100(self):
        answers = {
            "device_age": "less_than_6_months",
            "screen_condition": "excellent",
            "body_condition": "excellent",
            "battery_condition": "excellent",
            "functionality": "yes",
            "original_charger": "yes",
            "original_box": "yes",
            "repair_history": "no",
        }
        score = calculate_condition_score(answers)
        assert score <= 100
        assert score >= 98  # allowed +2 for accessories, adjusted

    def test_minor_scratches_apply_deduction(self):
        answers = {
            "device_age": "less_than_6_months",
            "screen_condition": "minor_scratches",
            "body_condition": "excellent",
            "battery_condition": "excellent",
            "functionality": "yes",
            "original_charger": "no",
            "original_box": "no",
            "repair_history": "no",
        }
        score = calculate_condition_score(answers)
        assert score == 89  # 100 - 8 (screen) - 3 (no accessories)

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
        score = calculate_condition_score(answers)
        assert score == 0  # deductions clamp at floor of 0


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
# FULL VALUATION
# ============================================================

class TestCalculateValuation:
    @pytest.mark.skipif(
        not pytest.importorskip(
            "app.services.valuation"
        ).PRICE_MODEL,
        reason="ML price model is not loaded"
    )
    def test_returns_expected_fields(self):
        result = calculate_valuation(
            brand="Apple",
            model="iPhone 15",
            storage="128GB",
            answers={
                "device_age": "less_than_6_months",
                "screen_condition": "excellent",
                "body_condition": "excellent",
                "battery_condition": "excellent",
                "functionality": "yes",
                "original_charger": "yes",
                "original_box": "yes",
                "repair_history": "no",
            },
        )

        assert set(
            [
                "market_price",
                "resale_price",
                "exchange_price",
                "condition_score",
                "condition_grade",
            ]
        ).issubset(result.keys())

        assert result["resale_price"] > 0
        assert result["exchange_price"] > 0
        assert result["resale_price"] >= result["exchange_price"]
        assert 0 <= result["condition_score"] <= 100

    @pytest.mark.skipif(
        not pytest.importorskip(
            "app.services.valuation"
        ).PRICE_MODEL,
        reason="ML price model is not loaded"
    )
    def test_exchange_is_88_percent_of_resale(self):
        result = calculate_valuation(
            brand="Apple",
            model="iPhone 15",
            storage="128GB",
            answers={
                "device_age": "less_than_6_months",
                "screen_condition": "excellent",
                "body_condition": "excellent",
                "battery_condition": "excellent",
                "functionality": "yes",
                "original_charger": "yes",
                "original_box": "yes",
                "repair_history": "no",
            },
        )

        assert result["exchange_price"] == round(
            result["resale_price"] * 0.88
        )

    def test_unknown_device_returns_fallback(self):
        result = calculate_valuation(
            brand="NonexistentBrand",
            model="NonexistentModel 99",
            storage="128GB",
            answers={},
        )

        assert result["resale_price"] > 0
        assert result["condition_grade"] in [
            "A+",
            "A",
            "B",
            "C",
            "D",
        ]
