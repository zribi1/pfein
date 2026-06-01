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


from sklearn.base import BaseEstimator, ClassifierMixin


class _CatBoostSklearnClassifier(ClassifierMixin, BaseEstimator):
    """sklearn-clone-safe wrapper around ``catboost.CatBoostClassifier``.

    Native ``CatBoostClassifier`` mutates list-typed constructor params
    (``cat_features``, ``class_weights``) internally — ``get_params()`` returns
    a different object id than what was passed, which breaks sklearn's
    ``clone()`` identity check inside ``RandomizedSearchCV``.

    Inherits from ``ClassifierMixin`` (declares ``_estimator_type='classifier'``
    so sklearn scorers route through ``predict_proba``) and ``BaseEstimator``
    (auto-derives ``get_params``/``set_params`` from the ``__init__`` signature
    — clone-safe because we store every arg verbatim).
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

# Bumped when the set of per-run outputs changes. Lets you tell new-style runs
# (credit-risk metrics + calibration + SHAP + valid-coverage conformal) apart
# from older ones. 2.2 fixes the 2.1 conformal under-coverage on drifted years.
OUTPUT_SCHEMA_VERSION = "2.2-conformal-valid-coverage"


class MondrianConformalCalibrator:
    """Class-conditional (Mondrian) inductive conformal predictor for binary
    classification.

    Nonconformity score of an example is ``1 - p_hat(its true class)``. Scores
    are collected on a calibration holdout the underlying model did NOT train
    on, so per-prediction confidence carries the standard conformal validity
    guarantee (error rate <= significance level, in expectation).

    Class-conditional ("Mondrian") because the target is heavily imbalanced:
    pooling the calibration scores would let the ~97% negatives swamp the
    positive-class p-values and distort confidence on the rare positives.

    For a new example it returns, per company:
      - predicted_label : class with the largest p-value
      - confidence      : 1 - second-largest p-value (sureness it is THAT class)
      - credibility     : largest p-value (how well the example fits training at all)

    Module-level so a fitted instance round-trips through joblib.
    """

    def __init__(self) -> None:
        self.cal_scores_: dict[int, Any] = {}

    def fit(self, prob_positive: Any, y_true: Any) -> "MondrianConformalCalibrator":
        import numpy as np

        p1 = np.asarray(prob_positive, dtype=float)
        y = np.asarray(y_true, dtype=int)
        # Nonconformity = 1 - p_hat(true class); store sorted, per class.
        self.cal_scores_ = {
            1: np.sort(1.0 - p1[y == 1]),
            0: np.sort(1.0 - (1.0 - p1[y == 0])),  # = p1 for the true-negative rows
        }
        return self

    def predict(self, prob_positive: Any) -> dict[str, Any]:
        import numpy as np

        p1 = np.asarray(prob_positive, dtype=float)
        s1 = self.cal_scores_[1]
        s0 = self.cal_scores_[0]
        n1, n0 = len(s1), len(s0)
        if n1 == 0 or n0 == 0:
            raise ValueError("conformal calibration set is missing one class")
        # p-value for label l = (#calib scores >= new nonconformity + 1) / (n + 1).
        ge1 = n1 - np.searchsorted(s1, 1.0 - p1, side="left")
        pval1 = (ge1 + 1.0) / (n1 + 1.0)
        ge0 = n0 - np.searchsorted(s0, p1, side="left")
        pval0 = (ge0 + 1.0) / (n0 + 1.0)
        return {
            "predicted_label": (pval1 >= pval0).astype(int),
            "confidence": 1.0 - np.minimum(pval0, pval1),
            "credibility": np.maximum(pval0, pval1),
            "p_value_0": pval0,
            "p_value_1": pval1,
        }

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {}

    def set_params(self, **params: Any) -> "MondrianConformalCalibrator":
        return self


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
        calibrate=args.calibrate,
        calibration_fraction=args.calibration_fraction,
        shap_enabled=args.shap,
        shap_sample=args.shap_sample,
        run_tag=args.run_tag,
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
    calibrate: bool = True,
    calibration_fraction: float = 0.15,
    shap_enabled: bool = True,
    shap_sample: int = 10000,
    run_tag: str | None = None,
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

    # Calibration: fit the model on (1 - calibration_fraction) of the training
    # rows and fit an isotonic calibrator on the held-out slice. The slice is
    # NOT used to train the model, so the calibrator stays honest, and the test
    # year is left fully untouched. The saved model is the one trained on the
    # 85% slice, so model and calibrator are mutually consistent.
    calibrator = None
    calibration_fit_rows = None
    if calibrate and y_train.nunique() == 2:
        from sklearn.isotonic import IsotonicRegression

        X_fit, X_calib, y_fit, y_calib = train_test_split(
            X_train,
            y_train,
            test_size=calibration_fraction,
            random_state=42,
            stratify=y_train if y_train.value_counts().min() >= 2 else None,
        )
        model.fit(X_fit, y_fit)
        calib_raw = model.predict_proba(X_calib)[:, 1]
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(calib_raw, y_calib.to_numpy().astype(float))
        calibration_fit_rows = int(len(X_fit))
    else:
        calibrate = False
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

    metrics.update(_advanced_metrics(y_test, probabilities, predictions))
    calibration_table, ece = _calibration_table(y_test, probabilities)
    metrics["expected_calibration_error"] = ece
    metrics["calibration_table"] = calibration_table
    metrics["decile_table"] = _decile_table(y_test, probabilities)

    # Calibrated probability metrics (ranking metrics are unchanged by the
    # monotonic isotonic map, so only the probability-quality ones are added).
    if calibrator is not None:
        from sklearn.metrics import brier_score_loss, log_loss

        calibrated = calibrator.predict(probabilities)
        calibrated_table, calibrated_ece = _calibration_table(y_test, calibrated)
        metrics["calibrated_brier_score"] = _safe_metric(brier_score_loss, y_test, calibrated)
        try:
            metrics["calibrated_log_loss"] = float(log_loss(y_test, calibrated, labels=[0, 1]))
        except Exception:
            metrics["calibrated_log_loss"] = None
        metrics["calibrated_expected_calibration_error"] = calibrated_ece
        metrics["calibrated_calibration_table"] = calibrated_table

    # Conformal confidence. The coverage guarantee requires the calibration set
    # be exchangeable with what we score. Calibrating on the training years
    # (2017-2023) and scoring the test year (2024) breaks that -- the documented
    # temporal drift makes conformal UNDER-cover on 2024. So we split the test
    # year itself 50/50: fit conformal on one half, measure validity on the
    # disjoint half. The model never trained on any test-year row, so the halves
    # are exchangeable and coverage holds. The saved calibrator is fit on recent
    # (test-year) data, which is also the right basis for scoring live companies.
    # Uses the model's RAW scores (independent of the isotonic map). Fail-soft.
    conformal = None
    if y_test.nunique() == 2:
        try:
            y_test_arr = y_test.to_numpy().astype(int)
            cal_idx, eval_idx = train_test_split(
                np.arange(len(y_test_arr)),
                test_size=0.5,
                random_state=42,
                stratify=y_test_arr,
            )
            conformal = MondrianConformalCalibrator().fit(
                probabilities[cal_idx], y_test_arr[cal_idx]
            )
            cp = conformal.predict(probabilities[eval_idx])
            eval_y = y_test_arr[eval_idx]
            pval_true = np.where(eval_y == 1, cp["p_value_1"], cp["p_value_0"])
            validity = []
            for eps in (0.01, 0.05, 0.10, 0.20):
                set_size = (cp["p_value_0"] > eps).astype(int) + (cp["p_value_1"] > eps).astype(int)
                validity.append({
                    "significance": eps,
                    "target_confidence": round(1.0 - eps, 2),
                    "empirical_error": float((pval_true <= eps).mean()),
                    "avg_set_size": float(set_size.mean()),
                    "singleton_rate": float((set_size == 1).mean()),
                    "empty_rate": float((set_size == 0).mean()),
                })
            counts, edges = np.histogram(cp["confidence"], bins=10, range=(0.0, 1.0))
            metrics["conformal_mean_confidence"] = float(cp["confidence"].mean())
            metrics["conformal_mean_credibility"] = float(cp["credibility"].mean())
            metrics["conformal_calibration_source"] = "test_year_holdout_50pct"
            metrics["conformal_validity"] = validity
            metrics["conformal_confidence_hist"] = [
                {"bin_lower": float(edges[i]), "bin_upper": float(edges[i + 1]), "count": int(counts[i])}
                for i in range(len(counts))
            ]
        except Exception as exc:
            conformal = None
            metrics["conformal_error"] = f"{type(exc).__name__}: {exc}"

    trained_at = datetime.now(tz=timezone.utc)
    model_version = trained_at.strftime("continuity-risk-%Y%m%d-%H%M%S")
    effective_run_tag = run_tag if run_tag else _detect_feature_schema(data_lake_dir)
    run_name = _run_artifacts_folder_name(
        model_version=model_version,
        target=target,
        model_family=model_family,
        split_strategy=split_strategy,
        max_rows=max_rows,
        rows=len(df),
        run_tag=effective_run_tag,
    )
    # Group runs by family on disk so the layout is self-evident:
    #   ml-artifacts/runs/hgb/<run_name>/...
    #   ml-artifacts/runs/catboost/<run_name>/...
    # Old runs at ml-artifacts/runs/<run_name>/ stay where they are; consumers
    # of archived runs look in both locations.
    run_artifacts_dir = artifacts_dir / "runs" / model_family / run_name
    bundle = {
        "pipeline": model,
        "target": target,
        "model_version": model_version,
        "feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "trained_at": trained_at.isoformat(),
        "horizon_months": 12,
        "calibrator": calibrator,
        "conformal": conformal,
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / model_file
    joblib.dump(bundle, model_path)

    # Archive a per-run copy. The root model_file is overwritten on every run,
    # so without this the only deployable artifact is always the latest run --
    # never the best. The interrogation notebook resolves this path when present.
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)
    archived_model_path = run_artifacts_dir / model_file
    joblib.dump(bundle, archived_model_path)

    # Standalone calibrator next to both the live and archived model, matching
    # the path the interrogation notebook already probes (isotonic_calibrator.joblib).
    if calibrator is not None:
        joblib.dump(calibrator, artifacts_dir / "isotonic_calibrator.joblib")
        joblib.dump(calibrator, run_artifacts_dir / "isotonic_calibrator.joblib")
    if conformal is not None:
        joblib.dump(conformal, artifacts_dir / "conformal_calibrator.joblib")
        joblib.dump(conformal, run_artifacts_dir / "conformal_calibrator.joblib")
    metadata = {
        "model_version": model_version,
        "run_name": run_name,
        "model_family": model_family,
        "model_params_overridden": bool(model_params),
        "model_params": model_params or {},
        "gpu": bool(gpu),
        "target": target,
        "horizon_months": 12,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "calibrated": bool(calibrator is not None),
        "calibration_fraction": calibration_fraction if calibrator is not None else None,
        "calibration_fit_rows": calibration_fit_rows,
        "conformal": bool(conformal is not None),
        "run_tag": effective_run_tag,
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
        "archived_model_file": str(archived_model_path),
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
    if shap_enabled:
        metadata["evaluation_artifacts"].update(
            _write_shap_artifacts(
                run_artifacts_dir=run_artifacts_dir,
                model=model,
                X_test=X_test,
                scores=probabilities,
                sample_size=shap_sample,
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
    _write_outputs_manifest(run_artifacts_dir, metadata)
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


def _advanced_metrics(
    y_true: Any,
    y_score: Any,
    predictions: Any,
    *,
    bootstrap_iterations: int = 1000,
    random_state: int = 42,
) -> dict[str, Any]:
    """Credit-risk + calibration + balanced-threshold metrics, plus bootstrap CIs.

    Computed alongside the base metrics so every run carries them. None of these
    change the model -- they describe it more completely than AP/AUC alone.
    """
    import numpy as np
    from sklearn.metrics import (
        balanced_accuracy_score,
        brier_score_loss,
        log_loss,
        matthews_corrcoef,
        precision_recall_curve,
        roc_auc_score,
        roc_curve,
    )

    y = np.asarray(y_true, dtype=int)
    s = np.asarray(y_score, dtype=float)
    pred = np.asarray(predictions, dtype=int)
    out: dict[str, Any] = {}

    # Discrimination (rank-based, base-rate independent).
    auc = _safe_metric(roc_auc_score, y, s)
    out["gini"] = (2.0 * auc - 1.0) if auc is not None else None
    try:
        fpr, tpr, _ = roc_curve(y, s)
        out["ks_statistic"] = float(np.max(tpr - fpr))
    except Exception:
        out["ks_statistic"] = None

    # Probability quality (proper scoring rules -- sensitive to calibration).
    out["brier_score"] = _safe_metric(brier_score_loss, y, s)
    try:
        out["log_loss"] = float(log_loss(y, s, labels=[0, 1]))
    except Exception:
        out["log_loss"] = None

    # Balanced metrics at the 0.5 threshold.
    try:
        out["mcc"] = float(matthews_corrcoef(y, pred))
    except Exception:
        out["mcc"] = None
    try:
        out["balanced_accuracy"] = float(balanced_accuracy_score(y, pred))
    except Exception:
        out["balanced_accuracy"] = None
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    out["specificity_at_0_5"] = _safe_divide(tn, tn + fp)

    # Best precision attainable while holding recall >= target (operating-point design).
    try:
        precision, recall, _ = precision_recall_curve(y, s)
        for target in (0.5, 0.7, 0.9):
            mask = recall >= target
            out[f"precision_at_recall_{int(target * 100)}"] = (
                float(np.max(precision[mask])) if mask.any() else None
            )
    except Exception:
        for target in (50, 70, 90):
            out[f"precision_at_recall_{target}"] = None

    # Bootstrap 95% CIs for AUC and AP (defensibility -- report metric +/- band).
    auc_ci, ap_ci = _bootstrap_cis(y, s, iterations=bootstrap_iterations, random_state=random_state)
    out["roc_auc_ci95_low"], out["roc_auc_ci95_high"] = auc_ci
    out["average_precision_ci95_low"], out["average_precision_ci95_high"] = ap_ci
    return out


def _bootstrap_cis(
    y_true: Any,
    y_score: Any,
    *,
    iterations: int = 1000,
    random_state: int = 42,
) -> tuple[tuple[float | None, float | None], tuple[float | None, float | None]]:
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = np.asarray(y_true, dtype=int)
    s = np.asarray(y_score, dtype=float)
    n = len(y)
    if n == 0 or y.sum() == 0 or y.sum() == n:
        return (None, None), (None, None)
    rng = np.random.default_rng(random_state)
    aucs: list[float] = []
    aps: list[float] = []
    for _ in range(iterations):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue
        sb = s[idx]
        aucs.append(float(roc_auc_score(yb, sb)))
        aps.append(float(average_precision_score(yb, sb)))
    if not aucs:
        return (None, None), (None, None)
    auc_ci = (float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5)))
    ap_ci = (float(np.percentile(aps, 2.5)), float(np.percentile(aps, 97.5)))
    return auc_ci, ap_ci


def _decile_table(y_true: Any, y_score: Any, *, n_bins: int = 10) -> list[dict[str, Any]]:
    """Risk deciles ranked highest-first: standard credit-risk validation table."""
    import numpy as np

    y = np.asarray(y_true, dtype=int)
    s = np.asarray(y_score, dtype=float)
    total = len(y)
    total_pos = int(y.sum())
    if total == 0:
        return []
    order = np.argsort(-s)
    y_sorted = y[order]
    s_sorted = s[order]
    base_rate = _safe_divide(total_pos, total)
    rows: list[dict[str, Any]] = []
    cumulative_pos = 0
    for i, segment in enumerate(np.array_split(np.arange(total), n_bins), start=1):
        if len(segment) == 0:
            continue
        seg_y = y_sorted[segment]
        seg_pos = int(seg_y.sum())
        cumulative_pos += seg_pos
        actual_rate = _safe_divide(seg_pos, len(segment))
        rows.append(
            {
                "decile": i,
                "rows": int(len(segment)),
                "mean_predicted": float(s_sorted[segment].mean()),
                "actual_positives": seg_pos,
                "actual_rate": actual_rate,
                "lift": _safe_divide(actual_rate, base_rate),
                "cumulative_positives": cumulative_pos,
                "cumulative_recall": _safe_divide(cumulative_pos, total_pos),
            }
        )
    return rows


def _calibration_table(
    y_true: Any,
    y_score: Any,
    *,
    n_bins: int = 10,
) -> tuple[list[dict[str, Any]], float | None]:
    """Reliability bins + expected calibration error (weighted mean |predicted - observed|)."""
    import numpy as np

    y = np.asarray(y_true, dtype=int)
    s = np.asarray(y_score, dtype=float)
    total = len(y)
    if total == 0:
        return [], None
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows: list[dict[str, Any]] = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = float(edges[i]), float(edges[i + 1])
        mask = (s >= lo) & (s <= hi) if i == n_bins - 1 else (s >= lo) & (s < hi)
        count = int(mask.sum())
        if count == 0:
            rows.append({"bin_lower": lo, "bin_upper": hi, "rows": 0,
                         "mean_predicted": None, "actual_rate": None, "gap": None})
            continue
        mean_pred = float(s[mask].mean())
        actual = float(y[mask].mean())
        gap = abs(mean_pred - actual)
        ece += (count / total) * gap
        rows.append({"bin_lower": lo, "bin_upper": hi, "rows": count,
                     "mean_predicted": mean_pred, "actual_rate": actual, "gap": gap})
    return rows, float(ece)


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

    decile_path = run_artifacts_dir / "decile_table.csv"
    _write_csv(decile_path, metadata["metrics"].get("decile_table", []))
    artifacts["decile_table_csv"] = str(decile_path)

    calibration_path = run_artifacts_dir / "calibration_table.csv"
    _write_csv(calibration_path, metadata["metrics"].get("calibration_table", []))
    artifacts["calibration_table_csv"] = str(calibration_path)

    if metadata["metrics"].get("conformal_validity"):
        conformal_path = run_artifacts_dir / "conformal_validity.csv"
        _write_csv(conformal_path, metadata["metrics"]["conformal_validity"])
        artifacts["conformal_validity_csv"] = str(conformal_path)

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


def _write_shap_artifacts(
    *,
    run_artifacts_dir: Path,
    model: Any,
    X_test: Any,
    scores: Any,
    sample_size: int = 10000,
) -> dict[str, str]:
    """Global SHAP explanations (bar, beeswarm, signed-importance CSV) for the
    trained model. Fail-soft: any error is captured to shap_error.txt so it can
    never abort a finished training run. Explains the exact model just trained,
    which is what the standalone Phase D notebook could not guarantee.
    """
    import numpy as np

    artifacts: dict[str, str] = {}
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)
    try:
        import shap
        import pandas as pd
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Sample = half highest-risk + half random, covering the operational
        # decision zone as well as the typical company.
        score_arr = np.asarray(scores, dtype=float)
        n = min(int(sample_size), len(X_test))
        order = np.argsort(-score_arr)
        half = n // 2
        high_idx = order[:half]
        remaining = order[half:]
        rng = np.random.default_rng(42)
        if len(remaining) and n - half > 0:
            random_idx = rng.choice(remaining, size=min(n - half, len(remaining)), replace=False)
        else:
            random_idx = np.array([], dtype=int)
        selected = np.concatenate([high_idx, random_idx]).astype(int)
        X_sample_raw = X_test.iloc[selected]

        # SHAP can't see through the sklearn Pipeline wrapper, so push the sample
        # through the transformer step and explain the bare classifier.
        transformer = model.named_steps["prepare_categoricals"]
        classifier = model.named_steps["classifier"]
        X_sample = transformer.transform(X_sample_raw).copy()

        # TreeExplainer needs numeric input. The model was trained on pandas
        # Categorical columns (HGB/LightGBM/XGBoost) or strings (CatBoost), so
        # map every non-numeric column to its integer category codes -- the same
        # encoding the trees split on. Without this, shap raises
        # "could not convert string to float".
        for column in X_sample.columns:
            if not pd.api.types.is_numeric_dtype(X_sample[column]):
                X_sample[column] = X_sample[column].astype("category").cat.codes

        explainer = shap.TreeExplainer(classifier)
        try:
            shap_values = explainer(X_sample, check_additivity=False)
        except TypeError:
            shap_values = explainer(X_sample)

        plt.figure()
        shap.plots.bar(shap_values, max_display=20, show=False)
        plt.title("SHAP mean |value| by feature (top 20)")
        bar_path = run_artifacts_dir / "shap_summary_bar.png"
        plt.savefig(bar_path, dpi=160, bbox_inches="tight")
        plt.close()
        artifacts["shap_summary_bar_png"] = str(bar_path)

        plt.figure()
        shap.plots.beeswarm(shap_values, max_display=20, show=False)
        beeswarm_path = run_artifacts_dir / "shap_summary_beeswarm.png"
        plt.savefig(beeswarm_path, dpi=160, bbox_inches="tight")
        plt.close()
        artifacts["shap_summary_beeswarm_png"] = str(beeswarm_path)

        values = np.asarray(shap_values.values)
        if values.ndim == 3:
            values = values[:, :, -1]
        feature_names = list(getattr(X_sample, "columns", [])) or [f"f{i}" for i in range(values.shape[1])]
        mean_shap = values.mean(axis=0)
        mean_abs = np.abs(values).mean(axis=0)
        rows = [
            {
                "feature": str(feature_names[i]),
                "mean_shap": float(mean_shap[i]),
                "mean_abs_shap": float(mean_abs[i]),
                "dominant_push": "toward_risk" if mean_shap[i] >= 0 else "away_from_risk",
            }
            for i in range(len(feature_names))
        ]
        rows.sort(key=lambda row: row["mean_abs_shap"], reverse=True)
        signs_path = run_artifacts_dir / "shap_top_feature_signs.csv"
        _write_csv(signs_path, rows)
        artifacts["shap_top_feature_signs_csv"] = str(signs_path)
    except Exception as exc:
        error_path = run_artifacts_dir / "shap_error.txt"
        error_path.write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        artifacts["shap_error"] = str(error_path)
    return artifacts


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
        "gini": metrics.get("gini"),
        "ks_statistic": metrics.get("ks_statistic"),
        "brier_score": metrics.get("brier_score"),
        "log_loss": metrics.get("log_loss"),
        "expected_calibration_error": metrics.get("expected_calibration_error"),
        "mcc": metrics.get("mcc"),
        "balanced_accuracy": metrics.get("balanced_accuracy"),
        "specificity_at_0_5": metrics.get("specificity_at_0_5"),
        "precision_at_recall_50": metrics.get("precision_at_recall_50"),
        "precision_at_recall_70": metrics.get("precision_at_recall_70"),
        "precision_at_recall_90": metrics.get("precision_at_recall_90"),
        "roc_auc_ci95_low": metrics.get("roc_auc_ci95_low"),
        "roc_auc_ci95_high": metrics.get("roc_auc_ci95_high"),
        "average_precision_ci95_low": metrics.get("average_precision_ci95_low"),
        "average_precision_ci95_high": metrics.get("average_precision_ci95_high"),
    }


def _run_artifacts_folder_name(
    *,
    model_version: str,
    target: str,
    model_family: str,
    split_strategy: str,
    max_rows: int | None,
    rows: int,
    run_tag: str | None = None,
) -> str:
    timestamp = model_version.replace("continuity-risk-", "")
    target_slug = _slugify(_strip_suffix(target, "_label"))
    split_slug = _short_split_slug(split_strategy)
    cap_slug = f"cap-{_compact_count(max_rows)}" if max_rows else "full-data"
    rows_slug = f"rows-{_compact_count(rows)}"
    tag_slug = f"feat-{_slugify(run_tag)}" if run_tag else None
    return "_".join(
        part
        for part in (
            timestamp,
            target_slug,
            _slugify(model_family),
            split_slug,
            cap_slug,
            rows_slug,
            tag_slug,
        )
        if part
    )


def _detect_feature_schema(data_lake_dir: Path) -> str | None:
    """Look up the feature parquet manifest and return its schema version, if any.

    Lets training runs stamp themselves with the feature schema they trained
    against, so 33-column legacy runs and 52-column trajectory+sector runs sit
    in distinguishable folders.
    """
    manifest_path = data_lake_dir / "features" / "company_year_features" / "_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("feature_schema_version")
    except Exception:
        return None


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
        f"| Output schema | `{metadata.get('output_schema_version')}` |",
        f"| Calibrated | {metadata.get('calibrated')} (holdout fraction {metadata.get('calibration_fraction')}) |",
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
        f"| Gini (2*AUC-1) | {_fmt_float(metrics.get('gini'))} |",
        f"| KS statistic | {_fmt_float(metrics.get('ks_statistic'))} |",
        f"| Brier score | {_fmt_float(metrics.get('brier_score'))} |",
        f"| Log loss | {_fmt_float(metrics.get('log_loss'))} |",
        f"| Expected calibration error | {_fmt_float(metrics.get('expected_calibration_error'))} |",
        f"| Brier (calibrated) | {_fmt_float(metrics.get('calibrated_brier_score'))} |",
        f"| ECE (calibrated) | {_fmt_float(metrics.get('calibrated_expected_calibration_error'))} |",
        f"| MCC | {_fmt_float(metrics.get('mcc'))} |",
        f"| Balanced accuracy | {_fmt_float(metrics.get('balanced_accuracy'))} |",
        f"| Specificity at 0.5 | {_fmt_float(metrics.get('specificity_at_0_5'))} |",
        f"| Precision @ recall 50/70/90% | {_fmt_float(metrics.get('precision_at_recall_50'))} / {_fmt_float(metrics.get('precision_at_recall_70'))} / {_fmt_float(metrics.get('precision_at_recall_90'))} |",
        f"| ROC AUC 95% CI | {_fmt_float(metrics.get('roc_auc_ci95_low'))} - {_fmt_float(metrics.get('roc_auc_ci95_high'))} |",
        f"| Avg precision 95% CI | {_fmt_float(metrics.get('average_precision_ci95_low'))} - {_fmt_float(metrics.get('average_precision_ci95_high'))} |",
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

    conformal_rows = metrics.get("conformal_validity", [])
    if conformal_rows:
        lines.extend(
            [
                "",
                "## Conformal Confidence",
                "",
                f"Mean confidence: {_fmt_float(metrics.get('conformal_mean_confidence'))}  |  "
                f"mean credibility: {_fmt_float(metrics.get('conformal_mean_credibility'))}",
                "",
                f"Calibration source: `{metrics.get('conformal_calibration_source', 'n/a')}` (exchangeable with the scored population, so the coverage guarantee holds).",
                "",
                "Validity: at each target confidence the empirical error should stay at or below the significance level (1 - confidence).",
                "",
                "| Target confidence | Significance | Empirical error | Avg set size | Singleton rate | Empty rate |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in conformal_rows:
            lines.append(
                "| "
                f"{_fmt_pct(row.get('target_confidence'))} | "
                f"{_fmt_float(row.get('significance'), digits=2)} | "
                f"{_fmt_float(row.get('empirical_error'))} | "
                f"{_fmt_float(row.get('avg_set_size'), digits=3)} | "
                f"{_fmt_pct(row.get('singleton_rate'))} | "
                f"{_fmt_pct(row.get('empty_rate'))} |"
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
        "calibration_curve_png",
        "cumulative_gains_curve_png",
        "headline_metrics_png",
        "class_counts_by_year_png",
        "top_feature_importances_png",
        "shap_summary_bar_png",
        "shap_summary_beeswarm_png",
        "conformal_confidence_hist_png",
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


# Descriptions for the per-run OUTPUTS.md manifest. Keyed by filename so the
# manifest reflects whatever files actually landed in the run folder.
_RUN_OUTPUT_DESCRIPTIONS = {
    "model.joblib": "Archived model bundle (pipeline + features + calibrator + conformal + metadata) for this run.",
    "isotonic_calibrator.joblib": "Fitted isotonic calibrator for this run's model (apply to raw scores for honest probabilities).",
    "conformal_calibrator.joblib": "Fitted Mondrian conformal predictor: turns a raw score into a per-company confidence + credibility.",
    "conformal_validity.csv": "Conformal validity table: empirical error vs target confidence and prediction-set sizes on the test set.",
    "conformal_confidence_hist.png": "Distribution of per-company conformal confidence on the test set.",
    "shap_summary_bar.png": "SHAP global importance: mean |SHAP value| per feature.",
    "shap_summary_beeswarm.png": "SHAP signed per-company contributions per feature (direction + spread).",
    "shap_top_feature_signs.csv": "Per feature: mean SHAP, mean |SHAP|, and dominant push (toward/away from risk).",
    "shap_error.txt": "SHAP stage failed for this run (see contents); training itself still succeeded.",
    "metadata.json": "Full run metadata: config, dataset stats, and every metric (incl. tables).",
    "run_summary.md": "Human-readable summary of the run and its headline metrics.",
    "metrics_summary.csv": "One-row flat table of all scalar metrics (spreadsheet-friendly).",
    "threshold_analysis.csv": "Precision/recall/F1/FPR/flagged-rate at thresholds 0.001-0.5.",
    "top_k_analysis.csv": "Precision/recall/lift at the top 0.1/0.5/1/5/10% by risk score.",
    "decile_table.csv": "Risk deciles (highest-first): mean predicted vs actual rate, lift, cumulative recall.",
    "calibration_table.csv": "10-bin reliability table: mean predicted vs observed + gap (feeds ECE).",
    "class_counts_by_year.json": "Positive/negative row counts per prediction year.",
    "feature_importances.csv": "Permutation importance (ROC-AUC drop) per feature.",
    "precision_recall_curve.png": "PR curve with average precision annotated.",
    "roc_curve.png": "ROC curve with AUC annotated.",
    "confusion_matrix_at_0_5.png": "Confusion matrix at threshold 0.5.",
    "score_distribution_by_class.png": "Predicted-score histograms split by true class.",
    "threshold_tradeoff.png": "Precision/recall/flagged-rate vs decision threshold.",
    "calibration_curve.png": "Reliability curve (predicted vs observed) with ECE.",
    "cumulative_gains_curve.png": "Cumulative positives captured vs population fraction (ranked by risk).",
    "headline_metrics.png": "Single bar chart of AUC, AP, Gini, KS, F1, precision and recall together.",
    "class_counts_by_year.png": "Stacked class counts per prediction year.",
    "top_feature_importances.png": "Bar chart of the top permutation importances.",
}


def _write_outputs_manifest(run_artifacts_dir: Path, metadata: dict[str, Any]) -> None:
    """Self-documenting list of every file this run produced, written as OUTPUTS.md."""
    lines = [
        f"# Run Outputs: {metadata.get('run_name') or metadata.get('model_version')}",
        "",
        f"Generated {metadata.get('trained_at')}. Every file in this folder:",
        "",
        "| File | Description |",
        "|---|---|",
    ]
    for file_path in sorted(run_artifacts_dir.glob("*")):
        if not file_path.is_file() or file_path.name == "OUTPUTS.md":
            continue
        description = _RUN_OUTPUT_DESCRIPTIONS.get(file_path.name)
        if description is None:
            if file_path.name.endswith(".png"):
                description = "Generated plot."
            elif file_path.name.endswith("error.txt"):
                description = "Error captured while generating an artifact (see contents)."
            else:
                description = "(see metadata.json)"
        lines.append(f"| `{file_path.name}` | {description} |")
    lines.append("")
    (run_artifacts_dir / "OUTPUTS.md").write_text("\n".join(lines), encoding="utf-8")


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

    calibration_rows = [
        row for row in metadata["metrics"].get("calibration_table", [])
        if row.get("mean_predicted") is not None
    ]
    if calibration_rows:
        calibration_path = run_artifacts_dir / "calibration_curve.png"
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1, label="Perfect calibration")
        ax.plot(
            [row["mean_predicted"] for row in calibration_rows],
            [row["actual_rate"] for row in calibration_rows],
            marker="o", linewidth=2, label="Raw",
        )
        calibrated_rows = [
            row for row in metadata["metrics"].get("calibrated_calibration_table", [])
            if row.get("mean_predicted") is not None
        ]
        if calibrated_rows:
            ax.plot(
                [row["mean_predicted"] for row in calibrated_rows],
                [row["actual_rate"] for row in calibrated_rows],
                marker="s", linewidth=2, label="Calibrated",
            )
        ax.set_title("Calibration (Reliability) Curve")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Observed frequency")
        ece = metadata["metrics"].get("expected_calibration_error")
        if ece is not None:
            ax.text(0.02, 0.95, f"ECE = {ece:.4f}", transform=ax.transAxes, va="top")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(calibration_path, dpi=160)
        plt.close(fig)
        plot_paths["calibration_curve_png"] = str(calibration_path)

    order = np.argsort(-y_score_arr)
    y_ordered = y_true_arr[order]
    total_positives = int(y_ordered.sum())
    if total_positives > 0:
        gains_path = run_artifacts_dir / "cumulative_gains_curve.png"
        population_fraction = np.arange(1, len(y_ordered) + 1) / len(y_ordered)
        positives_fraction = np.cumsum(y_ordered) / total_positives
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(population_fraction, positives_fraction, linewidth=2, label="Model")
        ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1, label="Random")
        ax.set_title("Cumulative Gains")
        ax.set_xlabel("Fraction of population (ranked by risk score)")
        ax.set_ylabel("Fraction of positives captured")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(gains_path, dpi=160)
        plt.close(fig)
        plot_paths["cumulative_gains_curve_png"] = str(gains_path)

    headline = [
        (label, metadata["metrics"].get(key))
        for label, key in (
            ("ROC AUC", "roc_auc"),
            ("Avg precision", "average_precision"),
            ("Gini", "gini"),
            ("KS", "ks_statistic"),
            ("F1 @0.5", "f1_at_0_5"),
            ("Precision @0.5", "precision_at_0_5"),
            ("Recall @0.5", "recall_at_0_5"),
        )
    ]
    headline = [(label, float(value)) for label, value in headline if value is not None]
    if headline:
        headline_path = run_artifacts_dir / "headline_metrics.png"
        labels = [label for label, _ in headline]
        values = [value for _, value in headline]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        bars = ax.barh(range(len(labels)), values, color="#0f766e", alpha=0.85)
        ax.set_yticks(range(len(labels)), labels=labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.set_title("Headline Metrics")
        ax.grid(True, axis="x", alpha=0.3)
        for bar, value in zip(bars, values):
            ax.text(min(value + 0.01, 0.97), bar.get_y() + bar.get_height() / 2, f"{value:.3f}", va="center")
        fig.tight_layout()
        fig.savefig(headline_path, dpi=160)
        plt.close(fig)
        plot_paths["headline_metrics_png"] = str(headline_path)

    conf_hist = metadata["metrics"].get("conformal_confidence_hist", [])
    if conf_hist:
        conf_path = run_artifacts_dir / "conformal_confidence_hist.png"
        centers = [(row["bin_lower"] + row["bin_upper"]) / 2 for row in conf_hist]
        counts = [row["count"] for row in conf_hist]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.bar(centers, counts, width=0.09, color="#0f766e", alpha=0.85)
        ax.set_title("Conformal Confidence Distribution (test set)")
        ax.set_xlabel("Per-company confidence")
        ax.set_ylabel("Companies")
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(conf_path, dpi=160)
        plt.close(fig)
        plot_paths["conformal_confidence_hist_png"] = str(conf_path)

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
        "gini": metrics.get("gini"),
        "ks_statistic": metrics.get("ks_statistic"),
        "brier_score": metrics.get("brier_score"),
        "log_loss": metrics.get("log_loss"),
        "expected_calibration_error": metrics.get("expected_calibration_error"),
        "roc_auc_ci95_low": metrics.get("roc_auc_ci95_low"),
        "roc_auc_ci95_high": metrics.get("roc_auc_ci95_high"),
        "average_precision_ci95_low": metrics.get("average_precision_ci95_low"),
        "average_precision_ci95_high": metrics.get("average_precision_ci95_high"),
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
        "gini": row.get("gini"),
        "ks_statistic": row.get("ks_statistic"),
        "brier_score": row.get("brier_score"),
        "expected_calibration_error": row.get("expected_calibration_error"),
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
    parser.add_argument(
        "--calibrate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fit an isotonic calibrator on a held-out slice of train (--no-calibrate to skip). "
             "When on, the model trains on (1 - calibration_fraction) of the training rows.",
    )
    parser.add_argument(
        "--calibration-fraction",
        type=float,
        default=0.15,
        help="Fraction of the training rows held out (not trained on) to fit the calibrator.",
    )
    parser.add_argument(
        "--shap",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compute SHAP global explanations on the trained model (--no-shap to skip). Fail-soft.",
    )
    parser.add_argument(
        "--shap-sample",
        type=int,
        default=10000,
        help="Rows scored for SHAP (half highest-risk + half random from the test set).",
    )
    parser.add_argument(
        "--run-tag",
        default=None,
        help=(
            "Optional short tag appended to the run folder name so different feature"
            " sets are visually distinguishable (e.g. 'v3-traj'). If omitted, the trainer"
            " auto-detects the feature_schema_version from the features parquet manifest."
        ),
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
