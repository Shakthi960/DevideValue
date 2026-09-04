import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(BASE_DIR)
)

import pandas as pd

from app.core.database import SessionLocal
from app.models.device_catalog import DeviceCatalog


CSV_FILE = (
    BASE_DIR
    / "data"
    / "device_catalog_clean.csv"
)


def main():

    print("Loading clean device catalog...")

    df = pd.read_csv(CSV_FILE)

    print(
        f"Rows found: {len(df)}"
    )

    db = SessionLocal()

    try:

        # -------------------------------------------------
        # Clear only the catalog table
        # -------------------------------------------------

        print(
            "Clearing existing device catalog..."
        )

        db.query(DeviceCatalog).delete()

        db.commit()

        # -------------------------------------------------
        # Insert catalog
        # -------------------------------------------------

        records = []

        for _, row in df.iterrows():

            record = DeviceCatalog(
                brand=str(row["brand"]),
                model=str(row["model"]),
                ram=str(int(row["ram"])) + "GB",
                storage=str(int(row["storage"])) + "GB",
                variant_name=str(
                    row["variant_name"]
                ),
            )

            records.append(record)

        db.add_all(records)

        db.commit()

        print()
        print(
            f"Successfully inserted "
            f"{len(records)} catalog records."
        )

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()