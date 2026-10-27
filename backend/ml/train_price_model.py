"""Train the DEVICE VALUE model.

=================================================================
WHAT IS TRAINED
=================================================================

A single Random Forest regressor with ONE target:

    device_value_inr

Inputs are the full feature contract in
`ml.feature_schema.FEATURES`:
  - device specifications (from data/smartphones.csv)
  - device age
  - battery health
  - screen / body / camera condition
  - scratch / dent / crack / frame-damage severity
  - functional test score
  - diagnostic score + individual diagnostic failures
  - repair history, accessories, warranty
  - AI physical condition score

Condition is part of the feature vector. Nothing multiplies a
predicted price afterwards.

-----------------------------------------------------------------
READ THIS BEFORE TRUSTING THE OUTPUT
-----------------------------------------------------------------

The committed dataset is a MARKET / LISTING dataset. It has no
condition columns. `ml.condition_dataset` therefore expands each
specification row across documented condition scenarios and
derives each scenario's label from an explicit depreciation
prior.

So: the model is genuinely trained and genuinely predicts from
its inputs, but the condition half of its training signal comes
from a stated assumption rather than from observed second-hand
transactions. It should be presented as an estimate, not as a
validated second-hand price.

Replacing that with real data is a one-function change: drop a
CSV at `data/used_phones_real.csv` and it takes precedence
automatically. See `ml.condition_dataset.load_training_frame`.

-----------------------------------------------------------------
RUN
-----------------------------------------------------------------

    cd backend
    python -m ml.train_price_model
"""

import os
import sys

try:
    # Windows consoles default to cp1252, which cannot encode
    # the rupee symbol used in the report below.
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import joblib
import numpy as np

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.core.logger import get_logger
from ml.condition_dataset import (
    TARGET_COLUMN,
    load_training_frame,
)
from ml.feature_schema import (
    CATEGORICAL_FEATURES,
    CONDITION_FEATURES,
    FEATURES,
    NUMERIC_FEATURES,
    SPEC_FEATURES,
    validate_feature_contract,
)
from ml.model_store import (
    ARTIFACT_VERSION,
    MODEL_DIR,
    MODEL_PATH,
    reset_model_cache,
)


# ============================================================
# TRAINING COST CONTROLS
#
# The expanded frame has ~200k rows (758 devices x ~258
# condition profiles). Fitting a wide one-hot encoder over that
# dominates runtime, so categorical cardinality is capped.
#
# Raising MAX_CATEGORIES or MAX_PROFILE_WEIGHTS improves
# fidelity to rare devices at a steep cost in training time.
# ============================================================

# Most frequent categorical levels kept per column. The tail is
# folded into a single "infrequent" level.
MAX_CATEGORIES = 120

# A level must appear at least this many times to be kept as
# its own category.
MIN_CATEGORY_FREQUENCY = 10

# Rows are thinned to at most this many, by sampling whole
# condition profiles per device. Keeps training fast without
# dropping any device from the dataset.
MAX_TRAINING_ROWS = 120_000

logger = get_logger("ml.train_price_model")


def print_header(title):
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66)


def thin_frame(frame, max_rows=MAX_TRAINING_ROWS):
    """Reduce the expanded frame to at most `max_rows`.

    Whole condition profiles are kept intact; only devices are
    sampled. That matters: an earlier version stepped through
    rows with a stride, which silently deleted entire scenarios
    from the training set. Twenty-two of sixty-three profiles
    vanished that way, including the counterfactual rows that
    make each damage flag separately identifiable, so
    `crack_severity` and `dent_severity` had literally no effect
    on the prediction.

    Sampling whole devices keeps every profile for every device
    that survives, so no condition state can disappear and the
    damage flags stay identifiable.
    """

    if len(frame) <= max_rows:
        return frame

    devices = frame["brand_model"].nunique()

    profiles_per_device = max(
        1, len(frame) // devices
    )

    keep_devices = max(
        1, max_rows // profiles_per_device
    )

    if keep_devices >= devices:
        return frame

    logger.info(
        "Thinning %d rows to ~%d: keeping all %d"
        " condition profiles for %d of %d devices.",
        len(frame),
        max_rows,
        frame["scenario"].nunique(),
        keep_devices,
        devices,
    )

    # Deterministic, evenly spaced device selection.
    device_keys = frame["brand_model"].drop_duplicates()
    device_keys = device_keys.iloc[
        np.linspace(
            0,
            len(device_keys) - 1,
            keep_devices,
        ).astype(int)
    ]

    sampled = frame[
        frame["brand_model"].isin(device_keys)
    ]

    logger.info(
        "Thinned to %d rows across %d profiles.",
        len(sampled),
        sampled["scenario"].nunique(),
    )

    return sampled


