from app.services.valuation.condition import (
    EXCHANGE_RATE,
    GRADE_MULTIPLIERS,
    calculate_condition_score,
    get_condition_grade,
)
from app.services.valuation.market import get_market_price


# ============================================================
# FINAL VALUATION
# ============================================================

def calculate_valuation(
    brand,
    model,
    storage,
    answers
):

    # ========================================================
    # 1. ML MARKET PRICE
    # ========================================================

    market_price, new_price_inr, price_source = (
        get_market_price(
            brand=brand,
            model=model,
            storage=storage
        )
    )

    # ========================================================
    # 2. CONDITION SCORE
    # ========================================================

    condition_score = calculate_condition_score(
        answers
    )

    # ========================================================
    # 3. CONDITION GRADE
    # ========================================================

    condition_grade = get_condition_grade(
        condition_score
    )

    # ========================================================
    # 4. CONDITION MULTIPLIER
    # ========================================================

    multiplier = GRADE_MULTIPLIERS[
        condition_grade
    ]

    # ========================================================
    # 5. FINAL RESALE PRICE
    # ========================================================

    resale_price = round(
        market_price
        * multiplier
    )

    # ========================================================
    # 6. EXCHANGE PRICE
    # ========================================================

    exchange_price = round(
        resale_price
        * EXCHANGE_RATE
    )

    # ========================================================
    # RESULT
    # ========================================================

    return {

        "market_price": market_price,

        "new_price_inr": new_price_inr,

        "resale_price": resale_price,

        "exchange_price": exchange_price,

        "condition_score": condition_score,

        "condition_grade": condition_grade,

        "device": {
            "brand": brand,
            "model": model,
            "storage": storage,
        },

        "model_source": price_source,

        "price_source": price_source,

        "valuation_type": "ML + Condition Adjustment",
    }
