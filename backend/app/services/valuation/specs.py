"""Device specification matching against the committed dataset.

The DEVICE VALUE model needs a full specification row (processor,
cores, display, camera, ...) for the phone being valued. That
row does not come from the user's answers - it comes from
matching the user's brand/model/storage against
`data/smartphones.csv`.

This module is the redesign's answer to the problem that the
old code solved with `registry.py`'s `find_device` +
`build_ml_input`. It is split out so the matching concern and
the condition-building concern stay independent.

Matching strategy, most specific first:
  1. brand + model + storage exact
  2. brand + model, nearest storage
  3. brand + partial model-word overlap, nearest storage
  4. brand + nearest storage
  5. nearest storage anywhere
"""

import re

import pandas as pd

from app.core.logger import get_logger
from ml.feature_schema import (
    SPEC_FEATURES,
)


logger = get_logger(__name__)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

_BRAND_ALIASES = {
    "google pixel": "google",
    "pixel": "google",
    "one plus": "oneplus",
    "redmi": "xiaomi",
    "moto": "motorola",
    "i qoo": "iqoo",
}


_BRAND_PREFIXES = re.compile(
    r"^(apple|samsung|vivo|oppo|realme|xiaomi|"
    r"oneplus|one plus|motorola|google|pixel|"
    r"poco|iqoo|infinix|tecno|lava|itel|honor|"
    r"hmd|cmf|alcatel|acer|nothing|"
    r"ulefone|ai\+|blackzone|peace|ringme)\s+"
)


def normalize_text(value):
    if value is None:
        return ""

    text = str(value).strip().lower()

    text = text.replace("_", " ")

    return re.sub(r"\s+", " ", text)


def normalize_brand(value):
    text = normalize_text(value)

    return _BRAND_ALIASES.get(text, text)


def normalize_model(value):
    text = normalize_text(value)

    return _BRAND_PREFIXES.sub("", text)


def parse_storage(storage):
    """Extract storage capacity in GB from free-form text.

    Handles "128GB", "1 TB", "6GB + 128GB" and "8/256".
    For compound strings the largest capacity wins, because the
    RAM figure is always the smaller number.
    """

    if storage is None:
        return None

    text = str(storage).strip().lower()

    tb_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*tb",
        text,
    )

    if tb_matches:
        return int(
            max(
                float(value) * 1024
                for value in tb_matches
            )
        )

    gb_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*gb",
        text,
    )

    if gb_matches:
        return int(
            max(
                float(value)
                for value in gb_matches
            )
        )

    numbers = re.findall(r"\d+", text)

    if numbers:
        return max(
            int(number)
            for number in numbers
        )

    return None


def parse_ram(storage):
    """Best-effort RAM extraction in GB from variant text.

    Only used when the matched dataset row lacks RAM. Patterns
    like "6GB + 128GB" or "8/256" put the smaller number first.
    """

    if storage is None:
        return None

    text = str(storage).strip().lower()

    explicit = re.search(
        r"(\d+(?:\.\d+)?)\s*gb\s*ram",
        text,
    )

    if explicit:
        return int(float(explicit.group(1)))

    pairs = re.findall(
        r"(\d+(?:\.\d+)?)\s*gb\s*\+\s*\d+",
        text,
    )

    if pairs:
        return int(
            float(
                pairs[0].replace("gb", "")
                .replace("+", "")
                .strip()
            )
        )

    numbers = re.findall(r"\d+", text)

    if len(numbers) >= 2:
        ordered = sorted(
            int(number)
            for number in numbers
        )

        return ordered[0]

    return None


# ============================================================
# MATCHING
# ============================================================