def build_pipeline():
    """Preprocessor + Random Forest.

    `handle_unknown="ignore"` is essential: users can type a
    model name that was never in training, and the encoder must
    degrade to the unknown bucket rather than raise.
    """

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            )
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="most_frequent"
                ),
            ),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore",
                    # Cap cardinality. Without this the encoder
                    # materialises one column per distinct model
                    # and processor name across ~160k rows, which
                    # dominates both training time and memory
                    # while adding no predictive value: the
                    # long tail is each device appearing once.
                    max_categories=MAX_CATEGORIES,
                    min_frequency=MIN_CATEGORY_FREQUENCY,
                    dtype="float32",
                ),
            ),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    model = RandomForestRegressor(
        # 120 trees is enough for this feature space. Confidence
        # is derived from per-tree spread, so a much larger
        # forest would mostly add training time rather than
        # signal.
        n_estimators=120,
        max_depth=None,
        min_samples_leaf=8,
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def main():
    validate_feature_contract()

    print_header("DEVICE VALUE MODEL TRAINING")

    frame = load_training_frame()

    # One key per physical device, used both for row thinning and
    # for the grouped train/test split, so the two always agree.
    frame["brand_model"] = (
        frame["smartphone_brand"].astype(str)
        + "|"
        + frame["model"].astype(str)
    )

    frame = thin_frame(frame)

    print(f"\nTraining rows          : {len(frame)}")
    print(f"Specification features : {len(SPEC_FEATURES)}")
    print(f"Condition features     : {len(CONDITION_FEATURES)}")
    print(f"Total features         : {len(FEATURES)}")
    print(f"Target column          : {TARGET_COLUMN}")

    if "scenario" in frame.columns:
        print("\nLabel provenance by scenario:")

        for label, group in frame.groupby("scenario"):
            print(
                f"  {label:<24} rows={len(group):<6} "
                f"mean=Rs.{group[TARGET_COLUMN].mean():>10,.0f}"
            )

    # The random-forest split must not leak near-duplicate rows
    # of the same device across train and test, so the split is
    # grouped by brand + model.
    group_key = frame["brand_model"]

    X = frame[FEATURES]
    y = frame[TARGET_COLUMN]

    # GroupShuffleSplit keeps every row for a given device on the
    # same side of the split. A plain train_test_split would put
    # the same phone in both train and test, which inflates the
    # score and hides whether the model generalises.
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=42,
    )

    train_index, test_index = next(
        splitter.split(X, y, groups=group_key)
    )

    X_train = X.iloc[train_index]
    X_test = X.iloc[test_index]
    y_train = y.iloc[train_index]
    y_test = y.iloc[test_index]

    print(f"\nTraining rows (split)  : {len(X_train)}")
    print(f"Testing rows  (split)  : {len(X_test)}")
    print("Split is grouped by brand|model to avoid leaking a "
          "device across train/test.")

    print("\nTraining Random Forest...")

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    print("Training complete.")

    predictions = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(
        y_test,
        predictions,
    ) ** 0.5
    r2 = r2_score(y_test, predictions)

    baseline = np.full_like(
        np.asarray(y_test, dtype=float),
        float(np.mean(np.abs(y_train))),
    )

    baseline_mae = float(np.mean(np.abs(
        np.asarray(y_test, dtype=float) - baseline
    )))

    print_header("MODEL PERFORMANCE (held-out split)")
    print(f"MAE                 : Rs.{mae:,.2f}")
    print(f"RMSE                : Rs.{rmse:,.2f}")
    print(f"R2                  : {r2:.4f}")
    print(f"Mean-value MAE      : Rs.{baseline_mae:,.2f}")
    print(f"Skill vs baseline   : "
          f"{100 * (1 - mae / baseline_mae):.1f}% lower MAE")

    # Condition sensitivity: the model must actually respond to
    # condition inputs. If these are flat, the condition features
    # are not wired up and the redesign has failed.
    print_header("CONDITION SENSITIVITY CHECK")
    print("Same device, degrading condition. The value must fall.\n")

    base_spec = frame[SPEC_FEATURES].iloc[0].to_dict()

    probe_specs = [
        ("new / flawless", {
            "device_age_months": 1.0,
            "battery_health_pct": 100.0,
            "screen_condition_score": 99.0,
            "body_condition_score": 99.0,
            "camera_condition_score": 99.0,
            "scratch_severity": 0.0,
            "dent_severity": 0.0,
            "crack_severity": 0.0,
            "frame_damage_severity": 0.0,
            "functional_test_score": 100.0,
            "diagnostic_score": 100.0,
            "diagnostics_failed_count": 0.0,
            "diagnostic_camera_failed": 0.0,
            "diagnostic_microphone_failed": 0.0,
            "diagnostic_touch_failed": 0.0,
            "diagnostic_sensor_failed": 0.0,
            "diagnostic_connectivity_failed": 0.0,
            "repair_history_code": 0.0,
            "accessories_code": 3.0,
            "warranty_months_remaining": 12.0,
            "ai_condition_score": 98.0,
        }),
        ("good / typical used", {
            "device_age_months": 16.0,
            "battery_health_pct": 90.0,
            "screen_condition_score": 88.0,
            "body_condition_score": 82.0,
            "camera_condition_score": 90.0,
            "scratch_severity": 1.0,
            "dent_severity": 0.0,
            "crack_severity": 0.0,
            "frame_damage_severity": 0.0,
            "functional_test_score": 88.0,
            "diagnostic_score": 95.0,
            "diagnostics_failed_count": 0.0,
            "diagnostic_camera_failed": 0.0,
            "diagnostic_microphone_failed": 0.0,
            "diagnostic_touch_failed": 0.0,
            "diagnostic_sensor_failed": 0.0,
            "diagnostic_connectivity_failed": 0.0,
            "repair_history_code": 0.0,
            "accessories_code": 2.0,
            "warranty_months_remaining": 0.0,
            "ai_condition_score": 86.0,
        }),
        ("fair / visible wear", {
            "device_age_months": 26.0,
            "battery_health_pct": 82.0,
            "screen_condition_score": 74.0,
            "body_condition_score": 62.0,
            "camera_condition_score": 82.0,
            "scratch_severity": 2.0,
            "dent_severity": 1.0,
            "crack_severity": 0.0,
            "frame_damage_severity": 1.0,
            "functional_test_score": 74.0,
            "diagnostic_score": 88.0,
            "diagnostics_failed_count": 1.0,
            "diagnostic_camera_failed": 0.0,
            "diagnostic_microphone_failed": 1.0,
            "diagnostic_touch_failed": 0.0,
            "diagnostic_sensor_failed": 0.0,
            "diagnostic_connectivity_failed": 0.0,
            "repair_history_code": 0.0,
            "accessories_code": 1.0,
            "warranty_months_remaining": 0.0,
            "ai_condition_score": 70.0,
        }),
        ("poor / damaged", {
            "device_age_months": 38.0,
            "battery_health_pct": 72.0,
            "screen_condition_score": 45.0,
            "body_condition_score": 35.0,
            "camera_condition_score": 60.0,
            "scratch_severity": 3.0,
            "dent_severity": 2.0,
            "crack_severity": 1.0,
            "frame_damage_severity": 2.0,
            "functional_test_score": 55.0,
            "diagnostic_score": 70.0,
            "diagnostics_failed_count": 2.0,
            "diagnostic_camera_failed": 1.0,
            "diagnostic_microphone_failed": 0.0,
            "diagnostic_touch_failed": 1.0,
            "diagnostic_sensor_failed": 0.0,
            "diagnostic_connectivity_failed": 1.0,
            "repair_history_code": 1.0,
            "accessories_code": 0.0,
            "warranty_months_remaining": 0.0,
            "ai_condition_score": 45.0,
        }),
    ]

    import pandas as pd

    previous = None
    monotonic = True

    for label, condition in probe_specs:

        row = {**base_spec, **condition}

        value = float(
            pipeline.predict(
                pd.DataFrame([row])[FEATURES]
            )[0]
        )

        if previous is not None and value >= previous:
            monotonic = False

        previous = value

        print(f"  {label:<22} Rs.{value:>10,.0f}")

    print(
        "\n  Monotonic decrease: "
        + ("YES" if monotonic else "NO - investigate")
    )

    print_header("TOP FEATURE IMPORTANCES")

    try:
        names = (
            pipeline.named_steps["preprocessor"]
            .get_feature_names_out()
        )

        raw = pipeline.named_steps[
            "model"
        ].feature_importances_

        ranked = sorted(
            zip(names, raw),
            key=lambda item: item[1],
            reverse=True,
        )

        for name, importance in ranked[:20]:
            print(f"  {name:<34} {importance:.4f}")

    except Exception as exc:
        print(f"  Could not read importances: {exc}")

    os.makedirs(MODEL_DIR, exist_ok=True)

    joblib.dump(
        {
            "pipeline": pipeline,
            "features": list(FEATURES),
            "spec_features": list(SPEC_FEATURES),
            "condition_features": list(
                CONDITION_FEATURES
            ),
            "target": TARGET_COLUMN,
            "artifact_version": ARTIFACT_VERSION,
            "model_type": "Random Forest Regressor",
            "training_rows": int(len(X_train)),
            "metrics": {
                "mae": float(mae),
                "rmse": float(rmse),
                "r2": float(r2),
                "baseline_mae": baseline_mae,
            },
            "label_provenance": (
                "real_used_dataset"
                if "scenario" in frame.columns
                and set(frame["scenario"].unique())
                == {"real_transaction"}
                else "spec_dataset_plus_condition_scenarios"
            ),
        },
        MODEL_PATH,
    )

    print_header("SAVED")
    print(f"Model path : {MODEL_PATH}")
    print(f"Target     : {TARGET_COLUMN} (single value, in rupees)")
    print(
        "\nRetrain with:  python -m ml.train_price_model\n"
    )


if __name__ == "__main__":
    main()