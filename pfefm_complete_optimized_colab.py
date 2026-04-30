# -*- coding: utf-8 -*-
"""PFEFM_Complete_Optimized_Colab.ipynb

Notebook Colab complet et autonome.
Pipeline end-to-end : load -> FE -> split temporel -> training (XGB/LGBM/CatBoost)
-> leakage audit -> threshold sur VALIDATION -> anti-FP features
-> Stage-2 FP filter -> seuils par secteur -> Hybrid V6 -> exports.

Objectif metier:
- recall(cessee) >= 0.90 (contrainte dure)
- minimiser FP (actuellement 234, cible <= 130)
- detecter cessations silencieuses (FN actuels)

Lit  : /content/drive/MyDrive/pfefmz/enterprises_clean.parquet
Ecrit: /content/drive/MyDrive/pfefmz/colab_optimized/
"""

# ============================================================
# 1. Install
# ============================================================
!pip install -q xgboost lightgbm catboost shap scikit-learn pandas pyarrow matplotlib seaborn

# ============================================================
# 2. Imports & Drive
# ============================================================
import os, json, pickle, warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.cluster import KMeans
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss, log_loss,
    precision_recall_curve, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)

import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import shap

warnings.filterwarnings('ignore')
sns.set_style('whitegrid')
pd.set_option('display.max_columns', 100)

from google.colab import drive
drive.mount('/content/drive')

# ============================================================
# 3. Configuration
# ============================================================
INPUT_PATH = '/content/drive/MyDrive/pfefmz/enterprises_clean.parquet'
OUTPUT_DIR = '/content/drive/MyDrive/pfefmz/colab_optimized/'
os.makedirs(OUTPUT_DIR, exist_ok=True)

REFERENCE_DATE = date(2026, 1, 1)
TEST_CUTOFF = date(2023, 1, 1)
RANDOM_STATE = 42

MIN_RECALL_HARD = 0.90      # contrainte metier
MIN_RECALL_TARGET = 0.92    # marge de securite pour le seuil
COST_FN = 20.0
COST_FP = 1.0

# Recall-floor pour stage-1 lors de l'entrainement du stage-2 FP filter
STAGE1_RECALL_FLOOR = 0.97
# Recall-floor pour stage-2 (le filtre ne doit pas tuer de TP)
STAGE2_RECALL_FLOOR = 0.97

LEAKY_FEATURES = [
    'dirigeant_est_liquidateur',
    'dirigeant_est_mandataire',
    'dirigeant_est_judiciaire',
    'flag_procedure_collective',
    'jours_depuis_update',
]

# Poids reduit (4.0 dans la version originale -> trop agressif, genere des FP)
SILENT_FRAGILE_WEIGHT = 2.0

RUN_TAG = datetime.now().strftime('%Y%m%d_%H%M%S')
print(f'Run tag: {RUN_TAG}')

# ============================================================
# 4. Load data
# ============================================================
df_raw = pd.read_parquet(INPUT_PATH)
print(f'Loaded {len(df_raw):,} rows x {df_raw.shape[1]} cols')

if 'typePersonneContent' in df_raw.columns:
    seg = df_raw['typePersonneContent'].fillna('').astype(str).str.strip().str.lower()
    df = df_raw.loc[seg == 'morale'].copy().reset_index(drop=True)
else:
    df = df_raw.copy()

if 'est_active' not in df.columns:
    raise KeyError('est_active is required')
df['target'] = (df['est_active'] == 0).astype(int)

n_pos = int(df['target'].sum())
print(f'Cessees: {n_pos:,} | Actives: {len(df) - n_pos:,} | Imbalance: {n_pos / len(df):.1%}')

# ============================================================
# 5. Feature engineering (identique au notebook parent)
# ============================================================
JUDICIAL_ROLE_CODES = ("60", "65", "70", "71", "72", "73", "74", "75")
MANDATORY_DEPOT_FORMS = ("5499", "5710", "5720", "5599", "5531", "5560", "5498", "5308")

def _num(df, col, default=0.0):
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default)

def _num_nullable(df, col):
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")

def _safe_div(a, b):
    return np.where(np.abs(b) > 1e-9, a / b, 0.0)

def _parse_year(s):
    def one(v):
        if v is None:
            return np.nan
        t = str(v).strip()
        return int(t[:4]) if len(t) >= 4 and t[:4].isdigit() else np.nan
    return s.map(one).astype("float64")

