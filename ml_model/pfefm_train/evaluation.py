"""Evaluation metrics and business-oriented reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass(frozen=True)
class Metrics:
    roc_auc: float
    pr_auc: float
    brier: float
    precision_at_threshold: float
    recall_at_threshold: float
    f1_at_threshold: float
    threshold: float
    confusion: dict[str, int]
    extras: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float | dict]:
        return {
            "roc_auc": self.roc_auc,
            "pr_auc": self.pr_auc,
            "brier": self.brier,
            "threshold": self.threshold,
            "precision_at_threshold": self.precision_at_threshold,
            "recall_at_threshold": self.recall_at_threshold,
            "f1_at_threshold": self.f1_at_threshold,
            "confusion": self.confusion,
            **self.extras,
        }


def core_metrics(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    threshold: float = 0.5,
) -> Metrics:
    """Compute AUC + thresholded precision/recall/F1 + Brier + confusion matrix."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    y_pred = (y_prob >= threshold).astype(int)

    try:
        roc = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        roc = float("nan")
    pr = float(average_precision_score(y_true, y_prob))
    brier = float(brier_score_loss(y_true, y_prob))

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel().tolist()

    return Metrics(
        roc_auc=roc,
        pr_auc=pr,
        brier=brier,
        precision_at_threshold=float(precision_score(y_true, y_pred, zero_division=0)),
        recall_at_threshold=float(recall_score(y_true, y_pred, zero_division=0)),
        f1_at_threshold=float(f1_score(y_true, y_pred, zero_division=0)),
        threshold=float(threshold),
        confusion={"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    )


def threshold_sweep(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    grid: np.ndarray | None = None,
) -> pd.DataFrame:
    """Return a per-threshold precision/recall/F1 table."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    if grid is None:
        grid = np.linspace(0.05, 0.95, 19)

    rows = []
    for t in grid:
        y_pred = (y_prob >= t).astype(int)
        rows.append(
            {
                "threshold": float(t),
                "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, zero_division=0)),
                "positives": int(y_pred.sum()),
            }
        )
    return pd.DataFrame(rows)


def precision_recall_curve_df(
    y_true: Iterable[int],
    y_prob: Iterable[float],
) -> pd.DataFrame:
    prec, rec, thr = precision_recall_curve(y_true, y_prob)
    # precision_recall_curve returns n+1 points; align by dropping the last threshold=1.0 row
    return pd.DataFrame(
        {
            "threshold": np.concatenate([thr, [1.0]]),
            "precision": prec,
            "recall": rec,
        }
    )


def top_k_metrics(
    y_true: Iterable[int],
    y_prob: Iterable[float],
    *,
    k_grid: Iterable[int],
) -> pd.DataFrame:
    """Precision@K / Recall@K / Lift for the top-K highest-probability rows."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    n = len(y_true)
    n_pos = int(y_true.sum())
    base_rate = n_pos / n if n else 0.0
    order = np.argsort(-y_prob)
    y_sorted = y_true[order]

    rows = []
    for k in k_grid:
        k = min(int(k), n)
        if k == 0:
            continue
        hits = int(y_sorted[:k].sum())
        prec_k = hits / k
        recall_k = hits / n_pos if n_pos else 0.0
        lift = prec_k / base_rate if base_rate > 0 else float("nan")
        rows.append(
            {
                "k": k,
                "precision_at_k": prec_k,
                "recall_at_k": recall_k,
                "lift": lift,
                "hits": hits,
            }
        )
    return pd.DataFrame(rows)


def lift_by_decile(
    y_true: Iterable[int],
    y_prob: Iterable[float],
) -> pd.DataFrame:
    """Return a 10-decile lift table sorted by descending predicted probability."""

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    if len(y_true) == 0:
        return pd.DataFrame()

    n = len(y_true)
    base_rate = float(y_true.sum()) / n if n else 0.0
    order = np.argsort(-y_prob)
    y_sorted = y_true[order]
    prob_sorted = y_prob[order]

    n_bins = min(10, n)
    bin_edges = np.linspace(0, n, n_bins + 1, dtype=int)
    rows = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if lo == hi:
            continue
        slice_y = y_sorted[lo:hi]
        slice_p = prob_sorted[lo:hi]
        pos = int(slice_y.sum())
        rate = pos / len(slice_y)
        rows.append(
            {
                "decile": i + 1,
                "n": int(hi - lo),
                "positives": pos,
                "rate": rate,
                "lift": rate / base_rate if base_rate else float("nan"),
                "proba_min": float(slice_p.min()),
                "proba_max": float(slice_p.max()),
            }
        )
    return pd.DataFrame(rows)
