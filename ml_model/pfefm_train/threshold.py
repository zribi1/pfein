"""Threshold selection strategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.metrics import f1_score, precision_recall_curve

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThresholdDecision:
    strategy: str
    value: float
    rationale: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "value": float(self.value),
            "rationale": {k: float(v) for k, v in self.rationale.items()},
        }


def recall_at_min_precision(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    min_precision: float,
) -> ThresholdDecision:
    """Largest recall such that precision >= ``min_precision``."""

    prec, rec, thr = precision_recall_curve(y_true, y_prob)
    # precision_recall_curve pads the last point with precision=1, recall=0.
    valid = prec[:-1] >= min_precision
    if not valid.any():
        # relax: pick the threshold whose precision is closest to the floor
        best_idx = int(np.argmin(np.abs(prec[:-1] - min_precision)))
        logger.warning(
            "No threshold reaches precision >= %.3f; falling back to the "
            "closest one (precision=%.3f, recall=%.3f).",
            min_precision,
            prec[best_idx],
            rec[best_idx],
        )
    else:
        candidates = np.flatnonzero(valid)
        best_idx = int(candidates[np.argmax(rec[candidates])])

    value = float(thr[best_idx]) if best_idx < len(thr) else 0.5
    return ThresholdDecision(
        strategy="recall_at_min_precision",
        value=value,
        rationale={
            "min_precision": float(min_precision),
            "achieved_precision": float(prec[best_idx]),
            "achieved_recall": float(rec[best_idx]),
        },
    )


def max_f1(y_true: Iterable[int], y_prob: Iterable[float]) -> ThresholdDecision:
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    grid = np.unique(np.round(y_prob, 3))
    best_t, best_f1 = 0.5, -1.0
    for t in grid:
        pred = (y_prob >= t).astype(int)
        f1 = f1_score(y_true, pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
    return ThresholdDecision(
        strategy="max_f1",
        value=best_t,
        rationale={"f1": float(best_f1)},
    )


def cost_weighted(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    cost_false_negative: float,
    cost_false_positive: float,
) -> ThresholdDecision:
    """Minimise ``FN * cfn + FP * cfp`` over a dense threshold grid."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    grid = np.unique(np.round(y_prob, 3))
    best_t, best_cost = 0.5, float("inf")
    for t in grid:
        pred = (y_prob >= t).astype(int)
        fn = int(((pred == 0) & (y_true == 1)).sum())
        fp = int(((pred == 1) & (y_true == 0)).sum())
        cost = fn * cost_false_negative + fp * cost_false_positive
        if cost < best_cost:
            best_cost = float(cost)
            best_t = float(t)
    return ThresholdDecision(
        strategy="cost_weighted",
        value=best_t,
        rationale={
            "cost_false_negative": float(cost_false_negative),
            "cost_false_positive": float(cost_false_positive),
            "min_total_cost": best_cost,
        },
    )


def choose(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    strategy: str,
    min_precision: float,
    cost_false_negative: float,
    cost_false_positive: float,
) -> ThresholdDecision:
    if strategy == "recall_at_min_precision":
        return recall_at_min_precision(y_true, y_prob, min_precision=min_precision)
    if strategy == "max_f1":
        return max_f1(y_true, y_prob)
    if strategy == "cost_weighted":
        return cost_weighted(
            y_true,
            y_prob,
            cost_false_negative=cost_false_negative,
            cost_false_positive=cost_false_positive,
        )
    raise ValueError(f"Unknown threshold strategy: {strategy!r}")
