"""Gradient-boosting models. Early stopping is done by the trainer."""

from __future__ import annotations

from typing import Any

from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier


def make_xgboost(params: dict[str, Any], random_state: int,
                 scale_pos_weight: float | None):
    kwargs: dict[str, Any] = dict(
        n_estimators=int(params.get("n_estimators", 1500)),
        max_depth=int(params.get("max_depth", 6)),
        learning_rate=float(params.get("learning_rate", 0.05)),
        subsample=float(params.get("subsample", 0.8)),
        colsample_bytree=float(params.get("colsample_bytree", 0.8)),
        eval_metric=params.get("eval_metric", "aucpr"),
        early_stopping_rounds=int(params.get("early_stopping_rounds", 50)),
        tree_method="hist",
        random_state=random_state,
        n_jobs=-1,
    )
    if scale_pos_weight is not None:
        kwargs["scale_pos_weight"] = float(scale_pos_weight)
    return XGBClassifier(**kwargs)


def make_lightgbm(params: dict[str, Any], random_state: int,
                  scale_pos_weight: float | None):
    kwargs: dict[str, Any] = dict(
        n_estimators=int(params.get("n_estimators", 1500)),
        max_depth=int(params.get("max_depth", 6)),
        num_leaves=int(params.get("num_leaves", 63)),
        learning_rate=float(params.get("learning_rate", 0.05)),
        subsample=float(params.get("subsample", 0.8)),
        colsample_bytree=float(params.get("colsample_bytree", 0.8)),
        random_state=random_state,
        n_jobs=-1,
        verbose=-1,
    )
    if scale_pos_weight is not None:
        kwargs["scale_pos_weight"] = float(scale_pos_weight)
    return LGBMClassifier(**kwargs)


def make_catboost(params: dict[str, Any], random_state: int,
                  scale_pos_weight: float | None):
    return CatBoostClassifier(
        iterations=int(params.get("iterations", 1500)),
        depth=int(params.get("depth", 6)),
        learning_rate=float(params.get("learning_rate", 0.05)),
        early_stopping_rounds=int(params.get("early_stopping_rounds", 50)),
        auto_class_weights="Balanced",
        random_seed=random_state,
        verbose=0,
        thread_count=-1,
        allow_writing_files=False,
    )
