"""Rule-based risk score for the physique segment.

This is **not** a supervised model. The function is deterministic, vectorised
and returns, for each row:

* ``score`` in [0, 100] (lower = riskier)
* ``band``  (one of the labels configured in ``physique_rules.yaml``)
* ``contributions`` (dict feature -> points deducted)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .config import DEFAULT_PHYSIQUE_RULES_PATH


@dataclass(frozen=True)
class PhysiqueRules:
    base_score: float
    flag_weights: dict[str, float]
    counted_weights: dict[str, dict[str, float]]
    sector_baseline: float
    sector_weight: float
    sector_cap: float
    bands: list[tuple[str, float]]                       # sorted descending by min
    band_to_category: dict[str, str]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "PhysiqueRules":
        p = Path(path) if path else DEFAULT_PHYSIQUE_RULES_PATH
        with p.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        bands = sorted(
            [(b["label"], float(b["min"])) for b in raw["bands"]],
            key=lambda t: t[1],
            reverse=True,
        )
        return cls(
            base_score=float(raw["base_score"]),
            flag_weights={k: float(v) for k, v in raw["flag_weights"].items()},
            counted_weights={
                k: {"weight": float(v["weight"]), "cap": float(v["cap"])}
                for k, v in raw["counted_weights"].items()
            },
            sector_baseline=float(raw["sector_weight"]["baseline"]),
            sector_weight=float(raw["sector_weight"]["weight"]),
            sector_cap=float(raw["sector_weight"]["cap"]),
            bands=bands,
            band_to_category=dict(raw["band_to_category"]),
            raw=raw,
        )

    def to_band(self, score: float) -> str:
        for label, threshold in self.bands:
            if score >= threshold:
                return label
        return self.bands[-1][0]


@dataclass(frozen=True)
class PhysiqueScored:
    score: pd.Series
    band: pd.Series
    contributions: pd.DataFrame


def _numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def score(df: pd.DataFrame, rules: PhysiqueRules) -> PhysiqueScored:
    """Vectorised physique score + band + per-feature contribution breakdown."""

    n = len(df)
    if n == 0:
        empty = pd.Series(dtype="float64")
        return PhysiqueScored(
            score=empty,
            band=pd.Series(dtype="object"),
            contributions=pd.DataFrame(index=df.index),
        )

    contributions = pd.DataFrame(index=df.index)
    score_vec = np.full(n, rules.base_score, dtype="float64")

    for feature, weight in rules.flag_weights.items():
        v = _numeric(df, feature, default=0.0)
        deduction = (v.astype(bool).astype(float) * weight).to_numpy()
        score_vec -= deduction
        contributions[feature] = deduction

    for feature, spec in rules.counted_weights.items():
        v = _numeric(df, feature, default=0.0).to_numpy()
        deduction = np.minimum(v * spec["weight"], spec["cap"])
        score_vec -= deduction
        contributions[feature] = deduction

    taux = _numeric(df, "taux_cessation_sectoriel", default=rules.sector_baseline).to_numpy()
    excess = np.maximum(0.0, (taux / rules.sector_baseline - 1.0) * rules.sector_weight)
    sector_deduction = np.minimum(excess, rules.sector_cap)
    score_vec -= sector_deduction
    contributions["taux_cessation_sectoriel"] = sector_deduction

    score_vec = np.clip(score_vec, 0.0, 100.0).round(2)
    score_series = pd.Series(score_vec, index=df.index, name="score_risque_physique")
    band_series = score_series.map(rules.to_band).rename("niveau_risque")

    return PhysiqueScored(
        score=score_series,
        band=band_series,
        contributions=contributions.round(2),
    )
