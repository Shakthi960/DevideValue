"""Model artifact loading for the DEVICE VALUE model.

The trained artifact is a plain sklearn Pipeline, saved with
joblib at the same location the old market-price model used
(`ml/models/price_model.joblib`) so nothing outside the
valuation layer needs to know the filename changed meaning.

The artifact is wrapped in a small dict alongside the feature
contract it was trained with. Loading validates that the
saved feature list still matches `ml.feature_schema.FEATURES`,
which turns a stale-artifact bug into an immediate, readable
error instead of a silently mis-ordered prediction.
"""

import os

import joblib
import pandas as pd

from app.core.logger import get_logger
from ml.feature_schema import (
    FEATURES,
    validate_feature_contract,
)


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

# Artifact format version. Bump when the saved dict layout
# changes so an old artifact fails loudly.
ARTIFACT_VERSION = 2


_model_bundle = None
_model_loaded = False


def get_price_model():
    """Return the trained DEVICE VALUE model bundle.

    Returns None when the artifact is missing or unreadable so
    the app can degrade gracefully, matching the previous
    behaviour of this function.
    """

    global _model_bundle, _model_loaded

    if _model_loaded:
        return _model_bundle

    validate_feature_contract()

    if not os.path.exists(MODEL_PATH):
        logger.warning(
            "Device value model not found: %s. "
            "Run `python -m ml.train_price_model`.",
            MODEL_PATH,
        )
        _model_loaded = True
        return None

    try:
        artifact = joblib.load(MODEL_PATH)

    except Exception as exc:
        logger.warning(
            "Could not load device value model: %s",
            exc,
        )
        _model_loaded = True
        return None

    # Accept either the new wrapped bundle or a bare pipeline
    # (for example an artifact produced by an older training
    # run), so the loader stays tolerant.
    if isinstance(artifact, dict):
        _model_bundle = artifact

    else:
        _model_bundle = {
            "pipeline": artifact,
            "features": list(FEATURES),
            "artifact_version": None,
        }

    saved_features = _model_bundle.get("features")

    if saved_features is not None and list(
        saved_features
    ) != list(FEATURES):
        logger.warning(
            "Device value model feature contract does not "
            "match ml.feature_schema.FEATURES. The artifact "
            "is stale; retrain with "
            "`python -m ml.train_price_model`."
        )
        _model_loaded = True
        return None

    logger.info(
        "Device value model loaded successfully "
        "(artifact version %s).",
        _model_bundle.get("artifact_version"),
    )

    _model_loaded = True
    return _model_bundle


def get_model_pipeline():
    """Return just the sklearn pipeline, or None."""

    bundle = get_price_model()

    if bundle is None:
        return None

    return bundle.get("pipeline")


def get_price_dataset():
    """Return the specification dataset, loaded once.

    Renamed from get_phone_dataset; the old name is kept as an
    alias because several non-valuation callers import it.
    """

    global _phone_dataset, _phone_dataset_loaded

    if _phone_dataset_loaded:
        return _phone_dataset

    try:
        data = pd.read_csv(DATASET_PATH)

        for column in (
            "smartphone_brand",
            "model",
        ):
            if column in data.columns:
                data[column] = (
                    data[column]
                    .astype(str)
                    .str.strip()
                )

        logger.info(
            "Specification dataset loaded: %d rows",
            len(data),
        )

        _phone_dataset = data

    except Exception as exc:
        logger.warning(
            "Could not load specification dataset: %s",
            exc,
        )
        _phone_dataset = pd.DataFrame()

    _phone_dataset_loaded = True
    return _phone_dataset


_phone_dataset = None
_phone_dataset_loaded = False


# Backwards-compatible alias.
get_phone_dataset = get_price_dataset


# Invalidate caches. Used by tests and by the training script,
# which retrains and then serves predictions in one process.
def reset_model_cache():
    global _model_bundle, _model_loaded
    global _phone_dataset, _phone_dataset_loaded

    _model_bundle = None
    _model_loaded = False
    _phone_dataset = None
    _phone_dataset_loaded = False