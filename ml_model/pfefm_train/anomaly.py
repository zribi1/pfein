"""Unsupervised auxiliary anomaly detector (Isolation Forest).

Trained on *active* morale companies so that "anomalies" are those that look
different from the typical active firm. Scores are not validated labels and
must be presented as an auxiliary signal only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnomalyOutputs:
    model: IsolationForest
    features: list[str]
    scores: pd.Series        # decision_function
    is_anomaly: pd.Series    # 0/1


def _prepare(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for col in features:
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0.0)
    return X


def fit_and_score(
    df: pd.DataFrame,
    *,
    features: Iterable[str],
    active_mask: pd.Series,
    contamination: float,
    n_estimators: int,
    random_state: int,
) -> AnomalyOutputs:
    """Fit on the active subset, score the full frame."""

    feats = [f for f in features if f in df.columns]
    missing = set(features) - set(feats)
    if missing:
        logger.warning("Anomaly features missing from data: %s", sorted(missing))

    X_full = _prepare(df, feats)
    X_active = X_full.loc[active_mask.to_numpy()]

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_active)
    logger.info(
        "IsolationForest fitted on %d active rows (contamination=%.2f, features=%d)",
        len(X_active),
        contamination,
        len(feats),
    )

    scores = pd.Series(model.decision_function(X_full).round(4), index=df.index, name="anomalie_score")
    pred = pd.Series(
        (model.predict(X_full) == -1).astype(int),
        index=df.index,
        name="est_anomalie",
    )
    logger.info("Anomalies detected: %d / %d", int(pred.sum()), len(pred))
    return AnomalyOutputs(model=model, features=feats, scores=scores, is_anomaly=pred)
