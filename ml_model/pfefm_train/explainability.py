"""SHAP + permutation-importance helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)


@dataclass
class ExplainabilityOutputs:
    feature_importance: pd.DataFrame
    shap_values: np.ndarray | None
    shap_feature_names: list[str] | None


def _post_feature_names(pipeline: Pipeline) -> list[str]:
    preprocess = pipeline.named_steps["preprocess"]
    try:
        return list(preprocess.get_feature_names_out())
    except Exception:
        return []


def _transform_for_shap(pipeline: Pipeline, X_raw: pd.DataFrame) -> np.ndarray:
    out = X_raw
    for _, step in pipeline.steps[:-1]:
        out = step.transform(out)
    return np.asarray(out)


def feature_importance(pipeline: Pipeline) -> pd.DataFrame:
    """Return a DataFrame of feature importances if the model exposes them."""

    model = pipeline.named_steps["model"]
    names = _post_feature_names(pipeline)

    if hasattr(model, "feature_importances_"):
        imp = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "get_feature_importance"):
        imp = np.asarray(model.get_feature_importance(), dtype=float)
    elif hasattr(model, "coef_"):
        imp = np.abs(np.asarray(model.coef_).ravel())
    else:
        return pd.DataFrame(columns=["feature", "importance"])

    if len(names) != len(imp):
        names = [f"f{i}" for i in range(len(imp))]

    df = pd.DataFrame({"feature": names, "importance": imp})
    s = df["importance"].sum()
    df["importance_norm"] = df["importance"] / s if s else 0.0
    return df.sort_values("importance", ascending=False).reset_index(drop=True)


def shap_summary(
    pipeline: Pipeline,
    X_raw: pd.DataFrame,
    *,
    max_samples: int = 2000,
    random_state: int = 42,
) -> ExplainabilityOutputs:
    """Compute SHAP values for the final estimator using the post-preprocessing matrix."""

    imp_df = feature_importance(pipeline)

    try:
        import shap
    except ImportError:
        logger.warning("SHAP not installed; skipping SHAP summary.")
        return ExplainabilityOutputs(imp_df, None, None)

    model = pipeline.named_steps["model"]
    if not hasattr(model, "predict_proba"):
        return ExplainabilityOutputs(imp_df, None, None)

    if len(X_raw) > max_samples:
        X_raw = X_raw.sample(max_samples, random_state=random_state)

    X_mat = _transform_for_shap(pipeline, X_raw)
    names = _post_feature_names(pipeline)

    try:
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(X_mat)
    except Exception:
        try:
            explainer = shap.Explainer(model, X_mat)
            sv = explainer(X_mat).values
        except Exception:
            logger.exception("SHAP failed; returning importance only.")
            return ExplainabilityOutputs(imp_df, None, None)

    if isinstance(sv, list):                      # old API: [neg_class, pos_class]
        sv = np.asarray(sv[-1])
    sv = np.asarray(sv)
    if sv.ndim == 3:                              # new API multi-output
        sv = sv[..., -1]
    return ExplainabilityOutputs(imp_df, sv, names)


def permutation(
    pipeline: Pipeline,
    X_raw: pd.DataFrame,
    y: np.ndarray,
    *,
    n_repeats: int = 5,
    random_state: int = 42,
    max_samples: int = 5000,
) -> pd.DataFrame:
    """Permutation-importance (slower; useful as a sanity check against tree importance)."""

    if len(X_raw) > max_samples:
        idx = np.random.default_rng(random_state).choice(len(X_raw), max_samples, replace=False)
        X_raw = X_raw.iloc[idx]
        y = np.asarray(y)[idx]

    result = permutation_importance(
        pipeline, X_raw, y,
        scoring="average_precision",
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=-1,
    )
    return (
        pd.DataFrame(
            {
                "feature": list(X_raw.columns),
                "importance_mean": result.importances_mean,
                "importance_std": result.importances_std,
            }
        )
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )
