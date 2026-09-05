import json
import os
import re
from datetime import datetime, timedelta

from google import genai
from google.genai import types

from app.core.logger import get_logger
from app.core.database import SessionLocal
from app.models.price_cache import PriceCache
from app.services.valuation import find_device


logger = get_logger(__name__)


genai_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

CACHE_TTL_DAYS = int(
    os.getenv(
        "PRICE_CACHE_TTL_DAYS",
        "30"
    )
)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_key(brand, model, storage):
    parts = [
        brand or "",
        model or "",
        storage or "",
    ]

    cleaned = []

    for part in parts:
        value = part.lower().strip()

        value = re.sub(r"\s+", " ", value)

        cleaned.append(value)

    return "|".join(cleaned)


# ============================================================
# GEMINI STRUCTURED PRICE LOOKUP
# ============================================================

_PRICE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "exists": types.Schema(
            type=types.Type.BOOLEAN
        ),
        "matched_model": types.Schema(
            type=types.Type.STRING
        ),
        "valid_variants": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.STRING
            ),
        ),
        "new_price_inr": types.Schema(
            type=types.Type.INTEGER
        ),
        "used_resale_price_inr": types.Schema(
            type=types.Type.INTEGER
        ),
        "currency": types.Schema(
            type=types.Type.STRING
        ),
        "confidence": types.Schema(
            type=types.Type.STRING
        ),
        "notes": types.Schema(
            type=types.Type.STRING
        ),
    },
    required=[
        "exists",
        "matched_model",
        "valid_variants",
        "new_price_inr",
        "used_resale_price_inr",
        "currency",
        "confidence",
    ],
)


_PRICE_PROMPT = """
You are a smartphone market data assistant for India.

Use current Indian market knowledge to respond about the
phone described below.

BRAND: {brand}
MODEL: {model}
STORAGE VARIANT (user text): {storage}

Steps:

1. Determine whether this smartphone model really exists
   in the Indian market as a distinct phone.

   - If the model name is a real phone (e.g. "Y200e 5G",
     "Galaxy S24"), set exists = true and matched_model
     to its official name only if a clean official name
     exists, otherwise repeat the given model.
   - If the brand/model combination is not a real phone
     (e.g. a made-up name like "S2" with no known device),
     set exists = false and prices to 0.

2. valid_variants: list the real RAM + storage variants
   that exist for this phone in India, formatted like
   "8GB + 128GB". If you are not sure of every variant,
   still include the most common ones you know.

3. new_price_inr: the current launch / street retail price
   of the closest matching variant of this phone in Indian
   rupees. Estimate a reasonable value if out of stock.

4. used_resale_price_inr: the current typical resale value
   of this phone in excellent / open-box used condition in
   Indian rupees.

5. currency must be "INR".

6. confidence must be one of: "high", "medium", "low".

Rules:
- If exists = false, set new_price_inr and
  used_resale_price_inr to 0.
- Only the phone's RAM/storage tier may change the price;
  ignore exact colour.
- Return ONLY valid JSON in the required schema.
"""


def _fetch_gemini(brand, model, storage):
    prompt = _PRICE_PROMPT.format(
        brand=brand or "",
        model=model or "",
        storage=storage or "",
    )

    response = genai_client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=_PRICE_SCHEMA,
        ),
    )

    if not response.text:
        raise ValueError(
            "Gemini returned an empty price response."
        )

    try:
        return json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON for price."
        ) from exc


# ============================================================
# DATASET FALLBACK
# ============================================================

def _dataset_fallback(brand, model, storage):
    try:
        from app.services.valuation import parse_storage

        storage_gb = parse_storage(storage)

        row = find_device(
            brand=brand,
            model=model,
            storage_gb=storage_gb,
        )

        if row is None:
            return None

        recorded = row.get("price_inr")

        if not recorded:
            return None

        recorded = float(recorded)

        return {
            "exists": True,
            "matched_model": str(row.get("model")),
            "valid_variants": [],
            "new_price_inr": int(round(recorded)),
            "used_resale_price_inr": int(round(recorded)),
            "confidence": "medium",
            "notes": "Fallback: matched from local market dataset.",
            "price_source": "dataset",
        }

    except Exception as exc:
        logger.warning(
            "Dataset fallback failed: %s",
            exc
        )

        return None


# ============================================================
# CACHE HELPERS
# ============================================================

def _is_fresh(record):
    if not record.fetched_at:
        return False

    try:

        fetched = datetime.fromisoformat(
            record.fetched_at
        )

        return (
            datetime.now()
            - fetched
        ) < timedelta(
            days=CACHE_TTL_DAYS
        )

    except Exception:
        return False


