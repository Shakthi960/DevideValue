from ml.price_predictor import predict_price_with_details


def calculate_ml_valuation(
    device_data: dict,
    condition_score: float = 100.0
) -> dict:
    """
    Calculate device valuation using the trained ML model
    and physical-condition adjustment.

    condition_score:
        100 = excellent
        0   = extremely poor
    """

    ml_result = predict_price_with_details(device_data)

    base_price = ml_result["predicted_price"]

    # Convert condition score into a multiplier.
    #
    # 100 -> 1.00
    # 90  -> 0.97
    # 80  -> 0.94
    # 70  -> 0.91
    # etc.
    #
    # Maximum adjustment is capped to avoid unrealistic prices.

    condition_multiplier = 0.70 + (
        max(0.0, min(100.0, condition_score)) / 100.0
    ) * 0.30

    resale_price = base_price * condition_multiplier

    # Exchange offers are normally lower than direct resale.
    exchange_price = resale_price * 0.88

    if condition_score >= 95:
        grade = "A+"
    elif condition_score >= 90:
        grade = "A"
    elif condition_score >= 80:
        grade = "B"
    elif condition_score >= 70:
        grade = "C"
    else:
        grade = "D"

    return {
        "base_market_price": round(base_price, 2),
        "condition_score": round(condition_score, 2),
        "condition_multiplier": round(condition_multiplier, 4),
        "resale_price": round(resale_price, 2),
        "exchange_price": round(exchange_price, 2),
        "condition_grade": grade,
        "prediction_source": "ML + Condition Analysis",
        "model_type": ml_result["model_type"],
        "model_version": ml_result["model_version"]
    }