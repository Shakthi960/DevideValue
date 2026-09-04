import re
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "smartphones.csv"
)

OUTPUT_DIR = BASE_DIR / "data"

OUTPUT_FILE = (
    OUTPUT_DIR
    / "device_catalog_clean.csv"
)


# ---------------------------------------------------------
# Allowed values
# ---------------------------------------------------------

VALID_RAM = {
    2,
    3,
    4,
    6,
    8,
    12,
    16,
    24,
    32,
}

VALID_STORAGE = {
    32,
    64,
    128,
    256,
    512,
    1024,
    2048,
}


# ---------------------------------------------------------
# Brand normalization
# ---------------------------------------------------------

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
    "ai+": "AI+",
    "ulefone": "Ulefone",
    "blackzone": "Blackzone",
    "peace": "Peace",
    "ringme": "Ringme",
}


# ---------------------------------------------------------
# Model cleaning
# ---------------------------------------------------------

def clean_model(value, brand):
    if pd.isna(value):
        return None

    model = str(value).strip()

    # Normalize whitespace
    model = re.sub(
        r"\s+",
        " ",
        model
    )

    # Remove leading brand name.
    # Example:
    # "Apple iPhone 15" -> "iPhone 15"
    # "Vivo Y200e 5G" -> "Y200e 5G"
    if brand:
        pattern = (
            r"^"
            + re.escape(brand)
            + r"\s+"
        )

        model = re.sub(
            pattern,
            "",
            model,
            flags=re.IGNORECASE
        )

    # Remove RAM information from model name.
    #
    # Example:
    # "Nova 5G (8GB RAM + 128GB)"
    # ->
    # "Nova 5G"
    model = re.sub(
        r"\s*\(\s*\d+\s*GB\s*RAM.*?\)",
        "",
        model,
        flags=re.IGNORECASE
    )

    # Remove RAM + storage information from model name.
    #
    # Examples:
    # "Y29 5G (6GB+128GB)" -> "Y29 5G"
    # "Phone (8GB + 256GB)" -> "Phone"
    model = re.sub(
        r"\s*\(\s*\d+\s*GB\s*\+\s*\d+\s*(?:GB|TB)\s*\)",
        "",
        model,
        flags=re.IGNORECASE
    )

    # Remove processor + RAM/storage information
    #
    # Example:
    # "Galaxy S21 FE (Snapdragon + 8GB RAM + 128GB)"
    # -> "Galaxy S21 FE"
    #
    # "Galaxy S24 5G (Snapdragon +256GB)"
    # -> "Galaxy S24 5G"
    model = re.sub(
        r"\s*\(\s*[^)]*(?:\d+\s*GB\s*RAM|\d+\s*(?:GB|TB))[^)]*\)",
        "",
        model,
        flags=re.IGNORECASE
    )

    # Remove storage information from model name.
    #
    # Example:
    # "iPhone 15 (256GB)"
    # ->
    # "iPhone 15"
    model = re.sub(
        r"\s*\(\s*\d+\s*(?:GB|TB)\s*\)",
        "",
        model,
        flags=re.IGNORECASE
    )

    # Remove common RAM/storage suffixes.
    model = re.sub(
        r"\s*\(\s*\d+\s*GB\s*/\s*\d+\s*GB\s*\)",
        "",
        model,
        flags=re.IGNORECASE
    )

    # Clean leftover spaces
    model = re.sub(
        r"\s+",
        " ",
        model
    ).strip()

    return model


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    print("Loading smartphone dataset...")

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Original rows: {len(df)}"
    )

    # -----------------------------------------------------
    # Validate columns
    # -----------------------------------------------------

    required_columns = {
        "smartphone_brand",
        "model",
        "ram_gb",
        "storage_gb",
    }

    missing = (
        required_columns
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Missing columns: "
            + ", ".join(sorted(missing))
        )

    # -----------------------------------------------------
    # Select columns
    # -----------------------------------------------------

    df = df[
        [
            "smartphone_brand",
            "model",
            "ram_gb",
            "storage_gb",
        ]
    ].copy()

    # -----------------------------------------------------
    # Rename
    # -----------------------------------------------------

    df = df.rename(
        columns={
            "smartphone_brand": "brand",
            "ram_gb": "ram",
            "storage_gb": "storage",
        }
    )

    # -----------------------------------------------------
    # Normalize brand
    # -----------------------------------------------------

    df["brand"] = (
        df["brand"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(BRAND_MAP)
    )

    # -----------------------------------------------------
    # Clean model
    # -----------------------------------------------------

    df["model"] = df.apply(
        lambda row: clean_model(
            row["model"],
            row["brand"]
        ),
        axis=1
    )

    # -----------------------------------------------------
    # Convert RAM/storage
    # -----------------------------------------------------

    df["ram"] = pd.to_numeric(
        df["ram"],
        errors="coerce"
    )

    df["storage"] = pd.to_numeric(
        df["storage"],
        errors="coerce"
    )

    # -----------------------------------------------------
    # Remove missing values
    # -----------------------------------------------------

    df = df.dropna(
        subset=[
            "brand",
            "model",
            "ram",
            "storage",
        ]
    )

    # -----------------------------------------------------
    # Validate RAM
    # -----------------------------------------------------

    df = df[
        df["ram"].isin(VALID_RAM)
    ]

    # -----------------------------------------------------
    # Validate storage
    # -----------------------------------------------------

    df = df[
        df["storage"].isin(
            VALID_STORAGE
        )
    ]

    # -----------------------------------------------------
    # Integer conversion
    # -----------------------------------------------------

    df["ram"] = df["ram"].astype(int)

    df["storage"] = (
        df["storage"].astype(int)
    )

    # -----------------------------------------------------
    # Variant name
    # -----------------------------------------------------

    def create_variant(row):

        return (
            f"{row['ram']}GB + "
            f"{row['storage']}GB"
        )

    df["variant_name"] = df.apply(
        create_variant,
        axis=1
    )

    # -----------------------------------------------------
    # Remove duplicate variants
    # -----------------------------------------------------

    df = df.drop_duplicates(
        subset=[
            "brand",
            "model",
            "ram",
            "storage",
        ]
    )

    # -----------------------------------------------------
    # Sort
    # -----------------------------------------------------

    df = df.sort_values(
        by=[
            "brand",
            "model",
            "ram",
            "storage",
        ]
    )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print()
    print(
        f"Clean rows: {len(df)}"
    )

    print(
        f"Brands: {df['brand'].nunique()}"
    )

    print(
        f"Models: {df['model'].nunique()}"
    )

    print()
    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "Brands:"
    )

    print(
        df["brand"]
        .value_counts()
        .sort_index()
        .to_string()
    )


if __name__ == "__main__":
    main()