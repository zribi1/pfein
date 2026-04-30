"""Temporal split and rolling validation folds.

The pipeline needs an ``observation_date`` per row so it can split honestly by
time. We derive it differently for each class:

* **Cessées** (``est_active == 0``) → ``cessation.dateRadiation`` if present.
  If it is missing, we fall back to the proxy date rule used for actives.
* **Actives** (``est_active == 1``) → ``reference_date - jours_depuis_update`` days.
  (Every record is still active *today*; we simulate having observed it on the
  date its attributes were last refreshed.)

Rows for which no observation date can be derived are dropped with a log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

OBS_DATE_COLUMN = "observation_date"


@dataclass(frozen=True)
class Split:
    df_train: pd.DataFrame
    df_test: pd.DataFrame


@dataclass(frozen=True)
class Fold:
    name: str
    train_idx: np.ndarray
    val_idx: np.ndarray
    train_end: date
    val_end: date


def add_observation_date(
    df: pd.DataFrame,
    *,
    reference_date: date,
    target_column: str = "est_active",
    event_value: int = 0,
) -> pd.DataFrame:
    """Attach an ``observation_date`` column to every row.

    Rows missing both a radiation date and ``jours_depuis_update`` are dropped.
    """

    out = df.copy()
    ref_ts = pd.Timestamp(reference_date)

    radiation = pd.to_datetime(
        out.get("cessation.dateRadiation"), errors="coerce"
    )
    days_since_update = pd.to_numeric(
        out.get("jours_depuis_update"), errors="coerce"
    )
    proxy = ref_ts - pd.to_timedelta(days_since_update, unit="D")

    y = (out[target_column] == event_value).astype(int)
    obs = np.where(y == 1, radiation, proxy)
    out[OBS_DATE_COLUMN] = pd.to_datetime(obs, errors="coerce")

    # For ceased rows where radiation is missing, fall back to the proxy date.
    fallback = out[OBS_DATE_COLUMN].isna() & (y == 1)
    if fallback.any():
        out.loc[fallback, OBS_DATE_COLUMN] = proxy.loc[fallback]

    dropped = int(out[OBS_DATE_COLUMN].isna().sum())
    if dropped:
        logger.warning(
            "Dropping %d rows with no derivable observation_date (no radiation "
            "date AND no jours_depuis_update).",
            dropped,
        )
        out = out.loc[out[OBS_DATE_COLUMN].notna()].copy()

    return out.reset_index(drop=True)


def temporal_split(
    df: pd.DataFrame,
    *,
    test_cutoff: date,
) -> Split:
    """Return (train, test) where test = rows with observation_date >= cutoff."""

    if OBS_DATE_COLUMN not in df.columns:
        raise ValueError(
            f"{OBS_DATE_COLUMN!r} missing - call add_observation_date() first."
        )
    cutoff_ts = pd.Timestamp(test_cutoff)
    train = df.loc[df[OBS_DATE_COLUMN] < cutoff_ts].copy().reset_index(drop=True)
    test = df.loc[df[OBS_DATE_COLUMN] >= cutoff_ts].copy().reset_index(drop=True)

    logger.info(
        "Temporal split: train=%d rows (< %s) | test=%d rows (>= %s)",
        len(train),
        test_cutoff,
        len(test),
        test_cutoff,
    )
    return Split(df_train=train, df_test=test)


def rolling_folds(
    df: pd.DataFrame,
    *,
    n_folds: int,
    gap_years: int,
) -> list[Fold]:
    """Produce expanding-window temporal validation folds.

    Fold *i* uses every row with observation_date < train_end as train,
    and rows in [train_end, val_end) as validation. Train/val are disjoint,
    and later folds see strictly more history.
    """

    if OBS_DATE_COLUMN not in df.columns:
        raise ValueError(
            f"{OBS_DATE_COLUMN!r} missing - call add_observation_date() first."
        )
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")

    dates = df[OBS_DATE_COLUMN]
    max_date = pd.Timestamp(dates.max()).date()
    folds: list[Fold] = []

    for i in range(n_folds):
        # Fold 0 (closest to the end) val = [max - gap, max)
        # Fold 1 val = [max - 2*gap, max - gap)
        # ...
        val_end = max_date - timedelta(days=365 * gap_years * i)
        train_end = val_end - timedelta(days=365 * gap_years)
        val_end_ts = pd.Timestamp(val_end)
        train_end_ts = pd.Timestamp(train_end)

        train_mask = dates < train_end_ts
        val_mask = (dates >= train_end_ts) & (dates < val_end_ts)

        if train_mask.sum() == 0 or val_mask.sum() == 0:
            logger.warning(
                "Fold %d has empty train or val (train=%d, val=%d) - skipping.",
                i,
                int(train_mask.sum()),
                int(val_mask.sum()),
            )
            continue

        folds.append(
            Fold(
                name=f"fold_{len(folds)}",
                train_idx=np.flatnonzero(train_mask.to_numpy()),
                val_idx=np.flatnonzero(val_mask.to_numpy()),
                train_end=train_end,
                val_end=val_end,
            )
        )

    # Chronological order (earliest first)
    folds.reverse()
    for fold in folds:
        logger.info(
            "%s: train<%s (n=%d) | val=[%s, %s) (n=%d)",
            fold.name,
            fold.train_end,
            len(fold.train_idx),
            fold.train_end,
            fold.val_end,
            len(fold.val_idx),
        )
    return folds
