"""Simple baselines - absolute floor to beat."""

from __future__ import annotations

from typing import Any

from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier


def make_dummy(params: dict[str, Any], random_state: int,
               scale_pos_weight: float | None):
    return DummyClassifier(strategy="prior", random_state=random_state)


def make_logistic_regression(params: dict[str, Any], random_state: int,
                             scale_pos_weight: float | None):
    return LogisticRegression(
        C=float(params.get("C", 1.0)),
        max_iter=int(params.get("max_iter", 2000)),
        class_weight="balanced",
        solver="lbfgs",
        random_state=random_state,
        n_jobs=-1,
    )


def make_decision_tree(params: dict[str, Any], random_state: int,
                       scale_pos_weight: float | None):
    return DecisionTreeClassifier(
        max_depth=int(params.get("max_depth", 6)),
        min_samples_leaf=int(params.get("min_samples_leaf", 20)),
        class_weight="balanced",
        random_state=random_state,
    )
