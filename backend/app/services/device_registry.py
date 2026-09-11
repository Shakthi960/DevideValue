import os
import re
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.models.device_catalog import DeviceCatalog
from app.models.price_cache import PriceCache
from ml.model_store import DATASET_PATH


logger = get_logger(__name__)


BRAND_MAP = {
    "samsung": "Samsung",
    "apple": "Apple",
    "realme": "Realme",
    "oppo": "Oppo",
    "vivo": "Vivo",
    "xiaomi": "Xiaomi",
    "motorola": "Motorola",
    "poco": "POCO",
    "iqoo": "iQOO",
    "oneplus": "OnePlus",
    "infinix": "Infinix",
    "tecno": "Tecno",
    "nothing": "Nothing",
    "google": "Google",
    "honor": "Honor",
    "itel": "Itel",
    "lava": "Lava",
    "hmd": "HMD",
    "cmf": "CMF",
    "alcatel": "Alcatel",
    "acer": "Acer",
    "ulefone": "Ulefone",
    "ai+": "AI+",
    "blackzone": "Blackzone",
    "peace": "Peace",
    "ringme": "Ringme",
}


def normalize_brand(value):
    if not value:
        return None

    key = str(value).strip().lower()

    key = re.sub(r"\s+", " ", key)

    return BRAND_MAP.get(key, str(value).strip())


def clean_model(value, brand=None):
    if not value:
        return ""

    model = str(value).strip()

    model = re.sub(r"\s+", " ", model)

    if brand:
        pattern = r"^" + re.escape(brand) + r"\s+"
        model = re.sub(pattern, "", model, flags=re.IGNORECASE)

    model = re.sub(
        r"\s*\(\s*\d+\s*GB\s*RAM.*?\)",
        "",
        model,
        flags=re.IGNORECASE,
    )

    model = re.sub(
        r"\s*\(\s*\d+\s*GB\s*\+\s*\d+\s*(?:GB|TB)\s*\)",
        "",
        model,
        flags=re.IGNORECASE,
    )

    model = re.sub(
        r"\s*\(\s*\d+\s*(?:GB|TB)\s*\)",
        "",
        model,
        flags=re.IGNORECASE,
    )

    model = re.sub(r"\s+", " ", model).strip()

    return model


def parse_ram_storage(value):
    matches = re.findall(r"\d+", str(value or ""))

    numbers = [
        int(m)
        for m in matches
        if int(m) > 0
    ]

    if not numbers:
        raise ValueError(
            "Variant must include RAM and storage, "
            'e.g. "8GB + 128GB" or "8+128".'
        )

    if len(numbers) == 1:
        raise ValueError(
            "Variant must include both RAM and storage, "
            'e.g. "8GB + 128GB" or "8+128".'
        )

    numbers.sort()

    return numbers[0], numbers[-1]


def _dataset_row_exists(df, brand, model, storage_gb):
    if df.empty:
        return False

    target_brand = str(brand).strip().lower()
    target_model = str(model).strip().lower()

    for _, row in df.iterrows():
        try:
            row_brand = str(row["smartphone_brand"]).strip().lower()
            row_model = str(row["model"]).strip().lower()
            row_storage = int(float(row["storage_gb"]))
        except Exception:
            continue

        if (
            row_brand == target_brand
            and row_model == target_model
            and row_storage == storage_gb
        ):
            return True

    return False


def _append_dataset_row(brand, model, storage_gb, ram_gb, price_inr):
    if not os.path.exists(DATASET_PATH):
        logger.warning(
            "Dataset not found: %s",
            DATASET_PATH,
        )
        return False

    df = pd.read_csv(DATASET_PATH)

    if _dataset_row_exists(df, brand, model, storage_gb):
        return False

    row = {
        "smartphone_brand": str(brand).strip().lower(),
        "model": str(model).strip(),
        "price_inr": price_inr,
        "ram_gb": ram_gb,
        "storage_gb": storage_gb,
    }

    for column in df.columns:
        if column not in row:
            row[column] = None

    df = pd.concat(
        [df, pd.DataFrame([row])],
        ignore_index=True,
    )

    df.to_csv(DATASET_PATH, index=False)

    return True


def _cache_key(brand, model, storage):
    parts = []
    for part in (brand, model, storage):
        value = re.sub(r"\s+", " ", str(part or "").strip().lower())
        parts.append(value)
    return "|".join(parts)


