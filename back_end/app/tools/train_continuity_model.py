"""Train the first company continuity-risk model.

The model predicts `continuity_risk_12m_label`: whether a company is likely to
stop being active/open within the next 12 months.
"""

from __future__ import annotations

import argparse
import math
import json
import logging
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("train_continuity_model")


class CategoricalCardinalityCapper:
    """Cap categorical column cardinality so HistGradientBoostingClassifier
    fits inside its max_bins limit, then cast to pandas Categorical so HGB
    picks the columns up via ``categorical_features="from_dtype"``.

    Categories outside the top-N most frequent in training data (and
    categories never seen at training time) are folded into ``__OTHER__``.
    NaN is kept as NaN and handled by HGB's native missing-value bin.

    Defined at module level so a fitted instance round-trips through joblib
    without requiring the caller to import a nested class.
    """

    def __init__(
        self,
        categorical_columns: list[str],
        max_categories: int = 250,
        other_label: str = "__OTHER__",
    ) -> None:
        # IMPORTANT: store parameters exactly as passed for sklearn ``clone()``
        # compatibility. Any coercion (``list(...)``, ``int(...)``, ``str(...)``)
        # breaks the identity check in ``_clone_parametrized`` and prevents the
        # estimator from being used inside RandomizedSearchCV / GridSearchCV.
        self.categorical_columns = categorical_columns
        self.max_categories = max_categories
        self.other_label = other_label

    def fit(self, X: Any, y: Any = None) -> "CategoricalCardinalityCapper":
        max_categories = int(self.max_categories)
        self.top_categories_: dict[str, set[str]] = {}
        for column in list(self.categorical_columns):
            if column not in X.columns:
                continue
            counts = X[column].dropna().astype(str).value_counts()
            self.top_categories_[column] = set(
                counts.head(max_categories).index.tolist()
            )
        return self

    def transform(self, X: Any) -> Any:
        other_label = str(self.other_label)
        X = X.copy()
        for column in list(self.categorical_columns):
            if column not in X.columns:
                continue
            allowed = self.top_categories_.get(column, set())
            series = X[column].astype(object).where(X[column].notna(), None)
            mapped = series.map(
                lambda value, _allowed=allowed, _other=other_label: (
                    value if (value is None or value in _allowed) else _other
                )
            )
            X[column] = mapped.astype("category")
        return X

    def fit_transform(self, X: Any, y: Any = None) -> Any:
        return self.fit(X, y).transform(X)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {
            "categorical_columns": self.categorical_columns,
            "max_categories": self.max_categories,
            "other_label": self.other_label,
        }

    def set_params(self, **params: Any) -> "CategoricalCardinalityCapper":
        for key, value in params.items():
            setattr(self, key, value)
        return self


class CategoricalCaster:
    """Cast the named columns to pandas ``Categorical`` without capping.

    Used for LightGBM and XGBoost, which detect Categorical dtype via their
    ``categorical_feature='auto'`` / ``enable_categorical=True`` paths and
    handle high cardinality natively (no max_bins-style cap like HGB).
    """

    def __init__(self, categorical_columns: list[str]) -> None:
        # See CategoricalCardinalityCapper.__init__ — store as-is for clone().
        self.categorical_columns = categorical_columns

    def fit(self, X: Any, y: Any = None) -> "CategoricalCaster":
        return self

    def transform(self, X: Any) -> Any:
        X = X.copy()
        for column in list(self.categorical_columns):
            if column in X.columns:
                X[column] = X[column].astype("category")
        return X

    def fit_transform(self, X: Any, y: Any = None) -> Any:
        return self.transform(X)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {"categorical_columns": self.categorical_columns}

    def set_params(self, **params: Any) -> "CategoricalCaster":
        for key, value in params.items():
            setattr(self, key, value)
        return self


class StringCaster:
    """Cast the named columns to Python ``str`` for CatBoost.

    CatBoost requires categorical columns to be string-typed and accepts a
    ``cat_features`` list at construction. NaN values become the literal
    string ``"nan"`` and are treated as a distinct category by CatBoost.
    """

    def __init__(self, categorical_columns: list[str]) -> None:
        # See CategoricalCardinalityCapper.__init__ — store as-is for clone().
        self.categorical_columns = categorical_columns

    def fit(self, X: Any, y: Any = None) -> "StringCaster":
        return self

    def transform(self, X: Any) -> Any:
        X = X.copy()
        for column in list(self.categorical_columns):
            if column in X.columns:
                X[column] = X[column].astype(str)
        return X

    def fit_transform(self, X: Any, y: Any = None) -> Any:
        return self.transform(X)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {"categorical_columns": self.categorical_columns}

    def set_params(self, **params: Any) -> "StringCaster":
        for key, value in params.items():
            setattr(self, key, value)
        return self


