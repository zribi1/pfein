"""Train the first company continuity-risk model.

The model predicts `continuity_risk_12m_label`: whether a company is likely to
stop being active/open within the next 12 months.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("train_continuity_model")

DEFAULT_TARGET = "continuity_risk_12m_label"
EXCLUDE_COLUMNS = {
    "siren",
    "prediction_date",
    "first_future_legal_event_date",
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
}


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    train_model(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        artifacts_dir=Path(args.artifacts_dir or settings.ML_ARTIFACTS_DIR),
        model_file=args.model_file or settings.ML_MODEL_FILE,
        target=args.target,
        min_rows=args.min_rows,
        max_rows=args.max_rows,
        train_start_year=args.train_start_year,
        train_end_year=args.train_end_year,
    )


def train_model(
    *,
    data_lake_dir: Path,
    artifacts_dir: Path,
    model_file: str,
    target: str,
    min_rows: int,
    max_rows: int | None,
    train_start_year: int | None = None,
    train_end_year: int | None = None,
) -> None:
    import duckdb
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    features_path = data_lake_dir / "features" / "company_year_features"
    labels_path = data_lake_dir / "features" / "risk_labels"
    if not _has_parquet(features_path):
        raise FileNotFoundError(f"missing features parquet under {features_path}")
    if not _has_parquet(labels_path):
        raise FileNotFoundError(f"missing labels parquet under {labels_path}")

    filters = [f"l.{target} IS NOT NULL"]
    if train_start_year is not None:
        filters.append(f"f.prediction_year >= {int(train_start_year)}")
    if train_end_year is not None:
        filters.append(f"f.prediction_year <= {int(train_end_year)}")
    where_sql = " AND ".join(filters)
    limit_sql = f"LIMIT {int(max_rows)}" if max_rows else ""
    query = f"""
        SELECT f.*, l.{target}
        FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true) f
        JOIN read_parquet('{_sql_string(_glob(labels_path))}', union_by_name=true) l
          USING (siren, prediction_year)
        WHERE {where_sql}
        ORDER BY f.prediction_year, f.siren
        {limit_sql}
    """
    con = duckdb.connect()
    try:
        df = con.execute(query).df()
    finally:
        con.close()

    if len(df) < min_rows:
        raise RuntimeError(f"not enough rows for training: {len(df)} < {min_rows}")

    y = df[target].astype(int)
    class_counts = y.value_counts().to_dict()
    if y.nunique() < 2:
        raise RuntimeError(f"target {target} has one class only: {class_counts}")

    feature_columns = [
        col
        for col in df.columns
        if col not in EXCLUDE_COLUMNS and col != target
    ]
    X = df[feature_columns].copy()
    for col in X.columns:
        if pd.api.types.is_bool_dtype(X[col]):
            X[col] = X[col].astype("Int64")

    numeric_columns = [
        col for col in X.columns if pd.api.types.is_numeric_dtype(X[col])
    ]
    categorical_columns = [col for col in X.columns if col not in numeric_columns]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ]
    )
    model = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "classifier",
                LogisticRegression(max_iter=1000, class_weight="balanced", n_jobs=1),
            ),
        ]
    )

    latest_year = int(df["prediction_year"].max())
    train_mask = df["prediction_year"] < latest_year
    if train_mask.sum() >= min_rows and y[train_mask].nunique() == 2 and y[~train_mask].nunique() == 2:
        X_train, X_test = X[train_mask], X[~train_mask]
        y_train, y_test = y[train_mask], y[~train_mask]
        split_strategy = f"time_split_latest_year_{latest_year}"
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y if y.value_counts().min() >= 2 else None,
        )
        split_strategy = "stratified_random_split"

    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "roc_auc": _safe_metric(roc_auc_score, y_test, probabilities),
        "average_precision": _safe_metric(average_precision_score, y_test, probabilities),
    }

    model_version = datetime.now(tz=timezone.utc).strftime("continuity-risk-%Y%m%d-%H%M%S")
    bundle = {
        "pipeline": model,
        "target": target,
        "model_version": model_version,
        "feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "horizon_months": 12,
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / model_file
    joblib.dump(bundle, model_path)
    metadata = {
        "model_version": model_version,
        "target": target,
        "horizon_months": 12,
        "rows": int(len(df)),
        "train_start_year": train_start_year,
        "train_end_year": train_end_year,
        "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        "split_strategy": split_strategy,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "metrics": metrics,
        "model_file": str(model_path),
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (artifacts_dir / "model_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    logger.info("trained model=%s rows=%d metrics=%s", model_path, len(df), metrics)


def _safe_metric(func: Any, y_true: Any, y_score: Any) -> float | None:
    try:
        return float(func(y_true, y_score))
    except Exception:
        return None


def _has_parquet(root: Path) -> bool:
    return root.exists() and any(root.rglob("*.parquet"))


def _glob(root: Path) -> str:
    return str(root / "**" / "*.parquet").replace("\\", "/")


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the continuity-risk model.")
    parser.add_argument("--data-lake-dir", help="Defaults to DATA_LAKE_DIR.")
    parser.add_argument("--artifacts-dir", help="Defaults to ML_ARTIFACTS_DIR.")
    parser.add_argument("--model-file", help="Defaults to ML_MODEL_FILE.")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--min-rows", type=int, default=1000)
    parser.add_argument("--max-rows", type=int, help="Optional smoke-test cap.")
    parser.add_argument("--train-start-year", type=int, help="First prediction_year allowed in the training dataset.")
    parser.add_argument("--train-end-year", type=int, help="Last prediction_year allowed in the training dataset.")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