def _result_from_record(record, source_label):
    return {
        "exists": (
            None
            if not record.exists
            else record.exists == "True"
        ),
        "matched_model": record.matched_model,
        "valid_variants": _parse_variants(
            record.valid_variants
        ),
        "new_price_inr": record.new_price_inr,
        "used_resale_price_inr": (
            record.used_resale_price_inr
        ),
        "confidence": record.confidence,
        "notes": record.notes,
        "price_source": record.price_source,
        "source": source_label,
    }


def _parse_variants(text):
    if not text:
        return []

    try:
        value = json.loads(text)

        return value if isinstance(value, list) else []
    except Exception:
        return []


# ============================================================
# PUBLIC LOOKUP
# ============================================================

def lookup(brand, model, storage, db=None):
    """
    Returns market data for the given phone.

    Order:
      1. DB cache (30 day TTL)
      2. Gemini live structured lookup
      3. Local dataset fallback

    Returns a dict with:
      exists: True / False / None (None = could not verify)
      matched_model: str | None
      valid_variants: list[str]
      new_price_inr: int | None
      used_resale_price_inr: int | None
      confidence: str | None
      notes: str | None
      price_source: "gemini" | "dataset" | None
      source: str (display label)

    Never raises for Gemini failures - it degrades to
    dataset/None so the pipeline can continue.
    """

    key = normalize_key(brand, model, storage)

    result = None

    try:

        session = db or SessionLocal()

        try:

            record = (
                session.query(PriceCache)
                .filter(
                    PriceCache.cache_key == key
                )
                .first()
            )

            if record and _is_fresh(record):
                result = _result_from_record(
                    record,
                    "Gemini Market Data (cached)",
                )

            if result is None:

                gemini_data = None

                try:
                    gemini_data = _fetch_gemini(
                        brand,
                        model,
                        storage,
                    )

                except Exception as exc:
                    logger.warning(
                        "Gemini price lookup failed for "
                        "%s: %s",
                        key,
                        exc,
                    )

                if gemini_data is not None:

                    exists = bool(
                        gemini_data.get("exists")
                    )

                    result = {
                        "exists": exists,
                        "matched_model": (
                            str(
                                gemini_data.get(
                                    "matched_model"
                                )
                                or model
                            )
                            if exists
                            else None
                        ),
                        "valid_variants": (
                            list(
                                gemini_data.get(
                                    "valid_variants"
                                )
                                or []
                            )
                            if exists
                            else []
                        ),
                        "new_price_inr": (
                            _clean_int(
                                gemini_data.get(
                                    "new_price_inr"
                                )
                            )
                            if exists
                            else None
                        ),
                        "used_resale_price_inr": (
                            _clean_int(
                                gemini_data.get(
                                    "used_resale_price_inr"
                                )
                            )
                            if exists
                            else None
                        ),
                        "confidence": (
                            str(
                                gemini_data.get(
                                    "confidence"
                                )
                                or "medium"
                            )
                            if exists
                            else None
                        ),
                        "notes": (
                            str(
                                gemini_data.get("notes")
                                or ""
                            )
                            or None
                        ),
                        "price_source": "gemini",
                        "source": "Gemini Market Data",
                    }

                else:

                    dataset_data = _dataset_fallback(
                        brand,
                        model,
                        storage,
                    )

                    if dataset_data is not None:
                        result = dataset_data
                        result["source"] = (
                            "Local Market Dataset (fallback)"
                        )
                    else:
                        result = {
                            "exists": None,
                            "matched_model": None,
                            "valid_variants": [],
                            "new_price_inr": None,
                            "used_resale_price_inr": None,
                            "confidence": None,
                            "notes": (
                                "Market data currently "
                                "unavailable."
                            ),
                            "price_source": None,
                            "source": "Unavailable",
                        }

                _save_cache(session, key, brand, model, storage, result)

        finally:
            if db is None:
                session.close()

    except Exception as exc:
        logger.error(
            "Price oracle lookup crashed for %s: %s",
            key,
            exc,
        )

        return _dataset_fallback(
            brand,
            model,
            storage,
        )

    return result


def _clean_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _save_cache(session, key, brand, model, storage, result):
    record = (
        session.query(PriceCache)
        .filter(PriceCache.cache_key == key)
        .first()
    )

    if record is None:
        record = PriceCache(cache_key=key)

    record.brand = brand
    record.model = model
    record.storage = storage
    record.exists = (
        None if result["exists"] is None
        else str(result["exists"])
    )
    record.matched_model = result["matched_model"]
    record.valid_variants = json.dumps(
        result["valid_variants"]
    )
    record.new_price_inr = result["new_price_inr"]
    record.used_resale_price_inr = (
        result["used_resale_price_inr"]
    )
    record.price_source = result["price_source"]
    record.confidence = result["confidence"]
    record.notes = result["notes"]
    record.fetched_at = datetime.now().isoformat()

    session.add(record)

    session.commit()