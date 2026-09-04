import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# --------------------------------------------------
# PATHS
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "smartphones.csv"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "ml",
    "models"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "price_model.joblib"
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

print("=" * 60)
print("DEVICE PRICE ML MODEL TRAINING")
print("=" * 60)

print("\nLoading dataset...")
df = pd.read_csv(DATA_PATH)

print(f"Dataset rows: {len(df)}")
print(f"Dataset columns: {len(df.columns)}")


# --------------------------------------------------
# CLEAN TARGET
# --------------------------------------------------

df["price_inr"] = pd.to_numeric(
    df["price_inr"],
    errors="coerce"
)

df = df.dropna(subset=["price_inr"])

print(f"Rows after cleaning: {len(df)}")


# --------------------------------------------------
# FEATURES
# --------------------------------------------------

features = [
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


# Keep only features that actually exist
features = [
    column for column in features
    if column in df.columns
]

X = df[features]
y = df["price_inr"]


print("\nFeatures used:")
for feature in features:
    print(" -", feature)


# --------------------------------------------------
# IDENTIFY FEATURE TYPES
# --------------------------------------------------

categorical_features = X.select_dtypes(
    include=["object", "bool"]
).columns.tolist()

numeric_features = X.select_dtypes(
    exclude=["object", "bool"]
).columns.tolist()


print("\nCategorical features:", len(categorical_features))
print("Numeric features:", len(numeric_features))


# --------------------------------------------------
# PREPROCESSING
# --------------------------------------------------

numeric_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        )
    ]
)


categorical_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent")
        ),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore"
            )
        )
    ]
)


preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_pipeline,
            numeric_features
        ),
        (
            "categorical",
            categorical_pipeline,
            categorical_features
        )
    ]
)


# --------------------------------------------------
# MODEL
# --------------------------------------------------

model = RandomForestRegressor(
    n_estimators=400,
    max_depth=None,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)


pipeline = Pipeline(
    steps=[
        (
            "preprocessor",
            preprocessor
        ),
        (
            "model",
            model
        )
    ]
)


# --------------------------------------------------
# TRAIN / TEST SPLIT
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


print("\nTraining rows:", len(X_train))
print("Testing rows:", len(X_test))


# --------------------------------------------------
# TRAIN
# --------------------------------------------------

print("\nTraining Random Forest...")
pipeline.fit(X_train, y_train)

print("Training completed.")


# --------------------------------------------------
# EVALUATION
# --------------------------------------------------

predictions = pipeline.predict(X_test)

mae = mean_absolute_error(
    y_test,
    predictions
)

rmse = mean_squared_error(
    y_test,
    predictions
) ** 0.5

r2 = r2_score(
    y_test,
    predictions
)


print("\n" + "=" * 60)
print("MODEL PERFORMANCE")
print("=" * 60)

print(f"MAE  : ₹{mae:,.2f}")
print(f"RMSE : ₹{rmse:,.2f}")
print(f"R²   : {r2:.4f}")


# --------------------------------------------------
# SAVE MODEL
# --------------------------------------------------

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)

joblib.dump(
    pipeline,
    MODEL_PATH
)


print("\nModel saved:")
print(MODEL_PATH)

print("\n" + "=" * 60)
print("TASK 1A COMPLETE")
print("=" * 60)