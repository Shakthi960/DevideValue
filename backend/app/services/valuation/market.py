from app.core.logger import get_logger
from app.services.valuation.registry import predict_market_price


logger = get_logger(__name__)


def _ml_fallback(brand, model, storage):
    """ML + dataset fallback that converts a missing model file
    into a clean ValueError instead of crashing the request."""

    try:
        return predict_market_price(
            brand=brand,
            model=model,
            storage=storage,
        )
    except RuntimeError as exc:
        logger.warning(
            "ML price model unavailable for %s %s: %s",
            brand,
            model,
            exc,
        )
        raise ValueError(
            "Market price is currently unavailable."
        ) from exc


# ============================================================
# MARKET PRICE (ORACLE-FIRST)
# ============================================================

def get_market_price(brand, model, storage):
    """
    Resolve the market anchor price.

    1. Live Gemini price oracle (with DB cache).
    2. ML + local dataset fallback if the oracle
       is unavailable.

    Returns:
      (market_price, new_price_inr, price_source)
    """

    try:

        from app.services.price_oracle import (
            lookup as oracle_lookup
        )

        result = oracle_lookup(
            brand=brand,
            model=model,
            storage=storage,
        )

    except Exception as exc:

        logger.warning(
            "Price oracle failed for %s %s: %s",
            brand,
            model,
            exc,
        )

        result = None

    if (
        result is not None
        and result.get("exists") is False
    ):

        logger.info(
            "Device '%s %s' could not be verified by the "
            "oracle. Falling back to the closest-match "
            "estimate instead of blocking.",
            brand,
            model,
        )

        market_price = _ml_fallback(
            brand=brand,
            model=model,
            storage=storage,
        )

        return (
            market_price,
            None,
            (
                "Random Forest ML + Dataset "
                "(closest match, unverified)"
            ),
        )

    if (
        result is not None
        and result.get("used_resale_price_inr")
    ):

        return (
            float(
                result["used_resale_price_inr"]
            ),
            result.get("new_price_inr"),
            (
                result.get("source")
                or "Gemini Market Data"
            ),
        )

    market_price = _ml_fallback(
        brand=brand,
        model=model,
        storage=storage,
    )

    return (
        market_price,
        None,
        "Random Forest ML + Dataset",
    )
