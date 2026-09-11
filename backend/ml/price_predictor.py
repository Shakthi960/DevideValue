import pandas as pd

from ml.model_store import (
    FEATURES,
    get_price_model,
)


def predict_price(device_data: dict) -> float:
    """
    Predict the market price of a smartphone.

    device_data must contain the features used
    during model training.
    """

    model = get_price_model()

    if model is None:
        raise RuntimeError(
            "ML price model is not loaded."
        )

    row = {}

    for feature in FEATURES:
        row[feature] = device_data.get(feature)

    df = pd.DataFrame([row])

    prediction = model.predict(df)[0]

    return round(float(prediction), 2)


def predict_price_with_details(device_data: dict) -> dict:
    """
    Return ML prediction with useful metadata.
    """

    predicted_price = predict_price(device_data)

    return {
        "predicted_price": predicted_price,
        "model_type": "Random Forest Regressor",
        "model_version": "v1",
        "prediction_source": "Machine Learning"
    }