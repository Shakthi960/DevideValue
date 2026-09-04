import os
import joblib
import pandas as pd


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "models",
    "price_model.joblib"
)


if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"ML price model not found: {MODEL_PATH}"
    )


model = joblib.load(MODEL_PATH)


FEATURES = [
    "smartphone_brand",
    "model",
    "rating_score",
    "processor_name",
    "processor_brand",
    "core_count",
    "clock_speed_ghz",
    "ram_gb",
    "storage_gb",
    "has_5g",
    "has_nfc",
    "has_ir_blaster",
    "display_inches",
    "res_width_px",
    "res_height_px",
    "refresh_rate_hz",
    "battery_mah",
    "fast_charging",
    "charging_watt",
    "rear_camera_count",
    "front_camera_count",
    "rear_camera_main_mp",
    "front_camera_main_mp",
    "os_name",
    "memory_card_supported",
    "memory_card_type",
]


def predict_price(device_data: dict) -> float:
    """
    Predict the market price of a smartphone.

    device_data must contain the features used
    during model training.
    """

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