"""
Tests for the ML-based valuation service and the shared
Gemini config (core.gemini).

The ML valuation tests are skipped automatically when the
trained price model is not present (e.g. clean CI checkout),
mirroring the behaviour in test_valuation.py.
"""

import pytest


class TestCalculateMlValuation:
    @pytest.fixture
    def skip_if_no_model(self):
        mod = pytest.importorskip(
            "app.services.valuation"
        )

        if not mod.PRICE_MODEL:
            pytest.skip("ML price model is not loaded")

    def _valuate(self, condition_score=100.0):
        from app.services.ml_valuation import (
            calculate_ml_valuation,
        )

        return calculate_ml_valuation(
            {
                "smartphone_brand": "Apple",
                "model": "iPhone 15",
                "rating_score": 8.0,
                "ram_gb": 8,
                "storage_gb": 128,
            },
            condition_score,
        )

    def test_returns_expected_fields(self, skip_if_no_model):
        result = self._valuate()

        assert set(
            [
                "base_market_price",
                "condition_score",
                "condition_multiplier",
                "resale_price",
                "exchange_price",
                "condition_grade",
                "prediction_source",
                "model_type",
                "model_version",
            ]
        ).issubset(result.keys())

        assert result["resale_price"] > 0

    def test_exchange_is_88_percent_of_resale(
        self,
        skip_if_no_model,
    ):
        result = self._valuate()
        assert result["exchange_price"] == round(
            result["resale_price"] * 0.88,
            2,
        )

    def test_perfect_condition_full_multiplier(
        self,
        skip_if_no_model,
    ):
        result = self._valuate(100.0)
        assert result["condition_multiplier"] == 1.0

    def test_zero_condition_floor_multiplier(
        self,
        skip_if_no_model,
    ):
        result = self._valuate(0.0)
        assert result["condition_multiplier"] == 0.70

    def test_condition_grade_matches_shared_rule(
        self,
        skip_if_no_model,
    ):
        from app.services.valuation import get_condition_grade

        assert self._valuate(95.0)["condition_grade"] == (
            get_condition_grade(95)
        )
        assert self._valuate(50.0)["condition_grade"] == "D"


class TestGeminiConfig:
    def test_model_name_defaults(self):
        from app.core.gemini import MODEL_NAME

        assert MODEL_NAME == "gemini-3.6-flash"

    def test_client_is_none_without_api_key(
        self, monkeypatch
    ):
        monkeypatch.delenv(
            "GEMINI_API_KEY", raising=False
        )

        from app.core.gemini import get_genai_client

        assert get_genai_client() is None