"""Train every candidate model with temporal CV and early stopping."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from . import evaluation
from .config import PipelineConfig
from .feature_engineering import build_features
from .feature_registry import FeatureRegistry
from .models import REGISTRY as MODEL_REGISTRY
from .models import SUPPORTS_EARLY_STOPPING, build as build_model
from .preprocessing import make_preprocessor
from .temporal_split import Fold

logger = logging.getLogger(__name__)


@dataclass
class FoldResult:
    fold: str
    metrics: dict[str, float]


@dataclass
class ModelResult:
    name: str
    fold_results: list[FoldResult] = field(default_factory=list)
    cv_mean: dict[str, float] = field(default_factory=dict)
    cv_std: dict[str, float] = field(default_factory=dict)
    fit_time_s: float = 0.0
    final_pipeline: Pipeline | None = None
    best_iteration: int | None = None


# ---- pipeline builder ---------------------------------------------------


def _fe_transformer(reference_year: int) -> FunctionTransformer:
    """Wrap ``build_features`` in a sklearn-compatible transformer."""

    def _apply(df):
        return build_features(df, reference_year=reference_year)

    return FunctionTransformer(_apply, validate=False, feature_names_out="one-to-one")


def make_pipeline(
    estimator,
    *,
    reference_year: int,
    numeric_features: list[str],
    categorical_features: list[str],
    numeric_strategy: str = "passthrough",
) -> Pipeline:
    """Assemble the end-to-end pipeline: FE -> ColumnTransformer -> estimator."""

    preproc = make_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        numeric_strategy=numeric_strategy,
    )
    return Pipeline(
        steps=[
            ("features", _fe_transformer(reference_year)),
            ("preprocess", preproc),
            ("model", estimator),
        ]
    )


# ---- early-stopping fit -------------------------------------------------


def _transform_for_early_stop(
    pipeline: Pipeline, X_val_raw: pd.DataFrame
) -> np.ndarray:
    """Apply the pre-estimator part of ``pipeline`` to a raw dataframe."""

    out = X_val_raw
    for name, step in pipeline.steps[:-1]:
        out = step.transform(out)
    return out


def _fit_with_early_stopping(
    name: str,
    pipeline: Pipeline,
    X_train_raw: pd.DataFrame,
    y_train: np.ndarray,
    X_val_raw: pd.DataFrame | None,
    y_val: np.ndarray | None,
) -> int | None:
    """Fit the pipeline; pass eval_set to the estimator if applicable.

    Returns the ``best_iteration`` (or ``None`` if early-stopping not used).
    """

    estimator_name = name
    # Fit feature + preprocess first so we can compute the validation matrix.
    pipeline.named_steps["features"].fit(X_train_raw, y_train)
    X_train_feat = pipeline.named_steps["features"].transform(X_train_raw)
    pipeline.named_steps["preprocess"].fit(X_train_feat, y_train)
    X_train_matrix = pipeline.named_steps["preprocess"].transform(X_train_feat)

    model = pipeline.named_steps["model"]
    best_iteration: int | None = None

    if estimator_name in SUPPORTS_EARLY_STOPPING and X_val_raw is not None and y_val is not None:
        X_val_matrix = _transform_for_early_stop(pipeline, X_val_raw)
        try:
            if estimator_name == "xgboost":
                model.fit(
                    X_train_matrix, y_train,
                    eval_set=[(X_val_matrix, y_val)],
                    verbose=False,
                )
                best_iteration = int(getattr(model, "best_iteration", -1))
            elif estimator_name == "lightgbm":
                import lightgbm as lgb

                es_rounds = int(getattr(model, "_es_rounds", 50))  # safeguard
                model.fit(
                    X_train_matrix, y_train,
                    eval_set=[(X_val_matrix, y_val)],
                    eval_metric="auc",
                    callbacks=[lgb.early_stopping(50, verbose=False)],
                )
                best_iteration = int(getattr(model, "best_iteration_", -1) or -1)
            elif estimator_name == "catboost":
                model.fit(
                    X_train_matrix, y_train,
                    eval_set=(X_val_matrix, y_val),
                    verbose=False,
                )
                best_iteration = int(getattr(model, "tree_count_", -1))
        except Exception:
            logger.exception(
                "Early-stopping fit failed for %s; falling back to plain fit.",
                estimator_name,
            )
            model.fit(X_train_matrix, y_train)
    else:
        model.fit(X_train_matrix, y_train)

    return best_iteration


# ---- cross-validation ---------------------------------------------------


def _metric_row(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    m = evaluation.core_metrics(y_true, y_prob, threshold=0.5)
    return {
        "roc_auc": m.roc_auc,
        "pr_auc": m.pr_auc,
        "brier": m.brier,
        "recall_at_0.5": m.recall_at_threshold,
        "f1_at_0.5": m.f1_at_threshold,
    }


def cross_validate_temporal(
    *,
    name: str,
    make_estimator: Callable[[], Any],
    X_raw: pd.DataFrame,
    y: np.ndarray,
    folds: list[Fold],
    reference_year: int,
    numeric_features: list[str],
    categorical_features: list[str],
    numeric_strategy: str,
) -> ModelResult:
    """Run temporal CV for one model, returning per-fold metrics + aggregates."""

    result = ModelResult(name=name)
    for fold in folds:
        X_tr = X_raw.iloc[fold.train_idx]
        X_va = X_raw.iloc[fold.val_idx]
        y_tr = y[fold.train_idx]
        y_va = y[fold.val_idx]

        pipeline = make_pipeline(
            make_estimator(),
            reference_year=reference_year,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            numeric_strategy=numeric_strategy,
        )

        _fit_with_early_stopping(
            name, pipeline, X_tr, y_tr, X_va, y_va,
        )

        y_prob_va = pipeline.predict_proba(X_va)[:, 1]
        metrics = _metric_row(y_va, y_prob_va)
        result.fold_results.append(FoldResult(fold=fold.name, metrics=metrics))

    if result.fold_results:
        keys = result.fold_results[0].metrics.keys()
        result.cv_mean = {
            k: float(np.mean([fr.metrics[k] for fr in result.fold_results]))
            for k in keys
        }
        result.cv_std = {
            k: float(np.std([fr.metrics[k] for fr in result.fold_results]))
            for k in keys
        }
    return result


# ---- training orchestration --------------------------------------------


@dataclass
class TrainingOutputs:
    results: dict[str, ModelResult]
    numeric_features: list[str]
    categorical_features: list[str]


def _scale_pos_weight_for(name: str, y_train: np.ndarray) -> float | None:
    """XGBoost/LightGBM scale_pos_weight = n_negatives / n_positives."""

    if name not in {"xgboost", "lightgbm"}:
        return None
    n_pos = int((y_train == 1).sum())
    n_neg = int((y_train == 0).sum())
    if n_pos == 0:
        return None
    return n_neg / n_pos


def train_all(
    *,
    config: PipelineConfig,
    registry: FeatureRegistry,
    X_train_raw: pd.DataFrame,
    y_train: np.ndarray,
    X_val_raw: pd.DataFrame,
    y_val: np.ndarray,
    folds: list[Fold],
) -> TrainingOutputs:
    """Cross-validate each candidate, then re-fit on train+val for deployment.

    For boosters the final fit uses ``X_val_raw`` as early-stopping set so the
    number of trees reflects what was learned with validation monitoring, but
    the model itself only trains on ``X_train_raw``.
    """

    # Resolve feature lists against the enriched dataset (post-FE columns).
    probe = build_features(
        X_train_raw.head(10),
        reference_year=config.reference_date.year,
    )
    available = set(probe.columns)
    numeric_features = registry.supervised_numeric(available)
    categorical_features = registry.supervised_categorical(available)

    missing_num = [
        f.name for f in registry.supervised_features()
        if f.type == "numeric" and f.name not in available
    ]
    missing_cat = [
        f.name for f in registry.supervised_features()
        if f.type == "categorical" and f.name not in available
    ]
    if missing_num or missing_cat:
        logger.warning(
            "Registry features not available after FE: numeric=%s | categorical=%s",
            missing_num,
            missing_cat,
        )

    logger.info(
        "Training with %d numeric + %d categorical features.",
        len(numeric_features),
        len(categorical_features),
    )

    results: dict[str, ModelResult] = {}
    for name in config.candidates:
        if name not in MODEL_REGISTRY:
            logger.warning("Skipping unknown candidate %r", name)
            continue

        params = config.hyperparameters.get(name, {})
        scale_pw = _scale_pos_weight_for(name, y_train)
        numeric_strategy = (
            "median_impute" if name in {"logistic_regression", "decision_tree"}
            else "passthrough"
        )

        def _make(n=name, p=params, spw=scale_pw):
            return build_model(
                n,
                p,
                random_state=config.random_state,
                scale_pos_weight=spw,
            )

        logger.info("=" * 60)
        logger.info("Model: %s", name)

        t0 = time.time()
        cv_result = cross_validate_temporal(
            name=name,
            make_estimator=_make,
            X_raw=X_train_raw,
            y=y_train,
            folds=folds,
            reference_year=config.reference_date.year,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            numeric_strategy=numeric_strategy,
        )

        logger.info(
            "  CV (%d folds): %s",
            len(cv_result.fold_results),
            {k: round(v, 4) for k, v in cv_result.cv_mean.items()},
        )

        # Final pipeline fit with the provided validation set for early stopping.
        final_pipeline = make_pipeline(
            _make(),
            reference_year=config.reference_date.year,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            numeric_strategy=numeric_strategy,
        )
        best_iter = _fit_with_early_stopping(
            name, final_pipeline, X_train_raw, y_train, X_val_raw, y_val,
        )
        cv_result.final_pipeline = final_pipeline
        cv_result.best_iteration = best_iter
        cv_result.fit_time_s = round(time.time() - t0, 2)
        logger.info("  best_iteration=%s | elapsed=%.1fs", best_iter, cv_result.fit_time_s)
        results[name] = cv_result

    return TrainingOutputs(
        results=results,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )


def cv_summary_frame(outputs: TrainingOutputs) -> pd.DataFrame:
    rows = []
    for name, res in outputs.results.items():
        rows.append(
            {
                "model": name,
                "cv_roc_auc_mean": res.cv_mean.get("roc_auc"),
                "cv_pr_auc_mean": res.cv_mean.get("pr_auc"),
                "cv_recall_mean": res.cv_mean.get("recall_at_0.5"),
                "cv_f1_mean": res.cv_mean.get("f1_at_0.5"),
                "cv_brier_mean": res.cv_mean.get("brier"),
                "best_iteration": res.best_iteration,
                "fit_time_s": res.fit_time_s,
            }
        )
    return pd.DataFrame(rows).set_index("model")


def pick_winner(outputs: TrainingOutputs, metric: str) -> str:
    """Choose the winning model by CV metric (tie-break: fit time ascending)."""

    key = {
        "roc_auc": "roc_auc",
        "pr_auc": "pr_auc",
        "recall": "recall_at_0.5",
        "f1": "f1_at_0.5",
        "recall_at_min_precision": "pr_auc",  # proxy on CV; threshold tuning is on val
    }[metric]
    scored = [
        (name, res.cv_mean.get(key, float("-inf")), res.fit_time_s)
        for name, res in outputs.results.items()
    ]
    scored.sort(key=lambda t: (-t[1], t[2]))
    return scored[0][0]