def _upsert_price_cache(db, brand, model, storage, price_inr):
    if price_inr is None:
        return False

    key = _cache_key(brand, model, storage)

    record = (
        db.query(PriceCache)
        .filter(PriceCache.cache_key == key)
        .first()
    )

    if record is None:
        record = PriceCache(cache_key=key)

    record.brand = brand
    record.model = model
    record.storage = storage
    record.exists = "True"
    record.matched_model = model
    record.valid_variants = "[]"
    record.new_price_inr = price_inr
    record.used_resale_price_inr = price_inr
    record.price_source = "custom"
    record.confidence = "low"
    record.notes = "Manually added device with ML-estimated price."
    record.fetched_at = datetime.now().isoformat()

    db.add(record)
    db.commit()

    return True


def _estimate_price(brand, model, storage):
    try:
        from app.services.valuation import predict_market_price

        return int(predict_market_price(brand, model, storage))
    except Exception as exc:
        logger.warning(
            "Price estimate failed for %s %s: %s",
            brand,
            model,
            exc,
        )
        return None


def register_device(
    db: Session,
    brand,
    model,
    storage,
    new_price_inr=None,
    release_date=None,
):
    """
    Add a new device to the platform so future valuations
    (and the ML price model) can recognize it.

    Steps:
      1. Normalize and validate input.
      2. Upsert into the device_catalog table (dropdowns).
      3. Append to smartphones.csv (dataset / retraining source).
      4. Upsert into the price_cache table so the price oracle
         returns a value immediately.
    """

    canonical_brand = normalize_brand(brand)

    if not canonical_brand:
        raise ValueError("Brand is required.")

    clean_model_name = clean_model(model, canonical_brand)

    if not clean_model_name:
        raise ValueError("Model is required.")

    ram_gb, storage_gb = parse_ram_storage(storage)

    if storage_gb is None or storage_gb <= 0:
        raise ValueError("A valid storage size is required.")

    price = new_price_inr

    if price is not None and price < 0:
        raise ValueError("Price cannot be negative.")

    variant_name = f"{ram_gb}GB + {storage_gb}GB"

    # ---------------------------------------------------------
    # 1. Device catalog table (drives the dropdown selectors)
    # ---------------------------------------------------------

    added_catalog = False

    existing = (
        db.query(DeviceCatalog)
        .filter(
            DeviceCatalog.brand == canonical_brand,
            DeviceCatalog.model == clean_model_name,
            DeviceCatalog.ram == f"{ram_gb}GB",
            DeviceCatalog.storage == f"{storage_gb}GB",
        )
        .first()
    )

    if existing is None:
        record = DeviceCatalog(
            brand=canonical_brand,
            model=clean_model_name,
            ram=f"{ram_gb}GB",
            storage=f"{storage_gb}GB",
            variant_name=variant_name,
            release_date=release_date,
        )

        db.add(record)
        db.commit()

        added_catalog = True

    # ---------------------------------------------------------
    # 2. ML dataset (smartphones.csv) for future retraining
    # ---------------------------------------------------------

    added_dataset = _append_dataset_row(
        brand=canonical_brand,
        model=clean_model_name,
        storage_gb=storage_gb,
        ram_gb=ram_gb,
        price_inr=price,
    )

    # ---------------------------------------------------------
    # 3. Price estimate + price cache for immediate lookups
    # ---------------------------------------------------------

    if price is None:
        price = _estimate_price(
            canonical_brand,
            clean_model_name,
            f"{ram_gb}GB + {storage_gb}GB",
        )

    cached = _upsert_price_cache(
        db,
        canonical_brand,
        clean_model_name,
        f"{ram_gb}GB + {storage_gb}GB",
        price,
    )

    logger.info(
        "Registered device %s %s (%s) catalog=%s dataset=%s cached=%s",
        canonical_brand,
        clean_model_name,
        variant_name,
        added_catalog,
        added_dataset,
        cached,
    )

    return {
        "brand": canonical_brand,
        "model": clean_model_name,
        "ram_gb": ram_gb,
        "storage_gb": storage_gb,
        "storage": variant_name,
        "price_inr": price,
        "added_catalog": added_catalog,
        "added_dataset": added_dataset,
        "price_cached": cached,
    }