"""Inference for the DEVICE VALUE model.

=================================================================
THE NEW PIPELINE, END TO END
=================================================================

  specifications (brand, model, RAM, storage, processor, ...)
        +
  device age
        +
  battery health
        +
  functional diagnostic results
        +
  physical condition
        +
  AI photo inspection
        +
  accessories / warranty / repair history
        -------------------------------
                  |
                  v
          ONE ML VALUATION MODEL
        (Random Forest, single target: device_value_inr)
                  |
                  v
            FINAL DEVICE VALUE

-----------------------------------------------------------------
WHAT CHANGED VS THE OLD DESIGN
-----------------------------------------------------------------

OLD:  RF predicted a spec-only market price,
      then a hand-written condition deduction scaled it,
      then resale_price = price * multiplier and
      exchange_price = price * 0.88.

NEW:  condition and diagnostics are INPUT FEATURES to the same
      forest that sees the specifications. The forest emits one
      number: device_value.

There is no condition multiplier and no exchange rate anywhere
in this module.

-----------------------------------------------------------------
CONFIDENCE
-----------------------------------------------------------------

A regression forest has no `predict_proba`, so confidence is
derived from tree disagreement: the spread of per-tree
predictions. When the trees agree, the sample sits in a dense
region of training data and the estimate is trustworthy. When
they disagree, the input sits near a decision boundary or in a
sparse region, so confidence drops.

This is a genuine measure of estimator uncertainty, not a
decorative constant. It is reported, not used to alter the
price.
"""

import numpy as np
import pandas as pd

from app.core.logger import get_logger
from ml.feature_schema import (
    FEATURES,
    validate_feature_contract,
)
from ml.model_store import (
    get_model_pipeline,
)


logger = get_logger(__name__)


# ============================================================
# FLOOR
#
# A phone that does not power on still has scrap / parts value,
# so the model output is floored rather than allowed to go to
# zero. Not a valuation adjustment - just a domain bound.
# ============================================================

MIN_DEVICE_VALUE = 300.0

# Number of top features reported in `feature_importance`.
IMPORTANCE_TOP_N = 12


def _confidence_from_trees(per_tree_predictions, value):
    """Confidence in [0, 1] from forest tree disagreement.

    Relative standard deviation of the individual tree
    predictions. A relative spread of 0 means perfect agreement
    (confidence 1.0); a spread comparable to the predicted
    value itself means the trees are guessing (confidence
    approaches the floor).
    """

    predictions = np.asarray(
        per_tree_predictions,
        dtype=float,
    )

    if predictions.size == 0:
        return 0.5

    spread = float(np.std(predictions))

    reference = max(abs(float(value)), 1.0)

    relative_spread = spread / reference

    # 0.00 spread -> 1.00, ~0.45 spread -> ~0.10
    confidence = float(
        np.clip(
            1.0 - (relative_spread / 0.45),
            0.10,
            0.99,
        )
    )

    return round(confidence, 2)


def _per_tree_predictions(pipeline, frame):
    """Run every tree in the forest on one preprocessed row."""

    preprocessor = None
    estimator = None

    for name, step in getattr(
        pipeline, "steps", []
    ):
        if name in (
            "preprocessor",
            "preprocess",
            "transformer",
        ):
            preprocessor = step

        elif name in ("model", "regressor", "forest"):
            estimator = step

    if preprocessor is None or estimator is None:
        return []

    try:
        transformed = preprocessor.transform(frame)

        trees = getattr(estimator, "estimators_", [])

        return [
            float(tree.predict(transformed)[0])
            for tree in trees
        ]

    except Exception as exc:
        logger.warning(
            "Could not compute per-tree predictions: %s",
            exc,
        )
        return []


def _feature_importance(pipeline):
    """Named importances from the fitted ColumnTransformer."""

    importances = []

    try:
        preprocessor = dict(
            pipeline.steps
        )["preprocessor"]

        estimator = dict(
            pipeline.steps
        )["model"]

        raw = estimator.feature_importances_

        names = preprocessor.get_feature_names_out()

    except Exception as exc:
        logger.warning(
            "Could not read feature importances: %s",
            exc,
        )
        return importances

    for name, importance in zip(names, raw):
        importances.append(
            {
                "feature": str(name),
                "importance": round(
                    float(importance), 5
                ),
            }
        )

    importances.sort(
        key=lambda item: item["importance"],
        reverse=True,
    )

    return importances[:IMPORTANCE_TOP_N]


def predict_device_value(
    feature_row: dict,
    include_importance: bool = False
) -> dict:
    """Predict the single DEVICE VALUE for one device.

    feature_row:
        A dict keyed by the feature names in
        ml.feature_schema.FEATURES. Missing numeric condition
        keys fall back to
        DEFAULT_CONDITION_FEATURES; specification keys are
        supplied by the caller after dataset matching.

    Returns:
        {
            "device_value": int,
            "currency": "INR",
            "confidence": float,
            "prediction_interval": {
                "low": int,
                "high": int
            },
            "tree_disagreement_pct": float,
            "model_type": "Random Forest Regressor",
            "feature_importance": [...]   # optional
        }
    """

    validate_feature_contract()

    pipeline = get_model_pipeline()

    if pipeline is None:
        raise RuntimeError(
            "Device value model is not loaded. "
            "Train it with `python -m ml.train_price_model`."
        )

    row = {}

    for feature in FEATURES:
        row[feature] = feature_row.get(feature)

    frame = pd.DataFrame([row])[FEATURES]

    prediction = float(
        pipeline.predict(frame)[0]
    )

    value = max(
        MIN_DEVICE_VALUE,
        prediction,
    )

    tree_predictions = _per_tree_predictions(
        pipeline,
        frame,
    )

    if tree_predictions:
        low = float(
            np.percentile(tree_predictions, 10)
        )

        high = float(
            np.percentile(tree_predictions, 90)
        )

        spread = float(np.std(tree_predictions))

        reference = max(abs(value), 1.0)

        disagreement_pct = round(
            (spread / reference) * 100.0,
            2,
        )

    else:
        # No dispersion estimate available. Report a neutral
        # confidence rather than inventing one.
        low = value
        high = value
        disagreement_pct = None

    confidence = _confidence_from_trees(
        tree_predictions,
        value,
    )

    result = {
        "device_value": int(round(value)),
        "currency": "INR",
        "confidence": confidence,
        "prediction_interval": {
            "low": int(
                round(max(MIN_DEVICE_VALUE, low))
            ),
            "high": int(round(max(MIN_DEVICE_VALUE, high))),
        },
        "tree_disagreement_pct": disagreement_pct,
        "model_type": "Random Forest Regressor",
        "prediction_source": "Device Value ML Model",
    }

    if include_importance:
        result["feature_importance"] = (
            _feature_importance(pipeline)
        )

    return result


def predict_device_value_with_details(
    feature_row: dict,
    include_importance: bool = False
) -> dict:
    """Prediction plus the feature vector that produced it.

    Useful for debugging and for demonstrating to a user which
    inputs actually moved the number.
    """

    result = predict_device_value(
        feature_row,
        include_importance=include_importance,
    )

    result["input_features"] = {
        feature: feature_row.get(feature)
        for feature in FEATURES
    }

    return result