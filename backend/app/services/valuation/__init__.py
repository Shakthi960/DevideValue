"""Valuation service.

Facade re-exporting the public API from the internal
valuation submodules so existing callers can keep importing
`from app.services.valuation import ...` unchanged.
"""

from app.services.valuation.registry import (
    PRICE_MODEL,
    PHONE_DATA,
    normalize_text,
    normalize_brand,
    normalize_model,
    parse_storage,
    find_device,
    build_ml_input,
    predict_market_price,
)
from app.services.valuation.condition import (
    EXCHANGE_RATE,
    GRADE_MULTIPLIERS,
    calculate_condition_score,
    get_condition_grade,
    photo_condition_metrics,
)
from app.services.valuation.market import (
    get_market_price,
)
from app.services.valuation.core import (
    calculate_valuation,
)
