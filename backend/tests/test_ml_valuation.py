"""Tests for the ML valuation service and the shared Gemini config.

The ML tests are skipped automatically when the trained device
value model is not present (e.g. a clean CI checkout).

Redesign contract: `/ml/predict` returns ONE number. There is no
resale price, no exchange price and no condition multiplier, so
these tests assert the multiplier is gone and that the condition
score changes the value through the model.
"""

import pytest


def _model_loaded():
    mod = pytest.importorskip("app.services.valuation")

    if not mod.PRICE_MODEL:
        pytest.skip("Device value model is not loaded")

    return True


requires_model = pytest.mark.skipif(
    not _model_loaded(),
    reason="Device value model is not loaded",
)

_DEVICE = {
    "smartphone_brand": "Apple",
    "model": "iPhone 15",
    "rating_score": 8.0,
    "ram_gb": 8,
    "storage_gb": 128,
}


class TestCalculateMlValuation:
    def _valuate(self, condition_score=100.0, **kwargs):
        from app.services.ml_valuation import (
            calculate_ml_valuation,
        )

        return calculate_ml_valuation(
            _DEVICE,
            condition_score,
            **kwargs
        )

    @requires_model
    def test_returns_device_value_and_supporting_data(self):
        result = self._valuate()

        assert set(
            [
                "device_value",
                "currency",
                "confidence",
                "condition_score",
                "diagnostic_score",
                "condition_grade",
                "prediction_source",
                "model_type",
            ]
        ).issubset(result.keys())

        assert result["device_value"] > 0
        assert result["currency"] == "INR"
        assert 0.0 <= result["confidence"] <= 1.0

    @requires_model
    def test_resale_exchange_and_multiplier_are_gone(self):
        result = self._valuate()

        assert "resale_price" not in result
        assert "exchange_price" not in result
        assert "condition_multiplier" not in result
        assert "base_market_price" not in result

    @requires_model
    def test_worse_condition_lowers_the_device_value(self):
        good = self._valuate(100.0)
        bad = self._valuate(10.0)

        assert bad["device_value"] < good["device_value"]

    @requires_model
    def test_condition_score_is_echoed_back(self):
        result = self._valuate(64.0)

        assert result["condition_score"] == 64.0
        assert result["condition_grade"] == "C"

    @requires_model
    def test_out_of_range_condition_is_clamped(self):
        result = self._valuate(150.0)

        assert result["condition_score"] == 100.0
        assert self._valuate(-20.0)["condition_score"] == 0.0

    @requires_model
    def test_diagnostic_score_overrides_the_expansion(self):
        result = self._valuate(100.0, diagnostic_score=25.0)

        assert result["diagnostic_score"] == 25.0
        assert result["device_value"] < self._valuate(
            100.0, diagnostic_score=100.0
        )["device_value"]

    @requires_model
    def test_explicit_condition_features_win_over_the_score(self):
        """A caller that sends real features must not be overwritten."""

        from app.services.ml_valuation import (
            calculate_ml_valuation,
        )

        good = calculate_ml_valuation(
            dict(_DEVICE, screen_condition_score=100.0),
            50.0,
        )

        bad = calculate_ml_valuation(
            dict(_DEVICE, screen_condition_score=20.0),
            50.0,
        )

        assert good["device_value"] > bad["device_value"]

    @requires_model
    def test_unknown_device_still_predicts(self):
        from app.services.ml_valuation import (
            calculate_ml_valuation,
        )

        result = calculate_ml_valuation(
            {
                "smartphone_brand": "NonexistentBrand",
                "model": "NonexistentModel 99",
                "ram_gb": 8,
                "storage_gb": 128,
            },
            70.0,
        )

        assert result["device_value"] > 0

    @requires_model
    def test_empty_payload_does_not_crash(self):
        from app.services.ml_valuation import (
            calculate_ml_valuation,
        )

        result = calculate_ml_valuation({}, 70.0)

        assert result["device_value"] > 0


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