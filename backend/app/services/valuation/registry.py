import re

import pandas as pd

from app.core.logger import get_logger
from ml.model_store import (
    FEATURES as MODEL_FEATURES,
    get_price_model,
    get_phone_dataset,
)


logger = get_logger(__name__)


# ============================================================
# LOAD ML MODEL
# ============================================================

PRICE_MODEL = get_price_model()


# ============================================================
# LOAD SMARTPHONE DATASET
# ============================================================

PHONE_DATA = get_phone_dataset()


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

    value = value.replace("_", " ")

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


def normalize_brand(value):
    value = normalize_text(value)

    aliases = {
        "google pixel": "google",
        "pixel": "google",

        "samsung": "samsung",
        "vivo": "vivo",
        "oppo": "oppo",

        "oneplus": "oneplus",
        "one plus": "oneplus",

        "realme": "realme",

        "xiaomi": "xiaomi",
        "redmi": "xiaomi",

        "poco": "poco",

        "iqoo": "iqoo",
        "i qoo": "iqoo",

        "apple": "apple",

        "motorola": "motorola",
        "moto": "motorola",

        "nothing": "nothing",
        "infinix": "infinix",
        "tecno": "tecno",
        "lava": "lava",
        "itel": "itel",
        "honor": "honor",
        "hmd": "hmd",
        "cmf": "cmf",
        "alcatel": "alcatel",
        "acer": "acer",
        "ulefone": "ulefone",
        "ai+": "ai+",
        "blackzone": "blackzone",
        "peace": "peace",
        "ringme": "ringme",
    }

    return aliases.get(
        value,
        value
    )


def normalize_model(value):
    value = normalize_text(value)

    value = re.sub(
        r"^(apple|samsung|vivo|oppo|realme|xiaomi|"
        r"oneplus|motorola|google|poco|iqoo|"
        r"infinix|tecno|lava|itel|honor|hmd|"
        r"cmf|alcatel|acer)\s+",
        "",
        value
    )

    return value


# ============================================================
# STORAGE PARSER
# ============================================================

def parse_storage(storage):

    if storage is None:
        return None

    value = str(storage).strip().lower()

    # Example: 1 TB
    # (max handles multi-part variants like "6GB + 1TB")
    tb_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*tb",
        value
    )

    if tb_matches:
        return int(
            max(
                float(m) * 1024
                for m in tb_matches
            )
        )

    # Example: 128 GB or "6GB + 128GB"
    # (max picks the storage component, not the RAM)
    gb_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*gb",
        value
    )

    if gb_matches:
        return int(
            max(
                float(m)
                for m in gb_matches
            )
        )

    # Example: 128 or "8 + 256" or "8/256"
    # (no unit given: use the largest number, since the
    #  RAM value is always smaller than the storage)
    matches = re.findall(
        r"\d+",
        value
    )

    if matches:
        return max(
            int(m)
            for m in matches
        )

    return None


# ============================================================
# FIND DEVICE
# ============================================================

def find_device(
    brand,
    model,
    storage_gb=None
):

    if PHONE_DATA.empty:
        return None

    target_brand = normalize_brand(
        brand
    )

    target_model = normalize_model(
        model
    )

    data = PHONE_DATA.copy()

    # --------------------------------------------------------
    # NORMALIZED SEARCH COLUMNS
    # --------------------------------------------------------

    data["_brand_norm"] = (
        data["smartphone_brand"]
        .apply(normalize_brand)
    )

    data["_model_norm"] = (
        data["model"]
        .apply(normalize_model)
    )

    # --------------------------------------------------------
    # 1. EXACT BRAND + MODEL + STORAGE
    # --------------------------------------------------------

    exact = data[
        (data["_brand_norm"] == target_brand)
        &
        (data["_model_norm"] == target_model)
    ]

    if storage_gb is not None:

        exact_storage = exact[
            exact["storage_gb"]
            == storage_gb
        ]

        if not exact_storage.empty:
            return exact_storage.iloc[0]

    # --------------------------------------------------------
    # 2. EXACT BRAND + MODEL
    # --------------------------------------------------------

    if not exact.empty:

        # Prefer closest storage
        if storage_gb is not None:

            exact = exact.copy()

            exact["_storage_distance"] = (
                abs(
                    pd.to_numeric(
                        exact["storage_gb"],
                        errors="coerce"
                    )
                    - storage_gb
                )
            )

            exact = exact.sort_values(
                "_storage_distance"
            )

        return exact.iloc[0]

    # --------------------------------------------------------
    # 3. PARTIAL MODEL MATCH WITH SAME BRAND
    # --------------------------------------------------------

    brand_data = data[
        data["_brand_norm"] == target_brand
    ].copy()

    if not brand_data.empty:

        target_words = set(
            target_model.split()
        )

        candidates = []

        for _, row in brand_data.iterrows():

            row_model = normalize_model(
                row["model"]
            )

            row_words = set(
                row_model.split()
            )

            common_words = len(
                target_words & row_words
            )

            storage_distance = 999999

            if storage_gb is not None:

                try:
                    storage_distance = abs(
                        float(row["storage_gb"])
                        - storage_gb
                    )
                except Exception:
                    pass

            candidates.append(
                (
                    common_words,
                    -storage_distance,
                    row
                )
            )

        candidates.sort(
            key=lambda x: (
                x[0],
                x[1]
            ),
            reverse=True
        )

        if candidates:

            # Only use partial match when
            # at least one model word matches.
            if candidates[0][0] > 0:
                return candidates[0][2]

    # --------------------------------------------------------
    # 4. SAME BRAND + CLOSEST STORAGE
    #
    # This is the important fallback.
    #
    # A phone can exist in the device catalog while its
    # exact model is absent from smartphones.csv.
    #
    # Instead of failing valuation, use the closest
    # specification from the same brand and storage class.
    # --------------------------------------------------------

    if not brand_data.empty:

        if storage_gb is not None:

            brand_data = brand_data.copy()

            brand_data["_storage_distance"] = (
                abs(
                    pd.to_numeric(
                        brand_data["storage_gb"],
                        errors="coerce"
                    )
                    - storage_gb
                )
            )

            brand_data = brand_data.sort_values(
                "_storage_distance"
            )

        return brand_data.iloc[0]

    # --------------------------------------------------------
    # 5. LAST FALLBACK
    # --------------------------------------------------------

    if storage_gb is not None:

        data["_storage_distance"] = (
            abs(
                pd.to_numeric(
                    data["storage_gb"],
                    errors="coerce"
                )
                - storage_gb
            )
        )

        data = data.sort_values(
            "_storage_distance"
        )

    if not data.empty:
        return data.iloc[0]

    return None