class _CatBoostSklearnClassifier:
    """sklearn-clone-safe wrapper around ``catboost.CatBoostClassifier``.

    Native ``CatBoostClassifier`` mutates list-typed constructor params
    (``cat_features``, ``class_weights``) internally — ``get_params()`` returns
    a different object id than what was passed, which breaks sklearn's
    ``clone()`` identity check inside ``RandomizedSearchCV``.

    This wrapper stores every constructor argument verbatim on ``self``, so
    ``get_params()`` (implemented manually below to mirror sklearn's
    ``BaseEstimator``) returns the same Python objects ``clone()`` saw. The
    real ``CatBoostClassifier`` is instantiated lazily inside ``fit``.
    """

    def __init__(
        self,
        cat_features: list[str] | None = None,
        iterations: int = 400,
        learning_rate: float = 0.05,
        depth: int = 6,
        l2_leaf_reg: float = 3.0,
        auto_class_weights: str | None = "Balanced",
        bagging_temperature: float | None = None,
        random_seed: int = 42,
        verbose: bool = False,
        allow_writing_files: bool = False,
        task_type: str = "CPU",
        devices: str | None = None,
    ) -> None:
        # Store parameters exactly as passed (no list(...) / int(...) coercion)
        # so sklearn ``clone()`` can round-trip the estimator.
        self.cat_features = cat_features
        self.iterations = iterations
        self.learning_rate = learning_rate
        self.depth = depth
        self.l2_leaf_reg = l2_leaf_reg
        self.auto_class_weights = auto_class_weights
        self.bagging_temperature = bagging_temperature
        self.random_seed = random_seed
        self.verbose = verbose
        self.allow_writing_files = allow_writing_files
        self.task_type = task_type
        self.devices = devices

    _PARAM_NAMES = (
        "cat_features", "iterations", "learning_rate", "depth", "l2_leaf_reg",
        "auto_class_weights", "bagging_temperature", "random_seed", "verbose",
        "allow_writing_files", "task_type", "devices",
    )

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self._PARAM_NAMES}

    def set_params(self, **params: Any) -> "_CatBoostSklearnClassifier":
        for key, value in params.items():
            if key not in self._PARAM_NAMES:
                raise ValueError(f"Invalid parameter {key!r} for _CatBoostSklearnClassifier")
            setattr(self, key, value)
        return self

    def _build_estimator(self) -> Any:
        from catboost import CatBoostClassifier

        kwargs: dict[str, Any] = {
            "iterations": int(self.iterations),
            "learning_rate": float(self.learning_rate),
            "depth": int(self.depth),
            "l2_leaf_reg": float(self.l2_leaf_reg),
            "random_seed": int(self.random_seed),
            "verbose": bool(self.verbose),
            "allow_writing_files": bool(self.allow_writing_files),
            "task_type": str(self.task_type),
        }
        if self.cat_features is not None:
            kwargs["cat_features"] = list(self.cat_features)
        if self.auto_class_weights is not None:
            kwargs["auto_class_weights"] = self.auto_class_weights
        if self.bagging_temperature is not None:
            kwargs["bagging_temperature"] = float(self.bagging_temperature)
        if self.task_type == "GPU" and self.devices is not None:
            kwargs["devices"] = str(self.devices)
        return CatBoostClassifier(**kwargs)

    def fit(self, X: Any, y: Any = None, **fit_params: Any) -> "_CatBoostSklearnClassifier":
        self._estimator_ = self._build_estimator()
        self._estimator_.fit(X, y, **fit_params)
        self.classes_ = self._estimator_.classes_
        return self

    def predict(self, X: Any) -> Any:
        return self._estimator_.predict(X)

    def predict_proba(self, X: Any) -> Any:
        return self._estimator_.predict_proba(X)


MODEL_FAMILIES = ("hgb", "lightgbm", "catboost", "xgboost")


def _build_model_pipeline(
    *,
    family: str,
    categorical_columns: list[str],
    train_positive_count: int,
    train_negative_count: int,
    extra_params: dict[str, Any] | None = None,
    gpu: bool = False,
) -> Any:
    """Return a sklearn ``Pipeline`` configured for the requested boosting library.

    All four families use comparable settings: 400 boosting rounds, learning
    rate 0.05, tree complexity around ~63 leaves / depth 6, mild L2
    regularization, and balanced class weighting (each library exposes its
    own knob for this — ``class_weight``, ``class_weights``,
    ``scale_pos_weight``). The categorical prep step is library-specific:

    - HGB caps cardinality (``max_bins=255``) and casts to ``Categorical``.
    - LightGBM and XGBoost cast to ``Categorical`` without capping.
    - CatBoost casts to ``str`` and consumes a ``cat_features`` list.

    Passing ``extra_params`` overrides the classifier's defaults — used by
    Phase B hyperparameter tuning to inject the best configuration found by
    RandomizedSearchCV. ``gpu=True`` switches CatBoost and XGBoost to their
    CUDA paths; HGB and LightGBM have no GPU support here and ignore it.
    """
    from sklearn.pipeline import Pipeline

    pos = max(int(train_positive_count), 1)
    neg = max(int(train_negative_count), 1)
    pos_weight = neg / pos
    overrides = dict(extra_params or {})

    if family == "hgb":
        from sklearn.ensemble import HistGradientBoostingClassifier

        params = {
            "max_iter": 400,
            "learning_rate": 0.05,
            "max_leaf_nodes": 63,
            "min_samples_leaf": 50,
            "l2_regularization": 1.0,
            "class_weight": "balanced",
            "categorical_features": "from_dtype",
            "early_stopping": True,
            "validation_fraction": 0.1,
            "n_iter_no_change": 20,
            "random_state": 42,
        }
        params.update(overrides)
        return Pipeline(
            steps=[
                (
                    "prepare_categoricals",
                    CategoricalCardinalityCapper(categorical_columns, max_categories=250),
                ),
                ("classifier", HistGradientBoostingClassifier(**params)),
            ]
        )

    if family == "lightgbm":
        from lightgbm import LGBMClassifier

        params = {
            "n_estimators": 400,
            "learning_rate": 0.05,
            "num_leaves": 63,
            "min_child_samples": 50,
            "reg_lambda": 1.0,
            "class_weight": "balanced",
            "random_state": 42,
            "verbosity": -1,
            "n_jobs": -1,
        }
        params.update(overrides)
        return Pipeline(
            steps=[
                ("prepare_categoricals", CategoricalCaster(categorical_columns)),
                ("classifier", LGBMClassifier(**params)),
            ]
        )

    if family == "xgboost":
        from xgboost import XGBClassifier

        params = {
            "n_estimators": 400,
            "learning_rate": 0.05,
            "max_depth": 8,
            "min_child_weight": 50.0,
            "reg_lambda": 1.0,
            "scale_pos_weight": pos_weight,
            "enable_categorical": True,
            "tree_method": "hist",
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "random_state": 42,
            "verbosity": 0,
            "n_jobs": -1,
        }
        if gpu:
            params["device"] = "cuda"
        params.update(overrides)
        return Pipeline(
            steps=[
                ("prepare_categoricals", CategoricalCaster(categorical_columns)),
                ("classifier", XGBClassifier(**params)),
            ]
        )

    if family == "catboost":
        # Use the sklearn-clone-safe wrapper instead of CatBoostClassifier
        # directly. CatBoost's native ``__init__`` mutates list params, so
        # ``get_params()`` returns different identities than what was passed
        # and sklearn ``clone()`` (called inside ``RandomizedSearchCV``) fails.
        # The wrapper stores everything verbatim, then builds the real
        # CatBoostClassifier on ``fit``.
        kwargs: dict[str, Any] = {
            "cat_features": categorical_columns,
            "iterations": 400,
            "learning_rate": 0.05,
            "depth": 6,
            "l2_leaf_reg": 3.0,
            "auto_class_weights": "Balanced",
            "random_seed": 42,
            "verbose": False,
            "allow_writing_files": False,
        }
        if gpu:
            kwargs["task_type"] = "GPU"
            kwargs["devices"] = "0"
        kwargs.update(overrides)
        return Pipeline(
            steps=[
                ("prepare_categoricals", StringCaster(categorical_columns)),
                ("classifier", _CatBoostSklearnClassifier(**kwargs)),
            ]
        )

    raise ValueError(f"unknown model family: {family!r}")


