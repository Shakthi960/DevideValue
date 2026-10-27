"""Compatibility facade for the valuation service.

The valuation package was restructured for the DEVICE VALUE
redesign. The old `registry.py` mixed four concerns in one
file: text normalization, dataset matching, ML input building,
and market-price prediction.

Those now live in dedicated modules:

  specs.py                 dataset matching + feature assembly
  condition_features.py    questionnaire  -> features
  diagnostic_features.py   diagnostics     -> features
  photo_features.py        AI photos       -> features
  pipeline.py              the single predict_device_value flow

This module keeps the names that non-valuation callers still
import, so nothing outside the valuation layer has to change in
the same commit.

REMOVED ON PURPOSE
-----------------
`predict_market_price`, `build_ml_input`, `EXCHANGE_RATE` and
`GRADE_MULTIPLIERS` are gone. The market-price-only prediction
they implemented is exactly the design being replaced: predict a
spec-only price, then scale it by condition outside the model.
The replacement is `pipeline.predict_device_value_for_device`.
"""

from app.core.logger import get_logger
from app.services.valuation.specs import (
    build_spec_features,
    find_spec_row,
    normalize_brand,
    normalize_model,
    normalize_text,
    parse_ram,
    parse_storage,
    reference_price,
)
from ml.feature_schema import (
    CATEGORICAL_FEATURES,
    CONDITION_FEATURES,
    FEATURES,
    NUMERIC_FEATURES,
    SPEC_FEATURES,
    validate_feature_contract,
)
from ml.model_store import (
    get_model_pipeline,
    get_price_dataset,
)


logger = get_logger(__name__)


# Dataset and model handles, loaded once at import time exactly
# as before. `PRICE_MODEL` is now the fitted sklearn pipeline for
# the DEVICE VALUE model (previously it was the spec-only market
# price pipeline).
PRICE_MODEL = get_model_pipeline()
PHONE_DATA = get_price_dataset()


# Legacy alias. The specification matcher was renamed
# `find_spec_row`; this keeps older imports working.
def find_device(
    brand,
    model,
    storage_gb=None
):
    return find_spec_row(
        PHONE_DATA,
        brand=brand,
        model=model,
        storage_gb=storage_gb,
    )