# ============================================================
# BUILD ML INPUT
# ============================================================

def build_ml_input(
    device_row,
    brand,
    model,
    storage_gb
):

    row = device_row.copy()

    # --------------------------------------------------------
    # USER SELECTED BRAND
    # --------------------------------------------------------

    row["smartphone_brand"] = brand

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Use the dataset model for specification lookup.
    # This prevents an unknown model from breaking the
    # trained categorical encoder.
    # --------------------------------------------------------

    row["model"] = device_row["model"]

    # --------------------------------------------------------
    # USER SELECTED STORAGE
    # --------------------------------------------------------

    if storage_gb is not None:
        row["storage_gb"] = storage_gb

    values = {}

    # --------------------------------------------------------
    # GET ALL FEATURES
    # --------------------------------------------------------

    for feature in MODEL_FEATURES:

        if feature in row.index:
            values[feature] = row[feature]
        else:
            values[feature] = 0

    frame = pd.DataFrame(
        [values]
    )

    # --------------------------------------------------------
    # CATEGORICAL FEATURES
    # --------------------------------------------------------

    categorical_columns = [
        "smartphone_brand",
        "model",
        "processor_name",
        "processor_brand",
        "os_name",
        "memory_card_type",
    ]

    # --------------------------------------------------------
    # NUMERIC FEATURES
    # --------------------------------------------------------

    numeric_columns = [
        feature
        for feature in MODEL_FEATURES
        if feature not in categorical_columns
    ]

    for column in numeric_columns:

        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce"
        )

        frame[column] = (
            frame[column]
            .fillna(0)
        )

    # --------------------------------------------------------
    # CLEAN CATEGORICAL VALUES
    # --------------------------------------------------------

    for column in categorical_columns:

        frame[column] = (
            frame[column]
            .fillna("")
            .astype(str)
        )

    return frame[
        MODEL_FEATURES
    ]


# ============================================================
# ML MARKET PRICE
# ============================================================

def predict_market_price(
    brand,
    model,
    storage
):

    storage_gb = parse_storage(
        storage
    )

    if PRICE_MODEL is None:

        raise RuntimeError(
            "ML price model is not loaded."
        )

    if PHONE_DATA.empty:

        raise RuntimeError(
            "Smartphone dataset is not loaded."
        )

    # --------------------------------------------------------
    # FIND SPECIFICATION ROW
    # --------------------------------------------------------

    device_row = find_device(
        brand=brand,
        model=model,
        storage_gb=storage_gb
    )

    if device_row is None:

        raise ValueError(
            f"Unable to find specification "
            f"data for {brand} {model}."
        )

    # --------------------------------------------------------
    # BUILD MODEL INPUT
    # --------------------------------------------------------

    model_input = build_ml_input(
        device_row=device_row,
        brand=brand,
        model=model,
        storage_gb=storage_gb
    )

    # --------------------------------------------------------
    # RANDOM FOREST PREDICTION
    # --------------------------------------------------------

    prediction = PRICE_MODEL.predict(
        model_input
    )

    ml_price = float(
        prediction[0]
    )

    # --------------------------------------------------------
    # GROUND TO REAL MARKET DATA
    # --------------------------------------------------------
    # The dataset holds the real recorded market price for the
    # matched device. Blend it with the ML prediction so the
    # estimate stays anchored to actual market data and is not
    # distorted by a noisy single prediction.

    recorded_price = float(
        device_row.get("price_inr")
        or 0
    )

    if recorded_price > 0:
        # Keep the ML prediction within a sane band around the
        # real recorded market price so rare/extrapolated
        # variants cannot dominate the estimate.
        ml_price = max(
            recorded_price * 0.5,
            min(
                ml_price,
                recorded_price * 1.5
            )
        )

        price = (ml_price + recorded_price) / 2
    else:
        price = ml_price

    # --------------------------------------------------------
    # SAFETY LIMIT
    # --------------------------------------------------------

    price = max(
        500,
        price
    )

    return round(
        price
    )
