"""Probability calibration diagnostics and optional wrapper."""

from __future__ import annotations

import logging
from typing import Iterable

import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss

logger = logging.getLogger(__name__)


def reliability_points(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (mean_predicted_prob, observed_frequency) for a reliability plot."""

    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")
    return prob_pred, prob_true


def brier(y_true: Iterable[int], y_prob: Iterable[float]) -> float:
    return float(brier_score_loss(y_true, y_prob))


def calibrate(estimator, method: str):
    """Wrap a pre-fitted estimator in a ``CalibratedClassifierCV``.

    Use ``method="none"`` to return the estimator unchanged.
    """

    if method == "none":
        return estimator
    if method not in {"isotonic", "sigmoid"}:
        raise ValueError(f"Unknown calibration method: {method!r}")
    logger.info("Calibrating estimator with %s", method)
    return CalibratedClassifierCV(estimator, method=method, cv="prefit")
