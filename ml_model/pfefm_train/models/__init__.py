"""Factory functions for every candidate classifier.

Each function returns an UN-fitted estimator. Training logic (including
early-stopping for boosters) is centralised in
:mod:`pfefm_train.training`.
"""

from __future__ import annotations

from typing import Any, Callable

from .baselines import make_decision_tree, make_dummy, make_logistic_regression
from .boosting import make_catboost, make_lightgbm, make_xgboost
from .random_forest import make_random_forest

ModelFactory = Callable[[dict[str, Any], int, float | None], Any]

REGISTRY: dict[str, ModelFactory] = {
    "dummy":               make_dummy,
    "logistic_regression": make_logistic_regression,
    "decision_tree":       make_decision_tree,
    "random_forest":       make_random_forest,
    "xgboost":             make_xgboost,
    "lightgbm":            make_lightgbm,
    "catboost":            make_catboost,
}

SUPPORTS_EARLY_STOPPING = {"xgboost", "lightgbm", "catboost"}


def build(name: str, hyperparameters: dict[str, Any], *, random_state: int,
          scale_pos_weight: float | None) -> Any:
    """Return a fresh, un-fitted classifier by name."""

    if name not in REGISTRY:
        raise KeyError(f"Unknown model {name!r}. Known: {sorted(REGISTRY)}")
    return REGISTRY[name](hyperparameters, random_state, scale_pos_weight)


__all__ = ["build", "REGISTRY", "SUPPORTS_EARLY_STOPPING"]
