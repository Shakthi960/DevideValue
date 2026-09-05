import os
import re
import joblib
import pandas as pd

from app.core.logger import get_logger


logger = get_logger(__name__)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "models",
    "price_model.joblib"
)

DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "smartphones.csv"
)


# ============================================================
# LOAD ML MODEL
# ============================================================

try:
    PRICE_MODEL = joblib.load(MODEL_PATH)
    logger.info("ML price model loaded successfully.")
except Exception as e:
    PRICE_MODEL = None
    logger.warning("Could not load price model: %s", e)


# ============================================================
# LOAD SMARTPHONE DATASET
# ============================================================

try:
    PHONE_DATA = pd.read_csv(DATASET_PATH)

    PHONE_DATA["smartphone_brand"] = (
        PHONE_DATA["smartphone_brand"]
        .astype(str)
        .str.strip()
    )

    PHONE_DATA["model"] = (
        PHONE_DATA["model"]
        .astype(str)
        .str.strip()
    )

    logger.info(
        "Smartphone dataset loaded: %d rows",
        len(PHONE_DATA)
    )

except Exception as e:
    PHONE_DATA = pd.DataFrame()

    logger.warning(
        "Could not load smartphone dataset: %s",
        e
    )


# ============================================================
# ML FEATURES
# ============================================================

MODEL_FEATURES = [
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

        raise ValueError(
            f"Couldn't verify '{model}'. "
            f"Check the spelling or pick it from "
            f"the device list."
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

    market_price = predict_market_price(
        brand=brand,
        model=model,
        storage=storage,
    )

    return (
        market_price,
        None,
        "Random Forest ML + Dataset",
    )


# ============================================================
# CONDITION SCORE
# ============================================================

def calculate_condition_score(
    answers
):

    score = 100

    # ========================================================
    # AGE
    # ========================================================

    age = normalize_text(
        answers.get("age")
        or answers.get("device_age")
        or answers.get("purchase_age")
    )

    age_deductions = {

        "less than 6 months": 0,
        "0-6 months": 0,

        "6 to 12 months": 5,
        "6-12 months": 5,

        "1 year": 8,

        "1 to 2 years": 12,
        "1-2 years": 12,

        "2 years": 18,

        "2 to 3 years": 25,
        "2-3 years": 25,

        "3+ years": 32,
        "more than 3 years": 32,
    }

    score -= age_deductions.get(
        age,
        0
    )

    # ========================================================
    # SCREEN
    # ========================================================

    screen = normalize_text(
        answers.get("screen")
        or answers.get("screen_condition")
    )

    screen_deductions = {

        "excellent": 0,
        "like new": 0,

        "good": 5,

        "minor scratches": 8,

        "scratched": 12,

        "cracked": 30,

        "broken": 40,

        "display problem": 40,
    }

    score -= screen_deductions.get(
        screen,
        0
    )

    # ========================================================
    # BODY
    # ========================================================

    body = normalize_text(
        answers.get("body")
        or answers.get("body_condition")
    )

    body_deductions = {

        "excellent": 0,
        "like new": 0,

        "good": 5,

        "minor scratches": 8,

        "scratches": 10,
        "multiple scratches": 10,

        "dents": 18,
        "minor dents": 18,

        "heavy damage": 30,
        "major damage": 30,

        "broken": 40,
    }

    score -= body_deductions.get(
        body,
        0
    )

    # ========================================================
    # BATTERY
    # ========================================================

    battery = normalize_text(
        answers.get("battery")
        or answers.get("battery_health")
        or answers.get("battery_condition")
    )

    battery_deductions = {

        "excellent": 0,

        "good": 3,

        "80-100%": 3,

        "70-80%": 8,
        "below 80": 8,

        "below 70%": 15,
        "poor": 15,

        "replaced": 5,
    }

    score -= battery_deductions.get(
        battery,
        0
    )

    # ========================================================
    # FUNCTIONALITY
    # ========================================================

    functionality = normalize_text(
        answers.get("functionality")
        or answers.get("working_condition")
    )

    functionality_deductions = {

        "fully working": 0,
        "everything works": 0,
        "good": 0,
        "yes": 0,

        "minor issues": 10,
        "not sure": 5,

        "some issues": 15,
        "no": 15,

        "major issues": 30,

        "not working": 50,
    }

    score -= functionality_deductions.get(
        functionality,
        0
    )

    # ========================================================
    # ACCESSORIES
    # ========================================================

    charger = normalize_text(
        answers.get("original_charger")
        or answers.get("accessories")
        or answers.get("charger_box")
        or answers.get("charger")
    )

    box = normalize_text(
        answers.get("original_box")
    )

    if box == "yes" and charger == "yes":

        score += 2

    elif charger == "yes":

        score += 0

    elif box == "yes":

        score += 0

    else:

        score -= 3

    # ========================================================
    # REPAIR HISTORY
    # ========================================================

    repair = normalize_text(
        answers.get("repair_history")
        or answers.get("repair")
        or answers.get("repair_status")
    )

    if repair in [
        "no",
        "no repairs",
        "none",
    ]:

        score += 0

    elif repair in [
        "authorized",
        "authorized service",
        "yes authorized service",
    ]:

        score -= 5

    elif repair in [
        "third party",
        "third-party service",
        "yes third party service",
    ]:

        score -= 12

    elif repair in [
        "unknown",
        "i don't know",
    ]:

        score -= 3

    # ========================================================
    # FINAL RANGE
    # ========================================================

    return max(
        0,
        min(
            100,
            score
        )
    )


# ============================================================
# CONDITION GRADE
# ============================================================

def get_condition_grade(
    score
):

    if score >= 90:
        return "A+"

    if score >= 80:
        return "A"

    if score >= 70:
        return "B"

    if score >= 60:
        return "C"

    return "D"


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

    condition_multiplier = {

        "A+": 1.00,

        "A": 0.94,

        "B": 0.86,

        "C": 0.75,

        "D": 0.60,
    }

    multiplier = condition_multiplier[
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
        * 0.88
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