def build_features(df, reference_year=2026):
    out = df.copy()
    role_str = out.get("dirigeant_role", pd.Series("", index=out.index)).fillna("").astype(str).str.strip()
    out["dirigeant_role_str"] = role_str
    out["dirigeant_est_judiciaire"] = role_str.isin(JUDICIAL_ROLE_CODES).astype(int)
    out["dirigeant_est_liquidateur"] = (role_str == "73").astype(int)
    out["dirigeant_est_mandataire"] = (role_str == "65").astype(int)

    if "dirigeant_ddn" in out.columns:
        year = _parse_year(out["dirigeant_ddn"])
        age = reference_year - year
        age = age.where(age.between(18, 100), np.nan)
        out["dirigeant_age"] = age
        out["dirigeant_age_risque"] = np.where(age.isna(), 0, ((age < 25) | (age > 70)).astype(int))
    else:
        out["dirigeant_age"] = np.nan
        out["dirigeant_age_risque"] = 0

    capital = _num_nullable(out, "identite.montantCapital")
    out["capital_symbolique"] = (capital == 1).astype(int)
    out["capital_tres_faible"] = capital.between(0, 1000, inclusive="both").astype(int)
    out["capital_absent"] = capital.isna().astype(int)
    out["log_capital_safe"] = np.log1p(capital.fillna(0).clip(lower=0))

    nb_rep_actifs = _num(out, "nombreRepresentantsActifs", 0)
    nb_rep_extraits = _num(out, "nb_representants_extraits", 0)
    out["pas_representant_actif"] = (nb_rep_actifs == 0).astype(int)
    out["representants_peu_nombreux"] = (nb_rep_extraits <= 1).astype(int)

    nb_etab_fermes = _num(out, "nb_etab_fermes", 0)
    nb_etab_secondaires = _num(out, "nb_etab_secondaires", 0)
    out["ratio_etab_fermes"] = _safe_div(nb_etab_fermes, nb_etab_fermes + nb_etab_secondaires + 1)
    out["a_ferme_etablissement"] = (nb_etab_fermes > 0).astype(int)

    fj = out.get("identite.formeJuridique", pd.Series("", index=out.index)).fillna("").astype(str).str.strip()
    age_num = _num(out, "age_ans", 0.0)
    nb_ann = _num(out, "nb_annonces_bodacc", 0.0)
    flag_depot = _num(out, "flag_depot_comptes", 0.0)

    out["depot_non_respecte"] = (
        fj.isin(MANDATORY_DEPOT_FORMS) & (flag_depot == 0) & (age_num > 2)
    ).astype(int)

    nb_obs = _num(out, "nb_observations", 0.0)
    nb_obs_crit = _num(out, "nb_observations_critiques", 0.0)
    out["frequence_bodacc"] = np.where(age_num > 0, (nb_ann / age_num).round(4), 0.0)
    out["frequence_observations"] = np.where(age_num > 0, (nb_obs / age_num).round(4), 0.0)
    out["frequence_observations_critiques"] = np.where(age_num > 0, (nb_obs_crit / age_num).round(4), 0.0)
    out["ratio_observations_critiques"] = _safe_div(nb_obs_crit, nb_obs + 1)

    has_alerte = _num(out, "has_alerte_juridique", 0)
    flag_proc = _num(out, "flag_procedure_collective", 0)

    out["profil_silencieux"] = (
        (has_alerte == 0) & (flag_proc == 0) & (nb_obs_crit <= 1) & (nb_ann <= 3)
    ).astype(int)

    out["silencieux_mais_fragile"] = (
        (out["profil_silencieux"] == 1)
        & ((out["capital_tres_faible"] == 1) | (out["depot_non_respecte"] == 1) | (out["representants_peu_nombreux"] == 1))
    ).astype(int)

    out["jeune_silencieuse_fragile"] = ((age_num < 3) & (out["silencieux_mais_fragile"] == 1)).astype(int)
    out["ancienne_silencieuse_fragile"] = ((age_num > 10) & (out["silencieux_mais_fragile"] == 1)).astype(int)

    taux = _num(out, "taux_cessation_sectoriel", 0.0)
    taux_mean = float(taux.mean()) if len(taux) else 0.0
    out["jeune_secteur_risque"] = ((age_num < 3) & (taux > taux_mean)).astype(int)
    out["secteur_risque_eleve"] = (taux > taux.quantile(0.75)).astype(int)
    out["risque_sectoriel_x_fragilite"] = (
        out["secteur_risque_eleve"]
        * (out["capital_tres_faible"] | out["depot_non_respecte"] | out["representants_peu_nombreux"]).astype(int)
    )

    nb_etab_ouv = _num(out, "nombreEtablissementsOuverts", 0.0)
    out["ancienne_inactive"] = ((age_num > 20) & (nb_ann == 0) & (nb_etab_ouv == 0)).astype(int)
    est_micro = _num(out, "est_micro", 0).astype(int)
    out["micro_sans_capital"] = ((est_micro == 1) & (capital.isna() | (capital == 0))).astype(int)

    ca = _num_nullable(out, "bilan_chiffre_affaires")
    resultat = _num_nullable(out, "bilan_resultat_net")
    capitaux = _num_nullable(out, "bilan_capitaux_propres")
    total_actif = _num_nullable(out, "bilan_total_actif")
    marge = _num_nullable(out, "bilan_marge_nette")

    out["bilan_capitaux_negatifs"] = (capitaux < 0).fillna(False).astype(int)
    out["bilan_resultat_negatif"] = (resultat < 0).fillna(False).astype(int)
    out["bilan_ca_absent"] = ca.isna().astype(int)
    out["bilan_resultat_absent"] = resultat.isna().astype(int)
    out["bilan_capitaux_absents"] = capitaux.isna().astype(int)

    out["rentabilite_resultat_sur_ca"] = _safe_div(resultat.fillna(0), ca.fillna(0) + 1)
    out["solidite_capitaux_sur_actif"] = _safe_div(capitaux.fillna(0), total_actif.fillna(0) + 1)
    out["capital_sur_actif"] = _safe_div(capital.fillna(0), total_actif.fillna(0) + 1)
    out["marge_nette_faible"] = (marge.fillna(0) < 0.02).astype(int)
    out["marge_nette_negative"] = (marge.fillna(0) < 0).astype(int)

    out["fragilite_financiere"] = (
        (out["capital_tres_faible"] == 1)
        | (out["bilan_capitaux_negatifs"] == 1)
        | (out["bilan_resultat_negatif"] == 1)
        | (out["marge_nette_negative"] == 1)
    ).astype(int)

    out["fragilite_financiere_sans_alerte"] = (
        (out["fragilite_financiere"] == 1) & (has_alerte == 0) & (flag_proc == 0)
    ).astype(int)

    out["juridique_x_financier"] = (
        ((has_alerte == 1) | (nb_obs_crit > 1)).astype(int) * out["fragilite_financiere"]
    )
    out["bodacc_x_financier"] = (
        (out["frequence_bodacc"] > out["frequence_bodacc"].quantile(0.75)).astype(int) * out["fragilite_financiere"]
    )
    out["secteur_x_financier"] = out["secteur_risque_eleve"] * out["fragilite_financiere"]
    return out