def find_spec_row(
    dataset,
    brand,
    model,
    storage_gb=None
):
    """Locate the best specification row. See module docstring."""

    if dataset is None or len(dataset) == 0:
        return None

    target_brand = normalize_brand(brand)
    target_model = normalize_model(model)

    frame = dataset.copy()

    frame["_brand"] = frame[
        "smartphone_brand"
    ].apply(normalize_brand)

    frame["_model"] = frame["model"].apply(
        normalize_model
    )

    # 1. exact brand + model + storage

    exact = frame[
        (frame["_brand"] == target_brand)
        & (frame["_model"] == target_model)
    ]

    if storage_gb is not None and not exact.empty:

        match = exact[
            pd.to_numeric(
                exact["storage_gb"],
                errors="coerce",
            )
            == storage_gb
        ]

        if not match.empty:
            return match.iloc[0]

    # 2. exact brand + model, nearest storage

    if not exact.empty:
        return _nearest_storage(exact, storage_gb)

    # 3. partial model overlap within the brand

    brand_rows = frame[frame["_brand"] == target_brand]

    if not brand_rows.empty:

        target_words = set(target_model.split())

        scored = []

        for _, row in brand_rows.iterrows():

            row_words = set(
                normalize_model(row["model"]).split()
            )

            overlap = len(
                target_words & row_words
            )

            if overlap == 0:
                continue

            distance = _storage_distance(
                row,
                storage_gb,
            )

            scored.append(
                (overlap, -distance, row)
            )

        if scored:

            scored.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                ),
                reverse=True,
            )

            return scored[0][2]

        # 4. same brand, nearest storage

        return _nearest_storage(
            brand_rows,
            storage_gb,
        )

    # 5. nearest storage anywhere

    return _nearest_storage(frame, storage_gb)


def _storage_distance(row, storage_gb):
    if storage_gb is None:
        return -1.0

    value = pd.to_numeric(
        pd.Series([row.get("storage_gb")]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(value):
        return 999999.0

    return abs(float(value) - float(storage_gb))


def _nearest_storage(frame, storage_gb):
    if storage_gb is None:
        return frame.iloc[0]

    frame = frame.copy()

    frame["_distance"] = frame.apply(
        lambda row: _storage_distance(row, storage_gb),
        axis=1,
    )

    frame = frame.sort_values("_distance")

    return frame.iloc[0]


# ============================================================
# FEATURE ROW ASSEMBLY
# ============================================================

def build_spec_features(
    dataset,
    brand,
    model,
    storage,
    matched_row=None
):
    """Build the specification half of the feature row.

    matched_row:
        Optional pre-matched dataset row (lets the caller match
        once and reuse the result across several flows).

    Brand and storage are overridden with the USER's values, so
    a phone registered in the catalog under a variant the
    dataset lacks is still priced at the variant asked for.

    `model` is deliberately taken from the dataset row: the
    categorical encoder was fitted on real model names, and an
    invented name would fall into the unknown-category bucket
    and lose all model-level signal.
    """

    storage_gb = parse_storage(storage)

    if matched_row is None:
        matched_row = find_spec_row(
            dataset,
            brand=brand,
            model=model,
            storage_gb=storage_gb,
        )

    row = {}

    if matched_row is not None:

        for feature in SPEC_FEATURES:

            row[feature] = (
                matched_row.get(feature)
                if feature in matched_row.index
                else None
            )

        row["model"] = matched_row.get("model")

    else:

        logger.warning(
            "No specification row found for %s %s %s; "
            "specification features will be sparse.",
            brand,
            model,
            storage,
        )

        row["smartphone_brand"] = brand
        row["model"] = model

    # User-supplied identity wins over the matched row.
    row["smartphone_brand"] = brand

    if storage_gb is not None:
        row["storage_gb"] = storage_gb

    if row.get("ram_gb") in (None, 0):

        parsed_ram = parse_ram(storage)

        if parsed_ram is not None:
            row["ram_gb"] = parsed_ram

    return row, matched_row


def reference_price(matched_row):
    """Recorded market price of the matched row, in rupees.

    Used only for reporting context and for the confidence
    signal. It is NOT multiplied into the model's output.
    """

    if matched_row is None:
        return None

    value = matched_row.get("price_inr")

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None