"""Deterministic feature engineering.

The public :func:`build_features` function is pure and depends only on the
configured reference year. It is wrapped inside the sklearn Pipeline (via
``FunctionTransformer``) so the backend can score raw enterprise rows without
having to re-implement any of this logic.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

JUDICIAL_ROLE_CODES: tuple[str, ...] = (
    "60", "65", "70", "71", "72", "73", "74", "75",
)
MANDATORY_DEPOT_FORMS: tuple[str, ...] = (
    "5499", "5710", "5720", "5599", "5531", "5560", "5498", "5308",
)


def _numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def _numeric_nullable(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _parse_year(series: pd.Series) -> pd.Series:
    """Extract a 4-digit year from free-form birth-date strings."""

    def _one(v: object) -> float:
        if v is None:
            return np.nan
        s = str(v).strip()
        if len(s) >= 4 and s[:4].isdigit():
            return int(s[:4])
        return np.nan

    return series.map(_one).astype("float64")


def build_features(
    df: pd.DataFrame,
    *,
    reference_year: int = 2026,
) -> pd.DataFrame:
    """Return a copy of ``df`` with derived feature columns added.

    Parameters
    ----------
    df
        Raw enterprise dataframe. Missing source columns are tolerated - the
        dependent derived feature falls back to a sensible default.
    reference_year
        Used to compute the director's age. Configurable so the pipeline is
        reproducible regardless of ``date.today()``.
    """

    out = df.copy()

    # Director role -----------------------------------------------------------
    role_str = (
        out.get("dirigeant_role", pd.Series("", index=out.index))
        .fillna("")
        .astype(str)
        .str.strip()
    )
    out["dirigeant_role_str"] = role_str
    out["dirigeant_est_judiciaire"] = role_str.isin(JUDICIAL_ROLE_CODES).astype(int)
    out["dirigeant_est_liquidateur"] = (role_str == "73").astype(int)
    out["dirigeant_est_mandataire"] = (role_str == "65").astype(int)

    # Director age ------------------------------------------------------------
    if "dirigeant_ddn" in out.columns:
        year = _parse_year(out["dirigeant_ddn"])
        age = reference_year - year
        age = age.where(age.between(18, 100), np.nan)
        out["dirigeant_age"] = age
        out["dirigeant_age_risque"] = np.where(
            age.isna(), 0, ((age < 25) | (age > 70)).astype(int)
        )
    else:
        out["dirigeant_age"] = np.nan
        out["dirigeant_age_risque"] = 0

    # Capital -----------------------------------------------------------------
    capital = _numeric_nullable(out, "identite.montantCapital")
    out["capital_symbolique"] = (capital == 1).astype(int)
    out["capital_tres_faible"] = capital.between(0, 1000, inclusive="both").astype(int)
    out["capital_absent"] = capital.isna().astype(int)

    # Representatives ---------------------------------------------------------
    nb_rep = _numeric(out, "nombreRepresentantsActifs", default=0)
    out["pas_representant_actif"] = (nb_rep == 0).astype(int)

    # Mandatory filing respect ------------------------------------------------
    fj = (
        out.get("identite.formeJuridique", pd.Series("", index=out.index))
        .fillna("")
        .astype(str)
        .str.strip()
    )
    age_num = _numeric(out, "age_ans", default=0.0)
    nb_ann = _numeric(out, "nb_annonces_bodacc", default=0.0)
    flag_depot = _numeric(out, "flag_depot_comptes", default=0.0)
    out["depot_non_respecte"] = (
        fj.isin(MANDATORY_DEPOT_FORMS) & (flag_depot == 0) & (age_num > 2)
    ).astype(int)

    # Frequencies -------------------------------------------------------------
    out["frequence_bodacc"] = np.where(
        age_num > 0, (nb_ann / age_num).round(4), 0.0
    )
    nb_obs = _numeric(out, "nb_observations", default=0.0)
    out["frequence_observations"] = np.where(
        age_num > 0, (nb_obs / age_num).round(4), 0.0
    )

    # Sector / cohort signals -------------------------------------------------
    taux = _numeric(out, "taux_cessation_sectoriel", default=0.0)
    taux_mean = float(taux.mean()) if len(taux) else 0.0
    out["jeune_secteur_risque"] = ((age_num < 3) & (taux > taux_mean)).astype(int)

    nb_etab_ouv = _numeric(out, "nombreEtablissementsOuverts", default=0.0)
    out["ancienne_inactive"] = (
        (age_num > 20) & (nb_ann == 0) & (nb_etab_ouv == 0)
    ).astype(int)

    est_micro = _numeric(out, "est_micro", default=0.0).astype(int)
    out["micro_sans_capital"] = (
        (est_micro == 1) & (capital.isna() | (capital == 0))
    ).astype(int)

    # Bilan - negative equity flag (convenient boolean feature) ---------------
    if "bilan_capitaux_propres" in out.columns:
        bcap = _numeric_nullable(out, "bilan_capitaux_propres")
        out["bilan_capitaux_negatifs"] = (bcap < 0).fillna(False).astype(int)
    elif "bilan_capitaux_negatifs" not in out.columns:
        out["bilan_capitaux_negatifs"] = 0

    return out


def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Return ``df`` with every name in ``columns`` present (NaN if missing)."""

    out = df.copy()
    for c in columns:
        if c not in out.columns:
            out[c] = np.nan
    return out
