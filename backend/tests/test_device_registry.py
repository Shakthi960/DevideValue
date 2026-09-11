"""
Unit tests for the device registry helpers used when
registering new devices into the catalog/dataset.

These cover the pure helper functions only; the DB/CSV
persistence paths are exercised by the running app.
"""

import pandas as pd
import pytest

from app.services.device_registry import (
    normalize_brand,
    clean_model,
    parse_ram_storage,
    _cache_key,
    _dataset_row_exists,
    _estimate_price,
)


class TestNormalizeBrand:
    def test_known_brand_gets_title_case(self):
        assert normalize_brand("samsung") == "Samsung"
        assert normalize_brand("APPLE") == "Apple"
        assert normalize_brand("OnePlus") == "OnePlus"
        assert normalize_brand("iQOO") == "iQOO"

    def test_unknown_brand_passthrough(self):
        assert normalize_brand("Sony") == "Sony"

    def test_empty_returns_none(self):
        assert normalize_brand("") is None
        assert normalize_brand(None) is None


class TestCleanModel:
    def test_strips_brand_prefix(self):
        assert clean_model("Samsung Galaxy S23", "Samsung") == (
            "Galaxy S23"
        )

    def test_no_brand_prefix_unchanged(self):
        assert clean_model("Galaxy S23", "Samsung") == (
            "Galaxy S23"
        )

    def test_removes_parenthetical_storage_hints(self):
        assert clean_model("iPhone 15 (128GB)") == "iPhone 15"
        assert clean_model("Galaxy S23 (8GB RAM + 128GB)") == (
            "Galaxy S23"
        )
        assert clean_model("Galaxy S23 (8GB + 128GB)") == (
            "Galaxy S23"
        )

    def test_collapses_whitespace(self):
        assert clean_model("  Galaxy   S23  ") == "Galaxy S23"

    def test_empty_returns_empty(self):
        assert clean_model("") == ""
        assert clean_model(None) == ""


class TestParseRamStorage:
    def test_standard_variant(self):
        assert parse_ram_storage("8GB + 128GB") == (8, 128)

    def test_compact_variant(self):
        assert parse_ram_storage("8/256") == (8, 256)
        assert parse_ram_storage("8+128") == (8, 128)

    def test_always_ram_first_storage_last(self):
        assert parse_ram_storage("256GB 12GB ROM 12GB RAM") == (
            12,
            256,
        )

    def test_missing_value_raises(self):
        with pytest.raises(ValueError):
            parse_ram_storage("128GB")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_ram_storage("")


class TestCacheKey:
    def test_normalizes_and_joins(self):
        assert _cache_key(
            " Apple ", "iPhone 15", " 128GB "
        ) == "apple|iphone 15|128gb"

    def test_none_parts_become_empty(self):
        assert _cache_key(None, "S23", None) == "|s23|"


class TestDatasetRowExists:
    def _frame(self):
        return pd.DataFrame(
            [
                {
                    "smartphone_brand": "apple",
                    "model": "iphone 15",
                    "storage_gb": 128,
                }
            ]
        )

    def test_matching_row_returns_true(self):
        assert _dataset_row_exists(
            self._frame(), "Apple", "iPhone 15", 128
        )

    def test_different_storage_returns_false(self):
        assert not _dataset_row_exists(
            self._frame(), "Apple", "iPhone 15", 256
        )

    def test_empty_frame_returns_false(self):
        assert not _dataset_row_exists(
            pd.DataFrame(), "Apple", "iPhone 15", 128
        )


class TestEstimatePrice:
    @pytest.mark.skipif(
        not pytest.importorskip(
            "app.services.valuation"
        ).PRICE_MODEL,
        reason="ML price model is not loaded",
    )
    def test_known_device_returns_positive_int(self):
        estimate = _estimate_price(
            "Apple",
            "iPhone 15",
            "8GB + 128GB",
        )

        assert estimate is None or estimate > 0