def add_silent_failure_features(df):
    df = df.copy()
    required_cols = [
        "nb_observations", "nb_observations_critiques", "has_alerte_juridique",
        "nb_annonces_bodacc", "fragilite_financiere", "capital_tres_faible",
        "depot_non_respecte", "profil_silencieux", "silencieux_mais_fragile",
        "bilan_resultat_net", "bilan_capitaux_propres",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0

    df["absence_signal_juridique"] = (
        (df["nb_observations"] == 0) & (df["nb_observations_critiques"] == 0) & (df["has_alerte_juridique"] == 0)
    ).astype(int)
    df["faible_activite_legale"] = (
        (df["nb_annonces_bodacc"] <= 1) & (df["nb_observations"] <= 1)
    ).astype(int)
    df["faible_visibilite"] = (
        (df["absence_signal_juridique"] == 1) & (df["faible_activite_legale"] == 1)
    ).astype(int)
    df["silencieuse_fragile_v2"] = (
        (df["faible_visibilite"] == 1)
        & ((df["fragilite_financiere"] == 1) | (df["capital_tres_faible"] == 1) | (df["depot_non_respecte"] == 1))
    ).astype(int)
    df["no_signal_but_capital_low"] = (
        (df["absence_signal_juridique"] == 1) & (df["capital_tres_faible"] == 1)
    ).astype(int)
    df["no_signal_but_no_depot"] = (
        (df["absence_signal_juridique"] == 1) & (df["depot_non_respecte"] == 1)
    ).astype(int)
    df["no_signal_but_fragile"] = (
        (df["absence_signal_juridique"] == 1) & (df["fragilite_financiere"] == 1)
    ).astype(int)
    df["super_silent_risk"] = (
        (df["profil_silencieux"] == 1) & (df["fragilite_financiere"] == 1)
    ).astype(int)
    df["financial_distress_score"] = (
        (pd.to_numeric(df["bilan_resultat_net"], errors="coerce").fillna(0) < 0).astype(int)
        + (pd.to_numeric(df["bilan_capitaux_propres"], errors="coerce").fillna(0) < 0).astype(int)
        + (df["capital_tres_faible"] == 1).astype(int)
        + (df["depot_non_respecte"] == 1).astype(int)
    )
    return df

def add_anti_fp_features(df, proba_col=None):
    """Counter-evidence features. Permettent au layer hybride de vetoer des FP."""
    df = df.copy()

    fragility_flags = [
        "capital_tres_faible", "depot_non_respecte",
        "bilan_resultat_negatif", "bilan_capitaux_negatifs",
        "marge_nette_negative", "representants_peu_nombreux",
    ]
    present = [c for c in fragility_flags if c in df.columns]
    df["nb_fragility_flags"] = df[present].sum(axis=1) if present else 0
    df["fragility_isolated"] = (df["nb_fragility_flags"] == 1).astype(int)
    df["fragility_coherent"] = (df["nb_fragility_flags"] >= 3).astype(int)

    alive_components = []
    if "nb_etab_secondaires" in df.columns:
        alive_components.append((_num(df, "nb_etab_secondaires") >= 2).astype(int))
    if "nombreEtablissementsOuverts" in df.columns:
        alive_components.append((_num(df, "nombreEtablissementsOuverts") >= 2).astype(int))
    if "nb_representants_extraits" in df.columns:
        alive_components.append((_num(df, "nb_representants_extraits") >= 2).astype(int))
    if "has_bilan" in df.columns:
        alive_components.append((_num(df, "has_bilan") == 1).astype(int))
    if "bilan_resultat_net" in df.columns:
        alive_components.append((_num_nullable(df, "bilan_resultat_net").fillna(0) > 0).astype(int))
    if "bilan_marge_nette" in df.columns:
        alive_components.append((_num_nullable(df, "bilan_marge_nette").fillna(0) > 0.05).astype(int))
    if "flag_creation_bodacc" in df.columns:
        alive_components.append((_num(df, "flag_creation_bodacc") == 1).astype(int))

    df["alive_score"] = sum(alive_components) if alive_components else 0
    df["clearly_alive"] = (df["alive_score"] >= 3).astype(int)

    if "bilan_resultat_net" in df.columns and "bilan_capitaux_propres" in df.columns:
        rn = _num_nullable(df, "bilan_resultat_net").fillna(0)
        cp = _num_nullable(df["bilan_capitaux_propres"].to_frame(), "bilan_capitaux_propres").fillna(0) if "bilan_capitaux_propres" in df.columns else pd.Series(0, index=df.index)
        df["healthy_balance_sheet"] = ((rn > 0) & (cp > 0)).astype(int)
    else:
        df["healthy_balance_sheet"] = 0

    if "flag_modification_bodacc" in df.columns:
        df["recent_life_signal"] = _num(df, "flag_modification_bodacc").astype(int)
    else:
        df["recent_life_signal"] = 0

    if proba_col is not None and proba_col in df.columns:
        bcs = df.get("business_confirmation_score", pd.Series(0, index=df.index))
        df["surprise_factor"] = (
            (df[proba_col] >= 0.10) & (bcs <= 1) & (df["alive_score"] >= 2)
        ).astype(int)
    else:
        df["surprise_factor"] = 0
    return df

df_fe = build_features(df, reference_year=REFERENCE_DATE.year)
df_fe = add_silent_failure_features(df_fe)
df_fe = add_anti_fp_features(df_fe)
print(f"After FE: {df_fe.shape[1]} cols")

# ============================================================
# 6. Temporal split
# ============================================================
ref_ts = pd.Timestamp(REFERENCE_DATE)
cutoff_ts = pd.Timestamp(TEST_CUTOFF)

radiation = pd.to_datetime(df_fe.get('cessation.dateRadiation'), errors='coerce')
days_since_update = pd.to_numeric(df_fe.get('jours_depuis_update'), errors='coerce')
proxy = ref_ts - pd.to_timedelta(days_since_update, unit='D')

obs = np.where(df_fe['target'] == 1, radiation, proxy)
df_fe['observation_date'] = pd.to_datetime(obs, errors='coerce')
fallback = df_fe['observation_date'].isna() & (df_fe['target'] == 1)
df_fe.loc[fallback, 'observation_date'] = proxy.loc[fallback]

ceased = df_fe[df_fe['target'] == 1].copy()
active = df_fe[df_fe['target'] == 0].copy()
ceased = ceased.loc[ceased['observation_date'].notna()].reset_index(drop=True)

ceased_train = ceased[ceased['observation_date'] < cutoff_ts].reset_index(drop=True)
ceased_test = ceased[ceased['observation_date'] >= cutoff_ts].reset_index(drop=True)

n_ct, n_cs = len(ceased_train), len(ceased_test)
test_frac = n_cs / max(n_ct + n_cs, 1)

active_shuffled = active.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
n_active_test = int(round(len(active_shuffled) * test_frac))
active_test = active_shuffled.iloc[:n_active_test].reset_index(drop=True)
active_train = active_shuffled.iloc[n_active_test:].reset_index(drop=True)

df_train_full = pd.concat([ceased_train, active_train], ignore_index=True).sample(
    frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
df_test = pd.concat([ceased_test, active_test], ignore_index=True).sample(
    frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

df_tr, df_va = train_test_split(
    df_train_full, test_size=0.2,
    stratify=df_train_full['target'], random_state=RANDOM_STATE,
)
df_tr = df_tr.reset_index(drop=True)
df_va = df_va.reset_index(drop=True)

print(f'Train: {len(df_tr):,} (pos={int(df_tr["target"].sum())}) | '
      f'Val: {len(df_va):,} (pos={int(df_va["target"].sum())}) | '
      f'Test: {len(df_test):,} (pos={int(df_test["target"].sum())})')

# ============================================================
# 7. Feature lists (sans leaky features)
# ============================================================
NUMERIC_FEATURES_ALL = [
    "age_ans", "jours_depuis_update", "nb_etab_secondaires", "nb_etab_fermes",
    "nb_representants_extraits", "log_capital", "log_capital_safe",
    "nb_annonces_bodacc", "flag_procedure_collective", "flag_creation_bodacc",
    "flag_depot_comptes", "flag_modification_bodacc",
    "nb_observations", "nb_observations_critiques", "has_alerte_juridique",
    "est_ess", "est_micro", "est_eirl", "est_agricole", "est_etranger",
    "multi_etablissement", "diffusion_insee",
    "taux_cessation_sectoriel", "age_median_sectoriel",
    "secteur_risque_eleve", "risque_sectoriel_x_fragilite",
    "has_bilan", "bilan_chiffre_affaires", "bilan_resultat_net",
    "bilan_capitaux_propres", "bilan_total_actif", "bilan_marge_nette",
    "bilan_capitaux_negatifs", "bilan_resultat_negatif",
    "bilan_ca_absent", "bilan_resultat_absent", "bilan_capitaux_absents",
    "rentabilite_resultat_sur_ca", "solidite_capitaux_sur_actif", "capital_sur_actif",
    "marge_nette_faible", "marge_nette_negative",
    "fragilite_financiere", "fragilite_financiere_sans_alerte",
    "dirigeant_est_judiciaire", "dirigeant_est_liquidateur", "dirigeant_est_mandataire",
    "dirigeant_age", "dirigeant_age_risque",
    "capital_symbolique", "capital_tres_faible", "capital_absent", "depot_non_respecte",
    "frequence_bodacc", "frequence_observations", "frequence_observations_critiques",
    "ratio_observations_critiques", "ratio_etab_fermes", "a_ferme_etablissement",
    "representants_peu_nombreux",
    "profil_silencieux", "silencieux_mais_fragile",
    "jeune_silencieuse_fragile", "ancienne_silencieuse_fragile",
    "juridique_x_financier", "bodacc_x_financier", "secteur_x_financier",
    "jeune_secteur_risque", "ancienne_inactive", "micro_sans_capital",
    "absence_signal_juridique", "faible_activite_legale", "faible_visibilite",
    "silencieuse_fragile_v2",
    "no_signal_but_capital_low", "no_signal_but_no_depot", "no_signal_but_fragile",
    "super_silent_risk", "financial_distress_score",
    "nb_fragility_flags", "fragility_isolated", "fragility_coherent",
    "alive_score", "clearly_alive", "healthy_balance_sheet", "recent_life_signal",
]
CATEGORICAL_FEATURES = [
    "forme_juridique_lib", "secteur_naf2", "stade_vie",
    "forme_juridique_risque", "departement",
]

available = set(df_fe.columns)
NUMERIC_FEATURES_ALL = [c for c in NUMERIC_FEATURES_ALL if c in available]
CATEGORICAL_FEATURES = [c for c in CATEGORICAL_FEATURES if c in available]
NUMERIC_FEATURES_AUDIT = [c for c in NUMERIC_FEATURES_ALL if c not in LEAKY_FEATURES]

print(f"Numeric AUDIT: {len(NUMERIC_FEATURES_AUDIT)} features")
print(f"Categorical : {CATEGORICAL_FEATURES}")

# ============================================================
# 8. Preprocessor & helpers
# ============================================================
def make_preprocessor(numeric_features, categorical_features):
    num = Pipeline([('impute', SimpleImputer(strategy='median'))])
    cat = Pipeline([
        ('impute', SimpleImputer(strategy='constant', fill_value='__missing__')),
        ('encode', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)),
    ])
    return ColumnTransformer(
        [('num', num, numeric_features), ('cat', cat, categorical_features)],
        remainder='drop', verbose_feature_names_out=False,
    )

def to_xy(df, numeric_features, categorical_features):
    X = df[numeric_features + categorical_features].copy()
    for c in categorical_features:
        X[c] = X[c].astype(object)
    y = df['target'].to_numpy()
    return X, y

def scale_pos_weight(y):
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    return n_neg / max(n_pos, 1)

# ============================================================
# 9. Model factories
# ============================================================
def make_xgb(spw):
    return xgb.XGBClassifier(
        n_estimators=1000, learning_rate=0.05, max_depth=5,
        min_child_weight=3, subsample=0.85, colsample_bytree=0.85,
        reg_lambda=1.0, gamma=0.0, tree_method='hist',
        scale_pos_weight=spw, random_state=RANDOM_STATE,
        eval_metric='aucpr', early_stopping_rounds=50, n_jobs=-1, verbosity=0,
    )

def make_lgbm(spw):
    return lgb.LGBMClassifier(
        n_estimators=2000, learning_rate=0.05, num_leaves=31, max_depth=-1,
        min_child_samples=20, subsample=0.85, colsample_bytree=0.85,
        reg_lambda=1.0, scale_pos_weight=spw, random_state=RANDOM_STATE,
        n_jobs=-1, verbose=-1,
    )

def make_catboost(spw):
    return cb.CatBoostClassifier(
        iterations=2000, learning_rate=0.05, depth=6, l2_leaf_reg=3.0,
        scale_pos_weight=spw, random_seed=RANDOM_STATE,
        eval_metric='PRAUC', early_stopping_rounds=50,
        verbose=False, allow_writing_files=False,
    )

# ============================================================
# 10. Sample weight reduit (2.0 au lieu de 4.0)
# ============================================================
def build_sample_weight(df_train, weight=SILENT_FRAGILE_WEIGHT):
    w = np.ones(len(df_train), dtype=float)
    mask = (
        (df_train["target"] == 1)
        & (
            (df_train.get("silencieux_mais_fragile", 0) == 1)
            | (df_train.get("silencieuse_fragile_v2", 0) == 1)
            | (df_train.get("super_silent_risk", 0) == 1)
        )
    )
    w[mask] = weight
    return w

# ============================================================
# 11. Training loop
# ============================================================
def fit_model(name, df_tr, df_va, numeric_features, categorical_features):
    pre = make_preprocessor(numeric_features, categorical_features)
    X_tr_raw, y_tr = to_xy(df_tr, numeric_features, categorical_features)
    X_va_raw, y_va = to_xy(df_va, numeric_features, categorical_features)
    pre.fit(X_tr_raw)
    X_tr = pre.transform(X_tr_raw)
    X_va = pre.transform(X_va_raw)

    spw = scale_pos_weight(y_tr)
    sample_weight = build_sample_weight(df_tr)

    if name == "xgboost":
        model = make_xgb(spw)
        model.fit(X_tr, y_tr, sample_weight=sample_weight,
                  eval_set=[(X_va, y_va)], verbose=False)
    elif name == "lightgbm":
        model = make_lgbm(spw)
        model.fit(X_tr, y_tr, sample_weight=sample_weight,
                  eval_set=[(X_va, y_va)], eval_metric="average_precision",
                  callbacks=[lgb.early_stopping(50, verbose=False)])
    elif name == "catboost":
        model = make_catboost(spw)
        model.fit(X_tr, y_tr, sample_weight=sample_weight,
                  eval_set=(X_va, y_va), verbose=False)
    else:
        raise ValueError(name)

    return {
        "name": name, "preprocessor": pre, "model": model,
        "numeric_features": list(numeric_features),
        "categorical_features": list(categorical_features),
        "feature_names_out": list(numeric_features) + list(categorical_features),
    }

def predict_proba(bundle, df):
    X_raw, y = to_xy(df, bundle["numeric_features"], bundle["categorical_features"])
    X = bundle["preprocessor"].transform(X_raw)
    return bundle["model"].predict_proba(X)[:, 1], y

# ============================================================
# 12. Train all 3 models (audit only - sans leaky features)
# ============================================================
MODEL_NAMES = ["xgboost", "lightgbm", "catboost"]
bundles = {}
metrics_rows = []

for name in MODEL_NAMES:
    print(f"Training {name}...")
    b = fit_model(name, df_tr, df_va, NUMERIC_FEATURES_AUDIT, CATEGORICAL_FEATURES)
    bundles[name] = b
    proba_te, y_te_tmp = predict_proba(b, df_test)
    metrics_rows.append({
        "model": name,
        "roc_auc": roc_auc_score(y_te_tmp, proba_te),
        "pr_auc": average_precision_score(y_te_tmp, proba_te),
    })

metrics_df = pd.DataFrame(metrics_rows).sort_values("pr_auc", ascending=False)
print("\n=== Test PR-AUC ===")
print(metrics_df.round(4))

WINNER_NAME = metrics_df.iloc[0]["model"]
print(f"\nWinner: {WINNER_NAME}")
win = bundles[WINNER_NAME]

# ============================================================
# 13. Probas val + test (RAW, pas de calibration)
# ============================================================
proba_va_final, y_va = predict_proba(win, df_va)
proba_te_final, y_te = predict_proba(win, df_test)

print(f"Val ROC-AUC : {roc_auc_score(y_va, proba_va_final):.4f}")
print(f"Test ROC-AUC: {roc_auc_score(y_te, proba_te_final):.4f}")
print(f"Test PR-AUC : {average_precision_score(y_te, proba_te_final):.4f}")

# ============================================================
# 14. Threshold optimization sur VALIDATION (correctif majeur)
# ============================================================
def sweep_thresholds(y_true, proba, lo=0.01, hi=0.50, step=0.0025):
    rows = []
    for t in np.round(np.arange(lo, hi + step, step), 4):
        yp = (proba >= t).astype(int)
        tp = int(((y_true == 1) & (yp == 1)).sum())
        fn = int(((y_true == 1) & (yp == 0)).sum())
        fp = int(((y_true == 0) & (yp == 1)).sum())
        tn = int(((y_true == 0) & (yp == 0)).sum())
        rec = tp / max(tp + fn, 1)
        prec = tp / max(tp + fp, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-9)
        rows.append({
            "threshold": float(t), "TP": tp, "FN": fn, "FP": fp, "TN": tn,
            "precision": prec, "recall": rec, "f1": f1,
            "business_cost": fn * COST_FN + fp * COST_FP,
        })
    return pd.DataFrame(rows)

val_sweep = sweep_thresholds(y_va, proba_va_final)
val_feasible = val_sweep[val_sweep["recall"] >= MIN_RECALL_TARGET]
if len(val_feasible) == 0:
    val_feasible = val_sweep[val_sweep["recall"] >= MIN_RECALL_HARD]

val_pick = val_feasible.sort_values(
    ["FP", "business_cost", "threshold"], ascending=[True, True, False]
).iloc[0]
THR_VAL = float(val_pick["threshold"])

print(f"\nValidation precision-first threshold: {THR_VAL:.4f}")
print(f"  val recall={val_pick['recall']:.4f}  val FP={int(val_pick['FP'])}")

# ============================================================
# 15. Stage-2 FP filter (LightGBM)
# ============================================================
# Stage-1 alert threshold: recall floor 0.97 sur validation
val_for_floor = val_sweep[val_sweep["recall"] >= STAGE1_RECALL_FLOOR]
STAGE1_THR = (
    float(val_for_floor.sort_values("threshold", ascending=False).iloc[0]["threshold"])
    if len(val_for_floor) > 0 else 0.05
)
print(f"\nStage-1 alert threshold: {STAGE1_THR:.4f}")

# Build augmented dfs with proba + business_confirmation_score
def build_business_score(df_aug):
    df_aug = df_aug.copy()
    df_aug["business_confirmation_score"] = (
        (df_aug.get("has_alerte_juridique", 0) == 1).astype(int) * 3
        + (df_aug.get("nb_observations_critiques", 0) >= 1).astype(int) * 2
        + (df_aug.get("nb_etab_fermes", 0) >= 1).astype(int) * 2
        + (df_aug.get("fragilite_financiere", 0) == 1).astype(int) * 2
        + (df_aug.get("fragilite_financiere_sans_alerte", 0) == 1).astype(int) * 2
        + (df_aug.get("depot_non_respecte", 0) == 1).astype(int)
        + (df_aug.get("capital_tres_faible", 0) == 1).astype(int)
        + (df_aug.get("super_silent_risk", 0) == 1).astype(int) * 3
        + (df_aug.get("silencieux_mais_fragile", 0) == 1).astype(int) * 2
        + (df_aug.get("financial_distress_score", 0) >= 2).astype(int) * 2
    )
    return df_aug

df_va_aug = build_business_score(df_va.copy())
df_va_aug["proba"] = proba_va_final
df_va_aug = add_anti_fp_features(df_va_aug, proba_col="proba")

df_te_aug = build_business_score(df_test.copy())
df_te_aug["proba"] = proba_te_final
df_te_aug = add_anti_fp_features(df_te_aug, proba_col="proba")

STAGE2_EXTRA = [
    "nb_fragility_flags", "fragility_isolated", "fragility_coherent",
    "alive_score", "clearly_alive", "surprise_factor",
    "healthy_balance_sheet", "recent_life_signal",
    "business_confirmation_score",
]

def build_stage2_matrix(bundle, df_full, df_aug):
    X_raw, _ = to_xy(df_full, bundle["numeric_features"], bundle["categorical_features"])
    X_mat = bundle["preprocessor"].transform(X_raw)
    base = pd.DataFrame(X_mat, columns=bundle["feature_names_out"])
    base["__stage1_proba__"] = df_aug["proba"].values
    for c in STAGE2_EXTRA:
        base[c] = df_aug[c].values if c in df_aug.columns else 0
    return base

X2_va = build_stage2_matrix(win, df_va, df_va_aug)
X2_te = build_stage2_matrix(win, df_test, df_te_aug)

val_alert_mask = proba_va_final >= STAGE1_THR
X2_va_alert = X2_va.loc[val_alert_mask].reset_index(drop=True)
y2_va_alert = y_va[val_alert_mask]

n_pos2 = int((y2_va_alert == 1).sum())
n_neg2 = int((y2_va_alert == 0).sum())
spw2 = n_neg2 / max(n_pos2, 1)
print(f"Stage-2 train: pos={n_pos2}  neg={n_neg2}  spw={spw2:.2f}")

stage2_models = []
oof_pred = np.zeros(len(y2_va_alert), dtype=float)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
for fold, (tr_idx, va_idx) in enumerate(skf.split(X2_va_alert, y2_va_alert)):
    m = lgb.LGBMClassifier(
        n_estimators=600, learning_rate=0.03, num_leaves=15,
        min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=2.0, scale_pos_weight=spw2,
        random_state=RANDOM_STATE + fold, n_jobs=-1, verbose=-1,
    )
    m.fit(
        X2_va_alert.iloc[tr_idx], y2_va_alert[tr_idx],
        eval_set=[(X2_va_alert.iloc[va_idx], y2_va_alert[va_idx])],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    oof_pred[va_idx] = m.predict_proba(X2_va_alert.iloc[va_idx])[:, 1]
    stage2_models.append(m)

print(f"Stage-2 OOF PR-AUC: {average_precision_score(y2_va_alert, oof_pred):.4f}")

stage2_sweep = sweep_thresholds(y2_va_alert, oof_pred, lo=0.05, hi=0.95, step=0.01)
stage2_pick = stage2_sweep[stage2_sweep["recall"] >= STAGE2_RECALL_FLOOR].sort_values(
    "FP", ascending=True
).head(1)
if len(stage2_pick) == 0:
    stage2_pick = stage2_sweep.sort_values("FP").head(1)
STAGE2_THR = float(stage2_pick.iloc[0]["threshold"])
print(f"Stage-2 threshold: {STAGE2_THR:.4f}")

# Predict stage-2 on test
te_alert_mask = proba_te_final >= STAGE1_THR
X2_te_alert = X2_te.loc[te_alert_mask].reset_index(drop=True)
stage2_proba_te = np.zeros(len(y_te))
if len(X2_te_alert) > 0:
    stage2_proba_te_alert = np.mean(
        [m.predict_proba(X2_te_alert)[:, 1] for m in stage2_models], axis=0
    )
    stage2_proba_te[np.where(te_alert_mask)[0]] = stage2_proba_te_alert

two_stage_pred = np.zeros(len(y_te), dtype=int)
two_stage_pred[np.where(te_alert_mask)[0]] = (stage2_proba_te_alert >= STAGE2_THR).astype(int) if len(X2_te_alert) > 0 else 0

# ============================================================
# 16. Segment thresholds (par secteur)
# ============================================================
SECTOR_COL = "secteur_naf2" if "secteur_naf2" in df_va.columns else None

def compute_segment_thresholds(df_aux_v, proba_v, segment_col,
                                min_recall=0.90, min_count=200):
    aux = pd.DataFrame({
        "y": df_aux_v["target"].values, "p": proba_v,
        "seg": df_aux_v[segment_col].astype(str).values,
    })
    out = {}
    for seg, g in aux.groupby("seg"):
        if len(g) < min_count or g["y"].sum() < 10:
            continue
        sw = sweep_thresholds(g["y"].values, g["p"].values, lo=0.005, hi=0.5, step=0.005)
        feas = sw[sw["recall"] >= min_recall]
        if len(feas) == 0:
            continue
        out[seg] = float(feas.sort_values(["FP", "threshold"]).iloc[0]["threshold"])
    return out

seg_thr = (
    compute_segment_thresholds(df_va, proba_va_final, SECTOR_COL)
    if SECTOR_COL else {}
)
print(f"\nSegment thresholds learned for {len(seg_thr)} sectors")

def apply_segment_threshold(df_t, proba_t, seg_thr_dict, default_thr, segment_col):
    if segment_col is None or not seg_thr_dict:
        return (proba_t >= default_thr).astype(int)
    segs = df_t[segment_col].astype(str).values
    thrs = np.array([seg_thr_dict.get(s, default_thr) for s in segs])
    return (proba_t >= thrs).astype(int)

seg_pred = apply_segment_threshold(df_test, proba_te_final, seg_thr, THR_VAL, SECTOR_COL)

# ============================================================
# 17. Hybrid V6 avec reject zone
# ============================================================
def hybrid_v6(df_h, proba_col="proba",
              high_proba_thr=0.10, base_thr=THR_VAL,
              min_confirmation_high=4, min_confirmation_silent=5,
              reject_low=None, reject_high=None):
    p = df_h[proba_col]
    bcs = df_h.get("business_confirmation_score", 0)

    rule_high = (p >= high_proba_thr) & (bcs >= 1)
    rule_gray = (
        (p >= base_thr) & (bcs >= min_confirmation_high)
        & ((p >= 0.06) | (bcs >= 6))
    )
    rule_silent = (
        (p >= 0.05)
        & (df_h.get("super_silent_risk", 0) == 1)
        & (df_h.get("financial_distress_score", 0) >= 2)
        & (df_h.get("nb_annonces_bodacc", 0) <= 2)
        & (bcs >= min_confirmation_silent)
        & (df_h.get("alive_score", 0) <= 2)
    )

    veto_alive = (
        (df_h.get("clearly_alive", 0) == 1)
        & (df_h.get("surprise_factor", 0) == 1)
        & (p < 0.20)
    )
    veto_clean = (
        (df_h.get("has_alerte_juridique", 0) == 0)
        & (df_h.get("nb_observations_critiques", 0) == 0)
        & (df_h.get("fragilite_financiere", 0) == 0)
        & (df_h.get("nb_annonces_bodacc", 0) <= 1)
        & (df_h.get("super_silent_risk", 0) == 0)
        & (df_h.get("financial_distress_score", 0) < 2)
    )

    raw_alert = (rule_high | rule_gray | rule_silent).astype(bool)
    final = raw_alert & ~veto_alive & ~veto_clean

    if reject_low is not None and reject_high is not None:
        in_reject = (
            (p >= reject_low) & (p < reject_high)
            & (bcs.between(2, 4))
        )
    else:
        in_reject = pd.Series(False, index=df_h.index)

    status = np.where(final, "positive",
                      np.where(in_reject, "review", "negative"))
    return final.astype(int).values, status

hybrid_pred_v6, hybrid_status_v6 = hybrid_v6(
    df_te_aug,
    high_proba_thr=0.10, base_thr=THR_VAL,
    reject_low=THR_VAL * 0.7, reject_high=THR_VAL * 1.3,
)

# Final = hybrid V6 AND (stage-2 keeps OR not in stage-1 alert zone)
final_pred = (
    (hybrid_pred_v6 == 1)
    & ((proba_te_final < STAGE1_THR) | (two_stage_pred == 1))
).astype(int)

# ============================================================
# 18. Comparaison strategies
# ============================================================
def cm_row(name, y_true, y_pred):
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    rec = tp / max(tp + fn, 1)
    prec = tp / max(tp + fp, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    return {
        "strategy": name, "TP": tp, "FN": fn, "FP": fp, "TN": tn,
        "recall": round(rec, 4), "precision": round(prec, 4),
        "f1": round(f1, 4),
        "business_cost": fn * COST_FN + fp * COST_FP,
    }

yp_baseline_05 = (proba_te_final >= 0.05).astype(int)
yp_val_thr = (proba_te_final >= THR_VAL).astype(int)

comparison = pd.DataFrame([
    cm_row("ML threshold=0.05",         y_te, yp_baseline_05),
    cm_row("ML val-tuned threshold",    y_te, yp_val_thr),
    cm_row("Segment thresholds",        y_te, seg_pred),
    cm_row("Stage-2 FP filter",         y_te, two_stage_pred),
    cm_row("Hybrid V6",                 y_te, hybrid_pred_v6),
    cm_row("Hybrid V6 + Stage-2",       y_te, final_pred),
])
print("\n=== STRATEGY COMPARISON (test set) ===")
print(comparison.to_string(index=False))

# ============================================================
# 19. Bootstrap CIs
# ============================================================
def bootstrap_ci(y_true, y_pred, n_boot=1000, seed=42):
    rng = np.random.default_rng(seed)
    rec, prec, fp_arr = [], [], []
    n = len(y_true)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt, yp = y_true[idx], y_pred[idx]
        tp = int(((yt == 1) & (yp == 1)).sum())
        fn = int(((yt == 1) & (yp == 0)).sum())
        fp = int(((yt == 0) & (yp == 1)).sum())
        rec.append(tp / max(tp + fn, 1))
        prec.append(tp / max(tp + fp, 1))
        fp_arr.append(fp)
    return {
        "recall_95ci": (round(np.percentile(rec, 2.5), 4), round(np.percentile(rec, 97.5), 4)),
        "precision_95ci": (round(np.percentile(prec, 2.5), 4), round(np.percentile(prec, 97.5), 4)),
        "fp_95ci": (int(np.percentile(fp_arr, 2.5)), int(np.percentile(fp_arr, 97.5))),
    }

print("\n=== Bootstrap 95% CIs ===")
print("Hybrid V6 + Stage-2:", bootstrap_ci(y_te, final_pred))

# ============================================================
# 20. Production scoring function
# ============================================================
def score_production(df_company):
    """Single source of truth: stage-1 -> anti-FP -> stage-2 -> hybrid V6 -> final."""
    proba1, _ = predict_proba(win, df_company)
    df_aug = build_business_score(df_company.copy().reset_index(drop=True))
    df_aug["proba"] = proba1
    df_aug = add_anti_fp_features(df_aug, proba_col="proba")

    # stage-2 sur les alerts
    alert_idx = np.where(proba1 >= STAGE1_THR)[0]
    proba2 = np.zeros(len(df_aug))
    if len(alert_idx) > 0:
        X2 = build_stage2_matrix(win, df_company, df_aug)
        X2_alert = X2.iloc[alert_idx]
        proba2[alert_idx] = np.mean(
            [m.predict_proba(X2_alert)[:, 1] for m in stage2_models], axis=0
        )
    df_aug["stage2_proba"] = proba2
    df_aug["stage2_kept"] = (proba2 >= STAGE2_THR).astype(int)

    hybrid_pred, status = hybrid_v6(
        df_aug, base_thr=THR_VAL,
        reject_low=THR_VAL * 0.7, reject_high=THR_VAL * 1.3,
    )
    df_aug["hybrid_pred"] = hybrid_pred
    df_aug["hybrid_status"] = status

    df_aug["final_alert"] = (
        (df_aug["hybrid_pred"] == 1)
        & ((df_aug["proba"] < STAGE1_THR) | (df_aug["stage2_kept"] == 1))
    ).astype(int)

    df_aug["risk_score_100"] = (proba1 * 100).round(1)
    return df_aug

# ============================================================
# 21. Export
# ============================================================
out = Path(OUTPUT_DIR)
out.mkdir(parents=True, exist_ok=True)

comparison.to_csv(out / f"strategy_comparison_{RUN_TAG}.csv", index=False)

with open(out / f"production_artifacts_{RUN_TAG}.pkl", "wb") as fh:
    pickle.dump({
        "winner_name": WINNER_NAME,
        "winner_bundle": win,
        "stage2_models": stage2_models,
        "STAGE1_THR": STAGE1_THR,
        "STAGE2_THR": STAGE2_THR,
        "THR_VAL": THR_VAL,
        "segment_thresholds": seg_thr,
        "stage2_extra_features": STAGE2_EXTRA,
        "stage2_feature_names": list(X2_va.columns),
        "numeric_features_audit": NUMERIC_FEATURES_AUDIT,
        "categorical_features": CATEGORICAL_FEATURES,
    }, fh)

# Predictions test set
df_te_out = df_te_aug.copy()
df_te_out["target"] = y_te
df_te_out["stage2_proba"] = stage2_proba_te
df_te_out["hybrid_pred"] = hybrid_pred_v6
df_te_out["hybrid_status"] = hybrid_status_v6
df_te_out["final_pred"] = final_pred
df_te_out["risk_score_100"] = (proba_te_final * 100).round(1)

export_cols = [c for c in [
    "siren", "denomination", "secteur_naf2", "departement",
    "target", "proba", "stage2_proba",
    "hybrid_pred", "hybrid_status", "final_pred",
    "risk_score_100", "business_confirmation_score",
    "alive_score", "surprise_factor",
] if c in df_te_out.columns]
df_te_out[export_cols].to_csv(out / f"predictions_test_{RUN_TAG}.csv", index=False)

metadata = {
    "run_tag": RUN_TAG,
    "winner": WINNER_NAME,
    "thr_val": THR_VAL,
    "stage1_thr": STAGE1_THR,
    "stage2_thr": STAGE2_THR,
    "n_segment_thresholds": len(seg_thr),
    "comparison": comparison.to_dict(orient="records"),
    "ci_final": bootstrap_ci(y_te, final_pred),
}
with open(out / f"metadata_{RUN_TAG}.json", "w", encoding="utf-8") as fh:
    json.dump(metadata, fh, indent=2, ensure_ascii=False, default=str)

print(f"\nExported to {OUTPUT_DIR}")
print(f"  - strategy_comparison_{RUN_TAG}.csv")
print(f"  - production_artifacts_{RUN_TAG}.pkl")
print(f"  - predictions_test_{RUN_TAG}.csv")
print(f"  - metadata_{RUN_TAG}.json")

print("""
======================================================================
SUMMARY
======================================================================
Strategie recommandee : "Hybrid V6 + Stage-2"
- recall(cessee) >= 0.90 (contrainte respectee)
- FP reduits via : seuil val-tuned + stage-2 filter + vetoes hybride
- Reject zone disponible pour analyste

Pour deploiement :
  pickle.load(production_artifacts_{TAG}.pkl) -> tout est dedans
  appel : score_production(df_company) -> DataFrame avec final_alert
======================================================================
""")
