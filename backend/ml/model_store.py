import os

import joblib
import pandas as pd

from app.core.logger import get_logger


logger = get_logger(__name__)


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "ml",
    "models",
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "price_model.joblib",
)

DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "smartphones.csv",
)

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


_price_model = None
_price_model_loaded = False


def get_price_model():
    """Return the trained Random Forest model (loaded once).

    Returns None (instead of raising) when the model file is
    missing or unreadable, so the app can degrade gracefully.
    """

    global _price_model, _price_model_loaded

    if _price_model_loaded:
        return _price_model

    if not os.path.exists(MODEL_PATH):
        logger.warning(
            "Could not load price model: file not found %s",
            MODEL_PATH,
        )
        _price_model_loaded = True
        return None

    try:
        _price_model = joblib.load(MODEL_PATH)
        logger.info("ML price model loaded successfully.")
    except Exception as e:
        logger.warning("Could not load price model: %s", e)
        _price_model = None

    _price_model_loaded = True

    return _price_model


_phone_dataset = None
_phone_dataset_loaded = False


def get_phone_dataset():
    """Return the smartphone dataset (loaded once).

    Returns an empty DataFrame when the CSV is missing or
    unreadable, so the app can degrade gracefully.
    """

    global _phone_dataset, _phone_dataset_loaded

    if _phone_dataset_loaded:
        return _phone_dataset

    try:
        data = pd.read_csv(DATASET_PATH)

        data["smartphone_brand"] = (
            data["smartphone_brand"]
            .astype(str)
            .str.strip()
        )

        data["model"] = (
            data["model"]
            .astype(str)
            .str.strip()
        )

        logger.info(
            "Smartphone dataset loaded: %d rows",
            len(data)
        )

        _phone_dataset = data
    except Exception as e:
        logger.warning(
            "Could not load smartphone dataset: %s",
            e
        )
        _phone_dataset = pd.DataFrame()

    _phone_dataset_loaded = True

    return _phone_dataset