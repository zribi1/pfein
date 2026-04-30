"""RandomForest baseline."""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier


def make_random_forest(params: dict[str, Any], random_state: int,
                       scale_pos_weight: float | None):
    return RandomForestClassifier(
        n_estimators=int(params.get("n_estimators", 400)),
        max_depth=int(params.get("max_depth", 14)),
        min_samples_leaf=int(params.get("min_samples_leaf", 5)),
        max_features=params.get("max_features", "sqrt"),
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
