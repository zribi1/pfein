"""Load and split the enterprises parquet into morale / physique segments."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SEGMENT_COLUMN = "typePersonneContent"
SEGMENT_MORALE = "morale"
SEGMENT_PHYSIQUE = "physique"


@dataclass(frozen=True)
class SegmentedDataset:
    """Raw dataset split by legal-person type."""

    full: pd.DataFrame
    morale: pd.DataFrame
    physique: pd.DataFrame


def load_enterprises(input_path: str | Path) -> pd.DataFrame:
    """Read the enterprises parquet and return a dataframe."""

    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input parquet not found: {path}")

    logger.info("Reading %s", path)
    df = pd.read_parquet(path)
    logger.info("Loaded %d rows x %d columns", df.shape[0], df.shape[1])
    return df


def split_by_segment(df: pd.DataFrame) -> SegmentedDataset:
    """Return morale and physique subsets based on `typePersonneContent`."""

    if SEGMENT_COLUMN not in df.columns:
        raise KeyError(
            f"Column {SEGMENT_COLUMN!r} missing from dataset - cannot segment."
        )

    seg = df[SEGMENT_COLUMN].fillna("").astype(str).str.strip().str.lower()
    morale = df.loc[seg == SEGMENT_MORALE].copy().reset_index(drop=True)
    physique = df.loc[seg == SEGMENT_PHYSIQUE].copy().reset_index(drop=True)

    logger.info(
        "Morale: %d rows (%d ceased) | Physique: %d rows (%d ceased)",
        len(morale),
        (morale.get("est_active", pd.Series(dtype=int)) == 0).sum(),
        len(physique),
        (physique.get("est_active", pd.Series(dtype=int)) == 0).sum(),
    )
    return SegmentedDataset(full=df, morale=morale, physique=physique)