DEFAULT_TARGET = "continuity_risk_12m_label"
# The four INSEE identity columns (activity_code, legal_category_code,
# employee_size_bracket, administrative_status_at_cutoff) were once excluded
# here as temporal leakage. They are now temporally valid: the clean layer
# keeps INSEE periods and the feature builder selects the period in effect at
# each prediction_date, so they are back in the model inputs below.
EXCLUDE_COLUMNS = {
    "siren",
    "prediction_date",
    "first_future_legal_event_date",
    "company_name",
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
    # Degenerate features observed in run 20260515-193645:
    # has_confidential_financials is perfectly collinear with has_financial_data
    # (the source CTE only fires when a financial row exists, so both booleans
    # are the same). The three formalities_count_* columns had coefficient 0.0
    # (zero variance), indicating the formalities_events source table is empty
    # for the trained cohort. Reinstate if/when the source table is populated.
    "has_confidential_financials",
    "formalities_count_all",
    "formalities_count_12m",
    "cessation_formalities_count_all",
    # latest_equity_ratio is perfectly collinear with latest_debt_to_assets
    # (corr 0.9998 in the run 8 audit) because of the accounting identity
    # debt + equity ~= total_assets. Keeping both gives tree splits no extra
    # signal and confuses feature-importance attribution. Keep debt_to_assets.
    "latest_equity_ratio",
}


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    model_params: dict[str, Any] | None = None
    if args.params_file:
        model_params = json.loads(Path(args.params_file).read_text(encoding="utf-8"))
    train_model(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        artifacts_dir=Path(args.artifacts_dir or settings.ML_ARTIFACTS_DIR),
        model_file=args.model_file or settings.ML_MODEL_FILE,
        target=args.target,
        min_rows=args.min_rows,
        max_rows=args.max_rows,
        train_start_year=args.train_start_year,
        train_end_year=args.train_end_year,
        model_family=args.model_family,
        model_params=model_params,
        gpu=args.gpu,
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
    model_family: str = "hgb",
    model_params: dict[str, Any] | None = None,
    gpu: bool = False,
) -> None:
    if model_family not in MODEL_FAMILIES:
        raise ValueError(
            f"unknown model_family={model_family!r}; expected one of {MODEL_FAMILIES}"
        )
    import duckdb
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline

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
    con = duckdb.connect()
    try:
        total_rows = _count_training_rows(
            con,
            features_path=features_path,
            labels_path=labels_path,
            target=target,
            where_sql=where_sql,
        )
        sample_sql = ""
        order_sql = "ORDER BY f.prediction_year, f.siren"
        limit_sql = ""
        sample_strategy = "full_dataset"
        if max_rows and total_rows > max_rows:
            modulus = 1_000_000
            # Oversample slightly, then cap by hash order. This keeps capped
            # samples spread across all years instead of taking the earliest rows.
            threshold = math.ceil((int(max_rows) / total_rows) * modulus * 1.15)
            threshold = max(1, min(modulus, threshold))
            row_hash_sql = _row_hash_sql()
            sample_sql = f" AND {row_hash_sql} % {modulus} < {threshold}"
            order_sql = f"ORDER BY {row_hash_sql}"
            limit_sql = f"LIMIT {int(max_rows)}"
            sample_strategy = (
                f"deterministic_hash_sample_threshold_{threshold}_of_{modulus}"
            )

        feature_table_columns = _list_columns(con, _glob(features_path))
        all_source_columns = feature_table_columns + [target]
        # Pull only the columns the model needs. "SELECT f.*" also loads heavy
        # unused columns into the DataFrame -- company_name strings worst of all
        # -- which inflates peak memory and lowers the row cap that fits in RAM.
        # siren and prediction_year still drive the JOIN's USING clause on the
        # source tables even when siren is not in the SELECT list.
        select_columns = [
            col for col in feature_table_columns if col not in EXCLUDE_COLUMNS
        ]
        select_sql = ", ".join(f'f."{col}"' for col in select_columns)
        query = f"""
            SELECT {select_sql}, l."{target}"
            FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true) f
            JOIN read_parquet('{_sql_string(_glob(labels_path))}', union_by_name=true) l
              USING (siren, prediction_year)
            WHERE {where_sql}
            {sample_sql}
            {order_sql}
            {limit_sql}
        """
        df = con.execute(query).df()
    finally:
        con.close()

    if len(df) < min_rows:
        raise RuntimeError(f"not enough rows for training: {len(df)} < {min_rows}")

    y = df[target].astype(int)
    class_counts = y.value_counts().to_dict()
    class_counts_by_year = (
        df.groupby(["prediction_year", target], observed=True)
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )
    if y.nunique() < 2:
        raise RuntimeError(f"target {target} has one class only: {class_counts}")

    feature_columns = [
        col
        for col in df.columns
        if col not in EXCLUDE_COLUMNS and col != target
    ]
    excluded_columns_present = sorted(
        col for col in all_source_columns if col in EXCLUDE_COLUMNS
    )
    X = df[feature_columns].copy()
    for col in X.columns:
        # HGB consumes pandas booleans fine, but pyarrow-backed object columns
        # that arrive as 0/1/None get treated as object dtype and rejected.
        # Cast booleans to float so the missing-value bin route lights up
        # consistently.
        if pd.api.types.is_bool_dtype(X[col]):
            X[col] = X[col].astype(float)

    numeric_columns = [
        col for col in X.columns if pd.api.types.is_numeric_dtype(X[col])
    ]
    categorical_columns = [col for col in X.columns if col not in numeric_columns]

    # Gradient-boosting libraries all handle NaN + high-cardinality categoricals
    # natively, but each one needs the data shaped slightly differently
    # (Categorical vs string, capped vs uncapped). The dispatcher returns a
    # ready-to-fit Pipeline; class-imbalance handling is also library-specific.
    train_mask_preview = df["prediction_year"] < int(df["prediction_year"].max())
    preview_pos = int((y[train_mask_preview] == 1).sum())
    preview_neg = int((y[train_mask_preview] == 0).sum())
    model = _build_model_pipeline(
        family=model_family,
        categorical_columns=categorical_columns,
        train_positive_count=preview_pos,
        train_negative_count=preview_neg,
        extra_params=model_params,
        gpu=gpu,
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

    train_missing_values = int(X_train.isna().sum().sum())
    test_missing_values = int(X_test.isna().sum().sum())

    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    tn, fp, fn, tp = [
        int(value)
        for value in confusion_matrix(y_test, predictions, labels=[0, 1]).ravel()
    ]
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "roc_auc": _safe_metric(roc_auc_score, y_test, probabilities),
        "average_precision": _safe_metric(average_precision_score, y_test, probabilities),
        "precision_at_0_5": float(precision_score(y_test, predictions, zero_division=0)),
        "recall_at_0_5": float(recall_score(y_test, predictions, zero_division=0)),
        "f1_at_0_5": float(f1_score(y_test, predictions, zero_division=0)),
        "confusion_matrix_at_0_5": {
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "true_positive": tp,
        },
    }
    threshold_analysis = _threshold_analysis(y_test, probabilities)
    top_k_analysis = _top_k_analysis(y_test, probabilities)
    metrics["threshold_analysis"] = threshold_analysis
    metrics["top_k_analysis"] = top_k_analysis

    trained_at = datetime.now(tz=timezone.utc)
    model_version = trained_at.strftime("continuity-risk-%Y%m%d-%H%M%S")
    run_name = _run_artifacts_folder_name(
        model_version=model_version,
        target=target,
        model_family=model_family,
        split_strategy=split_strategy,
        max_rows=max_rows,
        rows=len(df),
    )
    run_artifacts_dir = artifacts_dir / "runs" / run_name
    bundle = {
        "pipeline": model,
        "target": target,
        "model_version": model_version,
        "feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "trained_at": trained_at.isoformat(),
        "horizon_months": 12,
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / model_file
    joblib.dump(bundle, model_path)
    metadata = {
        "model_version": model_version,
        "run_name": run_name,
        "model_family": model_family,
        "model_params_overridden": bool(model_params),
        "model_params": model_params or {},
        "gpu": bool(gpu),
        "target": target,
        "horizon_months": 12,
        "eligible_rows": int(total_rows),
        "rows": int(len(df)),
        "dataset_column_count": int(len(all_source_columns)),
        "train_start_year": train_start_year,
        "train_end_year": train_end_year,
        "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        "class_counts_by_year": _counts_by_year(class_counts_by_year),
        "sample_strategy": sample_strategy,
        "max_rows": max_rows,
        "split_strategy": split_strategy,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_count": int(len(feature_columns)),
        "excluded_columns_count": int(len(excluded_columns_present)),
        "excluded_columns_present": excluded_columns_present,
        "train_missing_values": train_missing_values,
        "test_missing_values": test_missing_values,
        "train_class_counts": {
            str(k): int(v) for k, v in y_train.value_counts().to_dict().items()
        },
        "test_class_counts": {
            str(k): int(v) for k, v in y_test.value_counts().to_dict().items()
        },
        "feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "metrics": metrics,
        "model_file": str(model_path),
        "trained_at": trained_at.isoformat(),
        "run_artifacts_dir": str(run_artifacts_dir),
    }
    metadata["evaluation_artifacts"] = _write_evaluation_artifacts(
        run_artifacts_dir=run_artifacts_dir,
        metadata=metadata,
        y_true=y_test,
        probabilities=probabilities,
        threshold_analysis=threshold_analysis,
        class_counts_by_year=_counts_by_year(class_counts_by_year),
    )
    metadata["evaluation_artifacts"].update(
        _write_model_explanation_artifacts(
            run_artifacts_dir=run_artifacts_dir,
            model=model,
            X_test=X_test,
            y_test=y_test,
        )
    )
    run_summary_path = run_artifacts_dir / "run_summary.md"
    _write_run_summary(run_summary_path, metadata)
    metadata["evaluation_artifacts"]["run_summary_md"] = str(run_summary_path)
    run_index_path = artifacts_dir / "model_run_index.jsonl"
    _append_run_index(run_index_path, metadata)
    metadata["evaluation_artifacts"].update(
        _write_run_comparison_artifacts(
            run_index_path=run_index_path,
            artifacts_dir=artifacts_dir,
        )
    )
    (artifacts_dir / "model_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    (run_artifacts_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    logger.info("trained model=%s rows=%d metrics=%s", model_path, len(df), metrics)


def _safe_metric(func: Any, y_true: Any, y_score: Any) -> float | None:
    try:
        return float(func(y_true, y_score))
    except Exception:
        return None


def _threshold_analysis(
    y_true: Any,
    y_score: Any,
    thresholds: tuple[float, ...] = (
        0.001,
        0.005,
        0.01,
        0.02,
        0.05,
        0.10,
        0.20,
        0.30,
        0.50,
    ),
) -> list[dict[str, float | int]]:
    import numpy as np

    y_true_arr = np.asarray(y_true, dtype=int)
    y_score_arr = np.asarray(y_score, dtype=float)
    rows: list[dict[str, float | int]] = []
    total = int(len(y_true_arr))
    positives = int(y_true_arr.sum())
    negatives = total - positives
    for threshold in thresholds:
        predicted = y_score_arr >= threshold
        tp = int(((predicted == 1) & (y_true_arr == 1)).sum())
        fp = int(((predicted == 1) & (y_true_arr == 0)).sum())
        fn = int(((predicted == 0) & (y_true_arr == 1)).sum())
        tn = int(((predicted == 0) & (y_true_arr == 0)).sum())
        predicted_positive = tp + fp
        rows.append(
            {
                "threshold": float(threshold),
                "predicted_positive": predicted_positive,
                "flagged_rate": _safe_divide(predicted_positive, total),
                "precision": _safe_divide(tp, predicted_positive),
                "recall": _safe_divide(tp, positives),
                "false_positive_rate": _safe_divide(fp, negatives),
                "f1": _safe_divide(2 * tp, 2 * tp + fp + fn),
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": tn,
            }
        )
    return rows


def _top_k_analysis(
    y_true: Any,
    y_score: Any,
    fractions: tuple[float, ...] = (0.001, 0.005, 0.01, 0.05, 0.10),
) -> list[dict[str, float | int | str]]:
    import numpy as np

    y_true_arr = np.asarray(y_true, dtype=int)
    y_score_arr = np.asarray(y_score, dtype=float)
    total = int(len(y_true_arr))
    positives = int(y_true_arr.sum())
    base_rate = _safe_divide(positives, total)
    order = np.argsort(-y_score_arr)
    rows: list[dict[str, float | int | str]] = []
    for fraction in fractions:
        top_n = max(1, int(math.ceil(total * fraction)))
        selected = order[:top_n]
        selected_positives = int(y_true_arr[selected].sum())
        precision = _safe_divide(selected_positives, top_n)
        rows.append(
            {
                "segment": f"top_{fraction:.1%}",
                "fraction": float(fraction),
                "selected_rows": top_n,
                "true_positive": selected_positives,
                "precision": precision,
                "recall": _safe_divide(selected_positives, positives),
                "lift": _safe_divide(precision, base_rate),
            }
        )
    return rows


def _safe_divide(numerator: float | int, denominator: float | int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _write_evaluation_artifacts(
    *,
    run_artifacts_dir: Path,
    metadata: dict[str, Any],
    y_true: Any,
    probabilities: Any,
    threshold_analysis: list[dict[str, float | int]],
    class_counts_by_year: dict[str, dict[str, int]],
) -> dict[str, str]:
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    threshold_path = run_artifacts_dir / "threshold_analysis.csv"
    _write_csv(threshold_path, threshold_analysis)
    artifacts["threshold_analysis_csv"] = str(threshold_path)

    top_k_path = run_artifacts_dir / "top_k_analysis.csv"
    _write_csv(top_k_path, metadata["metrics"]["top_k_analysis"])
    artifacts["top_k_analysis_csv"] = str(top_k_path)

    class_counts_path = run_artifacts_dir / "class_counts_by_year.json"
    class_counts_path.write_text(
        json.dumps(class_counts_by_year, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifacts["class_counts_by_year_json"] = str(class_counts_path)

    metrics_path = run_artifacts_dir / "metrics_summary.csv"
    _write_csv(metrics_path, [_flat_metric_row(metadata)])
    artifacts["metrics_summary_csv"] = str(metrics_path)

    try:
        plot_paths = _write_evaluation_plots(
            run_artifacts_dir=run_artifacts_dir,
            metadata=metadata,
            y_true=y_true,
            probabilities=probabilities,
            threshold_analysis=threshold_analysis,
            class_counts_by_year=class_counts_by_year,
        )
        artifacts.update(plot_paths)
    except Exception as exc:
        error_path = run_artifacts_dir / "plot_error.txt"
        error_path.write_text(str(exc), encoding="utf-8")
        artifacts["plot_error"] = str(error_path)

    return artifacts


def _write_model_explanation_artifacts(
    *,
    run_artifacts_dir: Path,
    model: Any,
    X_test: Any,
    y_test: Any,
    n_repeats: int = 5,
    sample_size: int = 50_000,
) -> dict[str, str]:
    """Permutation importance on a capped test slice.

    Trees don't expose coefficients, so we shuffle each feature in turn and
    measure the drop in ROC-AUC. Capped to ``sample_size`` rows because
    permutation importance refits ``predict_proba`` once per feature per
    repeat; on the full 291k test set with 30+ features and 5 repeats the
    runtime blows past 20 minutes.
    """
    from sklearn.inspection import permutation_importance

    artifacts: dict[str, str] = {}
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)

    try:
        if len(X_test) > sample_size:
            sampled = X_test.sample(n=sample_size, random_state=42)
            y_sampled = y_test.loc[sampled.index]
        else:
            sampled = X_test
            y_sampled = y_test

        result = permutation_importance(
            model,
            sampled,
            y_sampled,
            n_repeats=n_repeats,
            scoring="roc_auc",
            random_state=42,
            n_jobs=1,
        )
        feature_names = list(X_test.columns)
        rows = [
            {
                "feature": str(name),
                "importance_mean": float(result.importances_mean[idx]),
                "importance_std": float(result.importances_std[idx]),
            }
            for idx, name in enumerate(feature_names)
        ]
        rows.sort(key=lambda row: float(row["importance_mean"]), reverse=True)
        importances_path = run_artifacts_dir / "feature_importances.csv"
        _write_csv(importances_path, rows)
        artifacts["feature_importances_csv"] = str(importances_path)
    except Exception as exc:
        error_path = run_artifacts_dir / "feature_importances_error.txt"
        error_path.write_text(str(exc), encoding="utf-8")
        artifacts["feature_importances_error"] = str(error_path)
        return artifacts

    try:
        plot_path = run_artifacts_dir / "top_feature_importances.png"
        _write_top_importances_plot(plot_path, rows[:30])
        artifacts["top_feature_importances_png"] = str(plot_path)
    except Exception as exc:
        error_path = run_artifacts_dir / "feature_importances_plot_error.txt"
        error_path.write_text(str(exc), encoding="utf-8")
        artifacts["feature_importances_plot_error"] = str(error_path)

    return artifacts


def _write_top_importances_plot(path: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        path.write_text("No importance rows available.", encoding="utf-8")
        return
    rows_for_plot = list(reversed(rows))
    labels = [str(row["feature"])[:70] for row in rows_for_plot]
    values = [float(row["importance_mean"]) for row in rows_for_plot]
    errors = [float(row["importance_std"]) for row in rows_for_plot]
    fig_height = max(5.0, len(rows_for_plot) * 0.28)
    fig, ax = plt.subplots(figsize=(9, fig_height))
    ax.barh(
        range(len(rows_for_plot)),
        values,
        xerr=errors,
        color="#0f766e",
        alpha=0.82,
        error_kw={"ecolor": "#0f172a", "alpha": 0.6, "capsize": 2},
    )
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(range(len(rows_for_plot)), labels=labels)
    ax.set_title("Top Permutation Importances (ROC-AUC drop)")
    ax.set_xlabel("Mean ROC-AUC drop when feature is shuffled (± std)")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _flat_metric_row(metadata: dict[str, Any]) -> dict[str, Any]:
    metrics = metadata.get("metrics", {})
    class_counts = metadata.get("class_counts", {})
    train_class_counts = metadata.get("train_class_counts", {})
    test_class_counts = metadata.get("test_class_counts", {})
    rows = int(metadata.get("rows") or 0)
    positive_rows = int(class_counts.get("1") or class_counts.get(1) or 0)
    negative_rows = int(class_counts.get("0") or class_counts.get(0) or 0)
    return {
        "model_version": metadata.get("model_version"),
        "run_name": metadata.get("run_name"),
        "trained_at": metadata.get("trained_at"),
        "target": metadata.get("target"),
        "rows": rows,
        "columns": metadata.get("dataset_column_count"),
        "feature_count": metadata.get("feature_count"),
        "excluded_columns_count": metadata.get("excluded_columns_count"),
        "positive_rows": positive_rows,
        "negative_rows": negative_rows,
        "positive_rate": _safe_divide(positive_rows, rows),
        "train_rows": metadata.get("train_rows"),
        "train_positive_rows": train_class_counts.get("1"),
        "test_rows": metadata.get("test_rows"),
        "test_positive_rows": test_class_counts.get("1"),
        "train_missing_values": metadata.get("train_missing_values"),
        "test_missing_values": metadata.get("test_missing_values"),
        "sample_strategy": metadata.get("sample_strategy"),
        "split_strategy": metadata.get("split_strategy"),
        "accuracy": metrics.get("accuracy"),
        "roc_auc": metrics.get("roc_auc"),
        "average_precision": metrics.get("average_precision"),
        "precision_at_0_5": metrics.get("precision_at_0_5"),
        "recall_at_0_5": metrics.get("recall_at_0_5"),
        "f1_at_0_5": metrics.get("f1_at_0_5"),
    }


def _run_artifacts_folder_name(
    *,
    model_version: str,
    target: str,
    model_family: str,
    split_strategy: str,
    max_rows: int | None,
    rows: int,
) -> str:
    timestamp = model_version.replace("continuity-risk-", "")
    target_slug = _slugify(_strip_suffix(target, "_label"))
    split_slug = _short_split_slug(split_strategy)
    cap_slug = f"cap-{_compact_count(max_rows)}" if max_rows else "full-data"
    rows_slug = f"rows-{_compact_count(rows)}"
    return "_".join(
        part
        for part in (
            timestamp,
            target_slug,
            _slugify(model_family),
            split_slug,
            cap_slug,
            rows_slug,
        )
        if part
    )


def _short_split_slug(split_strategy: str) -> str:
    prefix = "time_split_latest_year_"
    if split_strategy.startswith(prefix):
        return f"time-test-{_slugify(split_strategy[len(prefix):])}"
    if split_strategy == "stratified_random_split":
        return "stratified-random"
    return _slugify(split_strategy)


def _slugify(value: str) -> str:
    chars: list[str] = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    return "".join(chars).strip("-")


def _strip_suffix(value: str, suffix: str) -> str:
    if value.endswith(suffix):
        return value[: -len(suffix)]
    return value


def _compact_count(value: int | None) -> str:
    if value is None:
        return "none"
    absolute = abs(int(value))
    if absolute >= 1_000_000:
        compact = value / 1_000_000
        text = f"{compact:.1f}".rstrip("0").rstrip(".").replace(".", "p")
        return f"{text}m"
    if absolute >= 1_000:
        compact = value / 1_000
        text = f"{compact:.1f}".rstrip("0").rstrip(".").replace(".", "p")
        return f"{text}k"
    return str(value)


def _write_run_summary(path: Path, metadata: dict[str, Any]) -> None:
    metrics = metadata.get("metrics", {})
    class_counts = metadata.get("class_counts", {})
    train_counts = metadata.get("train_class_counts", {})
    test_counts = metadata.get("test_class_counts", {})
    confusion = metrics.get("confusion_matrix_at_0_5", {})
    positive_rows = int(class_counts.get("1") or class_counts.get(1) or 0)
    rows = int(metadata.get("rows") or 0)
    positive_rate = _safe_divide(positive_rows, rows)
    threshold_rows = metrics.get("threshold_analysis", [])
    top_k_rows = metrics.get("top_k_analysis", [])
    artifacts = metadata.get("evaluation_artifacts", {})

    lines = [
        f"# ML Run Summary: {metadata.get('run_name') or metadata.get('model_version')}",
        "",
        "## Dataset And Split",
        "",
        "| Item | Value |",
        "|---|---:|",
        f"| Eligible rows before cap | {_fmt_int(metadata.get('eligible_rows'))} |",
        f"| Training dataset rows | {_fmt_int(metadata.get('rows'))} |",
        f"| Dataset columns | {_fmt_int(metadata.get('dataset_column_count'))} |",
        f"| Feature count | {_fmt_int(metadata.get('feature_count'))} |",
        f"| Excluded leakage/identifier columns | {_fmt_int(metadata.get('excluded_columns_count'))} |",
        f"| Positive rows | {_fmt_int(positive_rows)} |",
        f"| Negative rows | {_fmt_int(class_counts.get('0'))} |",
        f"| Positive rate | {_fmt_pct(positive_rate)} |",
        f"| Train rows | {_fmt_int(metadata.get('train_rows'))} |",
        f"| Train positives | {_fmt_int(train_counts.get('1'))} |",
        f"| Test rows | {_fmt_int(metadata.get('test_rows'))} |",
        f"| Test positives | {_fmt_int(test_counts.get('1'))} |",
        f"| Missing values in X_train | {_fmt_int(metadata.get('train_missing_values'))} |",
        f"| Missing values in X_test | {_fmt_int(metadata.get('test_missing_values'))} |",
        "",
        "## Experimental Design",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Run folder | `{metadata.get('run_name')}` |",
        f"| Model version | `{metadata.get('model_version')}` |",
        f"| Target | `{metadata.get('target')}` |",
        f"| Horizon | {metadata.get('horizon_months')} months |",
        f"| Sampling strategy | `{metadata.get('sample_strategy')}` |",
        f"| Split strategy | `{metadata.get('split_strategy')}` |",
        f"| Train year range | {metadata.get('train_start_year')} to {metadata.get('train_end_year')} |",
        "",
        "## Main Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Accuracy | {_fmt_float(metrics.get('accuracy'))} |",
        f"| ROC AUC | {_fmt_float(metrics.get('roc_auc'))} |",
        f"| Average precision | {_fmt_float(metrics.get('average_precision'))} |",
        f"| Precision at 0.5 | {_fmt_float(metrics.get('precision_at_0_5'))} |",
        f"| Recall at 0.5 | {_fmt_float(metrics.get('recall_at_0_5'))} |",
        f"| F1 at 0.5 | {_fmt_float(metrics.get('f1_at_0_5'))} |",
        "",
        "## Confusion Matrix At Threshold 0.5",
        "",
        "| Actual / Predicted | Predicted 0 | Predicted 1 |",
        "|---|---:|---:|",
        f"| Actual 0 | {_fmt_int(confusion.get('true_negative'))} | {_fmt_int(confusion.get('false_positive'))} |",
        f"| Actual 1 | {_fmt_int(confusion.get('false_negative'))} | {_fmt_int(confusion.get('true_positive'))} |",
    ]

    if threshold_rows:
        lines.extend(
            [
                "",
                "## Threshold Analysis",
                "",
                "| Threshold | Flagged rate | Precision | Recall | F1 |",
                "|---:|---:|---:|---:|---:|",
            ]
        )
        for row in threshold_rows:
            lines.append(
                "| "
                f"{_fmt_float(row.get('threshold'), digits=3)} | "
                f"{_fmt_pct(row.get('flagged_rate'))} | "
                f"{_fmt_float(row.get('precision'))} | "
                f"{_fmt_float(row.get('recall'))} | "
                f"{_fmt_float(row.get('f1'))} |"
            )

    if top_k_rows:
        lines.extend(
            [
                "",
                "## Top-Risk Capture",
                "",
                "| Segment | Rows | Precision | Recall | Lift |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in top_k_rows:
            lines.append(
                "| "
                f"{row.get('segment')} | "
                f"{_fmt_int(row.get('selected_rows'))} | "
                f"{_fmt_float(row.get('precision'))} | "
                f"{_fmt_float(row.get('recall'))} | "
                f"{_fmt_float(row.get('lift'))} |"
            )

    lines.extend(
        [
            "",
            "## Generated Report Images",
            "",
            "| Image | File |",
            "|---|---|",
        ]
    )
    for key in (
        "precision_recall_curve_png",
        "roc_curve_png",
        "confusion_matrix_at_0_5_png",
        "score_distribution_by_class_png",
        "threshold_tradeoff_png",
        "class_counts_by_year_png",
        "top_feature_importances_png",
    ):
        if key in artifacts:
            lines.append(f"| {key} | `{Path(str(artifacts[key])).name}` |")

    lines.extend(
        [
            "",
            "## Interpretation Template",
            "",
            "This run should be interpreted as a rare-event ranking experiment. Accuracy is secondary because the target is imbalanced. The strongest evidence is the temporal split strategy, average precision, threshold behavior, top-risk capture, and class balance by year.",
            "",
            "## Next Action",
            "",
            "Compare this run against previous entries in `model_run_index.jsonl`. If the split is temporal and the average precision remains above the positive base rate, proceed to threshold selection before changing the model family.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _fmt_int(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _fmt_float(value: Any, *, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_evaluation_plots(
    *,
    run_artifacts_dir: Path,
    metadata: dict[str, Any],
    y_true: Any,
    probabilities: Any,
    threshold_analysis: list[dict[str, float | int]],
    class_counts_by_year: dict[str, dict[str, int]],
) -> dict[str, str]:
    import numpy as np
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve, roc_curve

    y_true_arr = np.asarray(y_true, dtype=int)
    y_score_arr = np.asarray(probabilities, dtype=float)
    plot_paths: dict[str, str] = {}

    precision, recall, _ = precision_recall_curve(y_true_arr, y_score_arr)
    pr_path = run_artifacts_dir / "precision_recall_curve.png"
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(recall, precision, linewidth=2)
    ax.set_title("Precision-Recall Curve")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.grid(True, alpha=0.3)
    average_precision = metadata["metrics"].get("average_precision")
    if average_precision is not None:
        ax.text(
            0.02,
            0.95,
            f"Average precision = {average_precision:.4f}",
            transform=ax.transAxes,
            va="top",
        )
    fig.tight_layout()
    fig.savefig(pr_path, dpi=160)
    plt.close(fig)
    plot_paths["precision_recall_curve_png"] = str(pr_path)

    roc_path = run_artifacts_dir / "roc_curve.png"
    fig, ax = plt.subplots(figsize=(7, 5))
    fpr, tpr, _ = roc_curve(y_true_arr, y_score_arr)
    ax.plot(fpr, tpr, linewidth=2)
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
    ax.set_title("ROC Curve")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.grid(True, alpha=0.3)
    roc_auc = metadata["metrics"].get("roc_auc")
    if roc_auc is not None:
        ax.text(0.02, 0.95, f"ROC AUC = {roc_auc:.4f}", transform=ax.transAxes, va="top")
    fig.tight_layout()
    fig.savefig(roc_path, dpi=160)
    plt.close(fig)
    plot_paths["roc_curve_png"] = str(roc_path)

    matrix_path = run_artifacts_dir / "confusion_matrix_at_0_5.png"
    confusion = metadata["metrics"]["confusion_matrix_at_0_5"]
    matrix = np.array(
        [
            [confusion["true_negative"], confusion["false_positive"]],
            [confusion["false_negative"], confusion["true_positive"]],
        ]
    )
    fig, ax = plt.subplots(figsize=(5.5, 5))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_title("Confusion Matrix At Threshold 0.5")
    ax.set_xticks([0, 1], labels=["Predicted 0", "Predicted 1"])
    ax.set_yticks([0, 1], labels=["Actual 0", "Actual 1"])
    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            ax.text(col_idx, row_idx, f"{matrix[row_idx, col_idx]:,}", ha="center", va="center")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(matrix_path, dpi=160)
    plt.close(fig)
    plot_paths["confusion_matrix_at_0_5_png"] = str(matrix_path)

    distribution_path = run_artifacts_dir / "score_distribution_by_class.png"
    fig, ax = plt.subplots(figsize=(7, 5))
    negative_scores = y_score_arr[y_true_arr == 0]
    positive_scores = y_score_arr[y_true_arr == 1]
    bins = np.linspace(0.0, 1.0, 51)
    ax.hist(negative_scores, bins=bins, alpha=0.65, label="Actual 0", density=True)
    ax.hist(positive_scores, bins=bins, alpha=0.65, label="Actual 1", density=True)
    ax.set_title("Predicted Score Distribution By Class")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Density")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(distribution_path, dpi=160)
    plt.close(fig)
    plot_paths["score_distribution_by_class_png"] = str(distribution_path)

    threshold_path = run_artifacts_dir / "threshold_tradeoff.png"
    thresholds = [float(row["threshold"]) for row in threshold_analysis]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(thresholds, [float(row["precision"]) for row in threshold_analysis], marker="o", label="Precision")
    ax.plot(thresholds, [float(row["recall"]) for row in threshold_analysis], marker="o", label="Recall")
    ax.plot(thresholds, [float(row["flagged_rate"]) for row in threshold_analysis], marker="o", label="Flagged rate")
    ax.set_title("Threshold Trade-Off")
    ax.set_xlabel("Decision threshold")
    ax.set_ylabel("Rate")
    ax.set_xscale("log")
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(threshold_path, dpi=160)
    plt.close(fig)
    plot_paths["threshold_tradeoff_png"] = str(threshold_path)

    year_path = run_artifacts_dir / "class_counts_by_year.png"
    years = sorted(class_counts_by_year, key=int)
    negatives = [class_counts_by_year[year].get("0", 0) for year in years]
    positives = [class_counts_by_year[year].get("1", 0) for year in years]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(years, negatives, label="Negative")
    ax.bar(years, positives, bottom=negatives, label="Positive")
    ax.set_title("Class Counts By Prediction Year")
    ax.set_xlabel("Prediction year")
    ax.set_ylabel("Rows")
    ax.legend()
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(year_path, dpi=160)
    plt.close(fig)
    plot_paths["class_counts_by_year_png"] = str(year_path)

    return plot_paths


def _append_run_index(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = metadata.get("metrics", {})
    row = {
        "model_version": metadata.get("model_version"),
        "run_name": metadata.get("run_name"),
        "model_family": metadata.get("model_family"),
        "trained_at": metadata.get("trained_at"),
        "target": metadata.get("target"),
        "rows": metadata.get("rows"),
        "dataset_column_count": metadata.get("dataset_column_count"),
        "feature_count": metadata.get("feature_count"),
        "eligible_rows": metadata.get("eligible_rows"),
        "max_rows": metadata.get("max_rows"),
        "sample_strategy": metadata.get("sample_strategy"),
        "split_strategy": metadata.get("split_strategy"),
        "train_rows": metadata.get("train_rows"),
        "test_rows": metadata.get("test_rows"),
        "test_class_counts": metadata.get("test_class_counts"),
        "accuracy": metrics.get("accuracy"),
        "roc_auc": metrics.get("roc_auc"),
        "average_precision": metrics.get("average_precision"),
        "precision_at_0_5": metrics.get("precision_at_0_5"),
        "recall_at_0_5": metrics.get("recall_at_0_5"),
        "f1_at_0_5": metrics.get("f1_at_0_5"),
        "run_artifacts_dir": metadata.get("run_artifacts_dir"),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")


def _write_run_comparison_artifacts(
    *,
    run_index_path: Path,
    artifacts_dir: Path,
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    try:
        rows = _read_jsonl(run_index_path)
        comparison_rows = [_comparison_row(row) for row in rows]
        comparison_csv = artifacts_dir / "model_run_comparison.csv"
        _write_csv(comparison_csv, comparison_rows)
        artifacts["model_run_comparison_csv"] = str(comparison_csv)
    except Exception as exc:
        error_path = artifacts_dir / "model_run_comparison_error.txt"
        error_path.write_text(str(exc), encoding="utf-8")
        artifacts["model_run_comparison_error"] = str(error_path)
        return artifacts

    try:
        comparison_png = artifacts_dir / "model_run_comparison.png"
        _write_run_comparison_plot(comparison_png, comparison_rows)
        artifacts["model_run_comparison_png"] = str(comparison_png)
    except Exception as exc:
        error_path = artifacts_dir / "model_run_comparison_plot_error.txt"
        error_path.write_text(str(exc), encoding="utf-8")
        artifacts["model_run_comparison_plot_error"] = str(error_path)

    return artifacts


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _comparison_row(row: dict[str, Any]) -> dict[str, Any]:
    test_counts = row.get("test_class_counts") or {}
    test_rows = int(row.get("test_rows") or 0)
    test_positives = int(test_counts.get("1") or test_counts.get(1) or 0)
    return {
        "model_version": row.get("model_version"),
        "run_name": row.get("run_name"),
        "model_family": row.get("model_family"),
        "trained_at": row.get("trained_at"),
        "target": row.get("target"),
        "rows": row.get("rows"),
        "dataset_column_count": row.get("dataset_column_count"),
        "feature_count": row.get("feature_count"),
        "max_rows": row.get("max_rows"),
        "split_strategy": row.get("split_strategy"),
        "sample_strategy": row.get("sample_strategy"),
        "test_rows": test_rows,
        "test_positive_rows": test_positives,
        "test_positive_rate": _safe_divide(test_positives, test_rows),
        "average_precision": row.get("average_precision"),
        "roc_auc": row.get("roc_auc"),
        "precision_at_0_5": row.get("precision_at_0_5"),
        "recall_at_0_5": row.get("recall_at_0_5"),
        "f1_at_0_5": row.get("f1_at_0_5"),
        "run_artifacts_dir": row.get("run_artifacts_dir"),
    }


def _write_run_comparison_plot(path: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        path.write_text("No training runs available.", encoding="utf-8")
        return
    labels = [
        str(row.get("run_name") or row.get("model_version", f"run_{idx + 1}")).replace("continuity-risk-", "")
        for idx, row in enumerate(rows)
    ]
    x_values = list(range(len(rows)))
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(
        x_values,
        [_none_to_nan(row.get("average_precision")) for row in rows],
        marker="o",
        label="Average precision",
    )
    axes[0].plot(
        x_values,
        [_none_to_nan(row.get("roc_auc")) for row in rows],
        marker="o",
        label="ROC AUC",
    )
    axes[0].set_title("Model Run Comparison")
    axes[0].set_ylabel("Metric")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(
        x_values,
        [_none_to_nan(row.get("test_positive_rate")) for row in rows],
        marker="o",
        color="#64748b",
        label="Test positive rate",
    )
    axes[1].set_ylabel("Test positive rate")
    axes[1].set_xlabel("Run")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_xticks(x_values, labels=labels, rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _none_to_nan(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        return float(value)
    except Exception:
        return math.nan


def _count_training_rows(
    con: Any,
    *,
    features_path: Path,
    labels_path: Path,
    target: str,
    where_sql: str,
) -> int:
    query = f"""
        SELECT COUNT(*) AS rows
        FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true) f
        JOIN read_parquet('{_sql_string(_glob(labels_path))}', union_by_name=true) l
          USING (siren, prediction_year)
        WHERE {where_sql}
    """
    return int(con.execute(query).fetchone()[0])


def _row_hash_sql() -> str:
    return "hash(CAST(f.siren AS VARCHAR) || ':' || CAST(f.prediction_year AS VARCHAR))"


def _list_columns(con: Any, glob_path: str) -> list[str]:
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{_sql_string(glob_path)}', union_by_name=true)"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _counts_by_year(counts: Any) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for year, row in counts.iterrows():
        result[str(int(year))] = {str(int(label)): int(value) for label, value in row.items()}
    return result


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
    parser.add_argument(
        "--model-family",
        choices=MODEL_FAMILIES,
        default="hgb",
        help="Gradient-boosting library to train.",
    )
    parser.add_argument(
        "--params-file",
        help="Path to a JSON file with classifier kwargs overriding the family defaults (used to inject Phase B tuned hyperparameters).",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Enable GPU training for CatBoost (task_type=GPU) and XGBoost (device=cuda). HGB and LightGBM ignore this flag.",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
