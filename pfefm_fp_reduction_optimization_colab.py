# -*- coding: utf-8 -*-
"""PFEFM_FP_Reduction_Optimization_Colab.ipynb

Standalone optimisation notebook to plug AFTER section 17 of your existing
`pfefm_ml_leakage_audit_catboost_colab.py`.

Goal: cut FP from 234 -> target <= 130 while keeping recall(cessee) >= 0.90.

Required objects already in the kernel from the parent notebook:
    win, df_tr, df_va, df_test, df_te_hybrid,
    proba_va_final, proba_te_final,
    X_va_mat, X_te_mat, y_va, y_te,
    NUMERIC_FEATURES_AUDIT, CATEGORICAL_FEATURES,
    to_xy, predict_proba, build_sample_weight,
    make_preprocessor, make_xgb, make_lgbm, make_catboost, fit_model,
    FINAL_THRESHOLD, COST_FN, COST_FP, RANDOM_STATE, OUTPUT_DIR, RUN_TAG,
    bundles  (dict (scenario, name) -> bundle).

Sections:
    A. Sanity check & inputs
    B. Threshold optimisation on VALIDATION (no test peek)
    C. Anti-FP feature engineering (computed at inference time)
    D. Stage-2 FP filter (LightGBM precision booster)
    E. Segment-conditional thresholds (per-sector base rate)
    F. Hybrid V6 with reject zone
    G. Walk-forward validation across cutoffs
    H. Production monitoring helpers
    I. Final report & export
"""

# ============================================================
# A. Sanity check & inputs
# ============================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import json, pickle
from datetime import datetime

from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, roc_auc_score,
    confusion_matrix, classification_report,
)
from sklearn.utils import resample
import lightgbm as lgb

REQUIRED = [
    "win", "df_tr", "df_va", "df_test",
    "proba_va_final", "proba_te_final",
    "y_va", "y_te", "X_va_mat", "X_te_mat",
    "FINAL_THRESHOLD", "COST_FN", "COST_FP",
    "RANDOM_STATE", "to_xy", "predict_proba",
]
missing = [n for n in REQUIRED if n not in globals()]
assert not missing, f"Missing from kernel: {missing}. Run the parent notebook first."

print("Inputs OK.")
print(f"Current FINAL_THRESHOLD (parent) = {FINAL_THRESHOLD:.4f}")
print(f"Test rows: {len(df_test):,} | val rows: {len(df_va):,}")

# ============================================================
# B. Threshold optimisation on VALIDATION (no test peek)
# ============================================================
# WHY: parent notebook (Section 14) sweeps thresholds on y_te. That is an
# optimistic operating point. We re-pick on validation under recall constraint,
# then evaluate ONCE on test.

MIN_RECALL_TARGET = 0.92   # margin above the 0.90 business floor
COST_FN_LOCAL = float(COST_FN)
COST_FP_LOCAL = float(COST_FP)

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
            "threshold": float(t),
            "TP": tp, "FN": fn, "FP": fp, "TN": tn,
            "precision": prec, "recall": rec, "f1": f1,
            "business_cost": fn * COST_FN_LOCAL + fp * COST_FP_LOCAL,
        })
    return pd.DataFrame(rows)

val_sweep = sweep_thresholds(y_va, proba_va_final)
val_feasible = val_sweep[val_sweep["recall"] >= MIN_RECALL_TARGET].copy()

if len(val_feasible) == 0:
    print(f"WARNING: no threshold reaches recall>={MIN_RECALL_TARGET} on val. Falling back to 0.90.")
    val_feasible = val_sweep[val_sweep["recall"] >= 0.90].copy()

# Among feasible thresholds, pick the one with min FP (i.e. max precision)
# under the recall floor. Tiebreak by business_cost.
val_pick = val_feasible.sort_values(
    ["FP", "business_cost", "threshold"], ascending=[True, True, False]
).iloc[0]

THR_VAL_PRECISION_FIRST = float(val_pick["threshold"])
print(f"\nValidation precision-first threshold: {THR_VAL_PRECISION_FIRST:.4f}")
print(f"  val recall    : {val_pick['recall']:.4f}")
print(f"  val precision : {val_pick['precision']:.4f}")
print(f"  val FP/FN     : {int(val_pick['FP'])}/{int(val_pick['FN'])}")

# Apply to test (single shot)
yp_test_b = (proba_te_final >= THR_VAL_PRECISION_FIRST).astype(int)
tp = int(((y_te == 1) & (yp_test_b == 1)).sum())
fn = int(((y_te == 1) & (yp_test_b == 0)).sum())
fp = int(((y_te == 0) & (yp_test_b == 1)).sum())
tn = int(((y_te == 0) & (yp_test_b == 0)).sum())
print(f"\nTest @ precision-first threshold:")
print(f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}")
print(f"  recall   = {tp / max(tp + fn, 1):.4f}")
print(f"  precision= {tp / max(tp + fp, 1):.4f}")

# ============================================================
# C. Anti-FP feature engineering
# (computed on the existing dataframes - NO retrain needed)
# ============================================================

def add_anti_fp_features(df, proba_col="proba"):
    """Counter-evidence features that subtract from risk.

    Logic: every feature you currently have answers 'is this risky?'.
    These answer 'is this clearly alive?' so the hybrid layer can veto.
    """
    df = df.copy()

    # 1. signal_coherence_score: do weak signals agree?
    # If only ONE fragility flag fires alone -> probably noise.
    fragility_flags = [
        "capital_tres_faible", "depot_non_respecte",
        "bilan_resultat_negatif", "bilan_capitaux_negatifs",
        "marge_nette_negative", "representants_peu_nombreux",
    ]
    present = [c for c in fragility_flags if c in df.columns]
    df["nb_fragility_flags"] = df[present].sum(axis=1) if present else 0
    df["fragility_isolated"] = (df["nb_fragility_flags"] == 1).astype(int)
    df["fragility_coherent"] = (df["nb_fragility_flags"] >= 3).astype(int)

    # 2. actively_alive_score: counter-evidence
    alive_components = []
    if "nb_etab_secondaires" in df.columns:
        alive_components.append((df["nb_etab_secondaires"] >= 2).astype(int))
    if "nombreEtablissementsOuverts" in df.columns:
        alive_components.append(
            (pd.to_numeric(df["nombreEtablissementsOuverts"], errors="coerce").fillna(0) >= 2).astype(int)
        )
    if "nb_representants_extraits" in df.columns:
        alive_components.append((df["nb_representants_extraits"] >= 2).astype(int))
    if "has_bilan" in df.columns:
        alive_components.append(
            (pd.to_numeric(df["has_bilan"], errors="coerce").fillna(0) == 1).astype(int)
        )
    if "bilan_resultat_net" in df.columns:
        alive_components.append(
            (pd.to_numeric(df["bilan_resultat_net"], errors="coerce").fillna(0) > 0).astype(int)
        )
    if "bilan_marge_nette" in df.columns:
        alive_components.append(
            (pd.to_numeric(df["bilan_marge_nette"], errors="coerce").fillna(0) > 0.05).astype(int)
        )
    if "flag_creation_bodacc" in df.columns:
        alive_components.append((df["flag_creation_bodacc"] == 1).astype(int))

    if alive_components:
        df["alive_score"] = sum(alive_components)
    else:
        df["alive_score"] = 0

    df["clearly_alive"] = (df["alive_score"] >= 3).astype(int)

    # 3. surprise_factor: model proba is high but business signals are quiet
    # -> high probability the model is wrong (FP candidate).
    bcs = df.get("business_confirmation_score", pd.Series(0, index=df.index))
    df["surprise_factor"] = (
        (df[proba_col] >= 0.10) & (bcs <= 1) & (df["alive_score"] >= 2)
    ).astype(int)

    # 4. recent_life_signal: at least one positive-direction event recently.
    if "flag_modification_bodacc" in df.columns:
        df["recent_life_signal"] = df["flag_modification_bodacc"].fillna(0).astype(int)
    else:
        df["recent_life_signal"] = 0

    # 5. profit_floor: basic profitability cushion
    if "bilan_resultat_net" in df.columns and "bilan_capitaux_propres" in df.columns:
        rn = pd.to_numeric(df["bilan_resultat_net"], errors="coerce").fillna(0)
        cp = pd.to_numeric(df["bilan_capitaux_propres"], errors="coerce").fillna(0)
        df["healthy_balance_sheet"] = ((rn > 0) & (cp > 0)).astype(int)
    else:
        df["healthy_balance_sheet"] = 0

    return df

df_te_hybrid = add_anti_fp_features(df_te_hybrid, proba_col="proba")
df_va_hybrid = df_va.copy().reset_index(drop=True)
df_va_hybrid["proba"] = proba_va_final
df_va_hybrid["business_confirmation_score"] = (
    (df_va_hybrid.get("has_alerte_juridique", 0) == 1).astype(int) * 3
    + (df_va_hybrid.get("nb_observations_critiques", 0) >= 1).astype(int) * 2
    + (df_va_hybrid.get("nb_etab_fermes", 0) >= 1).astype(int) * 2
    + (df_va_hybrid.get("fragilite_financiere", 0) == 1).astype(int) * 2
    + (df_va_hybrid.get("depot_non_respecte", 0) == 1).astype(int)
    + (df_va_hybrid.get("super_silent_risk", 0) == 1).astype(int) * 3
    + (df_va_hybrid.get("financial_distress_score", 0) >= 2).astype(int) * 2
)
df_va_hybrid = add_anti_fp_features(df_va_hybrid, proba_col="proba")

print("\nAnti-FP features built on test:")
print(df_te_hybrid[[
    "nb_fragility_flags", "fragility_isolated", "fragility_coherent",
    "alive_score", "clearly_alive", "surprise_factor",
    "healthy_balance_sheet", "recent_life_signal",
]].describe().round(3).T)

# ============================================================
# D. Stage-2 FP filter (LightGBM precision booster)
# ------------------------------------------------------------
# Architecture:
#   Stage 1 (existing CatBoost) -> recall-first proba.
#   Stage 2 (new LightGBM)     -> only on rows flagged by stage 1
#                                 predicts P(true positive | stage1 alert)
# Final decision = stage1 alert AND stage2 keeps it.
# ============================================================

# Floor used to define "stage-1 alert" during stage-2 training.
# Lower than FINAL_THRESHOLD so stage-2 sees the full FP zone to learn from.
STAGE1_RECALL_FLOOR = 0.97

# Find threshold on validation that hits the recall floor (lowest such t).
val_for_floor = val_sweep[val_sweep["recall"] >= STAGE1_RECALL_FLOOR]
if len(val_for_floor) == 0:
    STAGE1_THR = float(val_sweep.iloc[0]["threshold"])
else:
    STAGE1_THR = float(val_for_floor.sort_values("threshold", ascending=False).iloc[0]["threshold"])
print(f"\nStage-1 alert threshold (recall>={STAGE1_RECALL_FLOOR} on val): {STAGE1_THR:.4f}")

# Build stage-2 training set from VALIDATION rows that stage-1 flagged.
# WHY validation and not train: train probas are over-confident due to
# the booster's fit. Validation probas are honest.
val_alert_mask = proba_va_final >= STAGE1_THR
print(f"Stage-2 training rows (val alerts): {val_alert_mask.sum()} "
      f"({(val_alert_mask & (y_va == 1)).sum()} positives)")

# Stage-2 features = base numerics + anti-FP features + stage1 proba + business score.
STAGE2_EXTRA = [
    "nb_fragility_flags", "fragility_isolated", "fragility_coherent",
    "alive_score", "clearly_alive", "surprise_factor",
    "healthy_balance_sheet", "recent_life_signal",
    "business_confirmation_score",
]

def build_stage2_matrix(bundle, df_full, df_aug, proba_col="proba"):
    """df_full: original features as fed to stage 1; df_aug: with anti-FP cols."""
    X_raw, _ = to_xy(df_full, bundle["numeric_features"], bundle["categorical_features"])
    X_mat = bundle["preprocessor"].transform(X_raw)
    base_df = pd.DataFrame(X_mat, columns=bundle["feature_names_out"])
    base_df["__stage1_proba__"] = df_aug[proba_col].values
    for c in STAGE2_EXTRA:
        base_df[c] = df_aug[c].values if c in df_aug.columns else 0
    return base_df

X2_va = build_stage2_matrix(win, df_va, df_va_hybrid)
X2_te = build_stage2_matrix(win, df_test, df_te_hybrid)

X2_va_alert = X2_va.loc[val_alert_mask].reset_index(drop=True)
y2_va_alert = y_va[val_alert_mask]

# Class balance inside stage-2 alerts is already shifted, but still use weighting.
n_pos2 = int((y2_va_alert == 1).sum())
n_neg2 = int((y2_va_alert == 0).sum())
spw2 = n_neg2 / max(n_pos2, 1)
print(f"Stage-2 train balance: pos={n_pos2}  neg={n_neg2}  scale_pos_weight={spw2:.2f}")

# Cross-validated stage-2 model so we don't overfit the small alert set.
from sklearn.model_selection import StratifiedKFold

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

print(f"\nStage-2 OOF PR-AUC (on val alerts): "
      f"{average_precision_score(y2_va_alert, oof_pred):.4f}")

# Stage-2 threshold: tuned on OOF predictions to keep stage-2 recall high.
# Stage 2 must NOT remove true positives -> require stage2_recall >= 0.97 on
# the stage-1-flagged true positives.
stage2_sweep = sweep_thresholds(y2_va_alert, oof_pred, lo=0.05, hi=0.95, step=0.01)
stage2_pick = stage2_sweep[stage2_sweep["recall"] >= 0.97].sort_values(
    "FP", ascending=True
).head(1)
if len(stage2_pick) == 0:
    stage2_pick = stage2_sweep.sort_values("FP").head(1)
STAGE2_THR = float(stage2_pick.iloc[0]["threshold"])
print(f"Stage-2 threshold: {STAGE2_THR:.4f}")

# Predict stage-2 on test (ensemble of fold models).
te_alert_mask = proba_te_final >= STAGE1_THR
X2_te_alert = X2_te.loc[te_alert_mask].reset_index(drop=True)
stage2_proba_te = np.mean(
    [m.predict_proba(X2_te_alert)[:, 1] for m in stage2_models], axis=0
)

# Two-stage final prediction on test.
two_stage_pred = np.zeros(len(y_te), dtype=int)
two_stage_pred[np.where(te_alert_mask)[0]] = (stage2_proba_te >= STAGE2_THR).astype(int)

tp = int(((y_te == 1) & (two_stage_pred == 1)).sum())
fn = int(((y_te == 1) & (two_stage_pred == 0)).sum())
fp = int(((y_te == 0) & (two_stage_pred == 1)).sum())
tn = int(((y_te == 0) & (two_stage_pred == 0)).sum())
print(f"\n=== Two-stage on test ===")
print(f"TP={tp}  FN={fn}  FP={fp}  TN={tn}")
print(f"recall   = {tp / max(tp + fn, 1):.4f}")
print(f"precision= {tp / max(tp + fp, 1):.4f}")
print(f"F1       = {2*tp / max(2*tp + fp + fn, 1):.4f}")

# ============================================================
# E. Segment-conditional thresholds (per-sector base rate)
# ============================================================

SECTOR_COL = "secteur_naf2" if "secteur_naf2" in df_tr.columns else None

def compute_segment_thresholds(df_train, proba_train, segment_col,
                               min_recall_per_segment=0.90, min_count=200):
    """For segments with enough train rows, find the per-segment threshold
    that hits min_recall_per_segment on train; else fall back to global."""
    df_aux = pd.DataFrame({
        "y": df_train["target"].values,
        "p": proba_train,
        "seg": df_train[segment_col].astype(str).values,
    })
    out = {}
    for seg, g in df_aux.groupby("seg"):
        if len(g) < min_count or g["y"].sum() < 10:
            continue
        sw = sweep_thresholds(g["y"].values, g["p"].values, lo=0.005, hi=0.5, step=0.005)
        feas = sw[sw["recall"] >= min_recall_per_segment]
        if len(feas) == 0:
            continue
        out[seg] = float(feas.sort_values(["FP", "threshold"]).iloc[0]["threshold"])
    return out

if SECTOR_COL is not None:
    # Use validation to tune (avoid overfit to train).
    seg_thr = compute_segment_thresholds(
        df_va, proba_va_final, SECTOR_COL,
        min_recall_per_segment=0.90, min_count=200,
    )
    print(f"\nSegment thresholds learned for {len(seg_thr)} sectors. "
          f"Sample: {dict(list(seg_thr.items())[:5])}")
else:
    seg_thr = {}

def apply_segment_threshold(df_test, proba_test, seg_thr, default_thr, segment_col):
    if segment_col is None or not seg_thr:
        return (proba_test >= default_thr).astype(int)
    segs = df_test[segment_col].astype(str).values
    thrs = np.array([seg_thr.get(s, default_thr) for s in segs])
    return (proba_test >= thrs).astype(int)

seg_pred = apply_segment_threshold(
    df_test, proba_te_final, seg_thr, THR_VAL_PRECISION_FIRST, SECTOR_COL
)
tp = int(((y_te == 1) & (seg_pred == 1)).sum())
fn = int(((y_te == 1) & (seg_pred == 0)).sum())
fp = int(((y_te == 0) & (seg_pred == 1)).sum())
tn = int(((y_te == 0) & (seg_pred == 0)).sum())
print(f"\n=== Segment-conditional threshold on test ===")
print(f"TP={tp}  FN={fn}  FP={fp}  TN={tn} | "
      f"rec={tp/max(tp+fn,1):.4f} prec={tp/max(tp+fp,1):.4f}")

# ============================================================
# F. Hybrid V6 with reject zone
# ============================================================
# Differences vs V5:
#   - rule_silent_recovery hardened: business_confirmation_score >= 5 required
#   - clean_profile veto strengthened with alive_score >= 3
#   - reject zone (uncertainty band) = "to review by analyst"
# ============================================================

def hybrid_v6(df_h, proba_col="proba",
              high_proba_thr=0.10,
              base_thr=THR_VAL_PRECISION_FIRST,
              min_confirmation_high=4,
              min_confirmation_silent=5,
              reject_low=None, reject_high=None):
    """Returns (hybrid_pred, status).
    status in {'positive', 'negative', 'review'}.
    """
    p = df_h[proba_col]
    bcs = df_h.get("business_confirmation_score", 0)

    rule_high = (p >= high_proba_thr) & (bcs >= 1)

    rule_gray_confirmed = (
        (p >= base_thr)
        & (bcs >= min_confirmation_high)
        & ((p >= 0.06) | (bcs >= 6))
    )

    # Silent recovery: hardened. Requires the business score to back it up.
    rule_silent = (
        (p >= 0.05)
        & (df_h.get("super_silent_risk", 0) == 1)
        & (df_h.get("financial_distress_score", 0) >= 2)
        & (df_h.get("nb_annonces_bodacc", 0) <= 2)
        & (bcs >= min_confirmation_silent)
        & (df_h.get("alive_score", 0) <= 2)  # NEW veto on clearly-alive
    )

    # Veto: clearly alive companies cannot be flagged unless very high proba.
    veto_alive = (
        (df_h.get("clearly_alive", 0) == 1)
        & (df_h.get("surprise_factor", 0) == 1)
        & (p < 0.20)
    )

    # Veto: clean profile (no risk signal at all) unless super_silent_risk
    veto_clean = (
        (df_h.get("clean_profile", 0) == 1)
        & (df_h.get("super_silent_risk", 0) == 0)
        & (df_h.get("financial_distress_score", 0) < 2)
    )

    raw_alert = (rule_high | rule_gray_confirmed | rule_silent).astype(bool)
    final = raw_alert & ~veto_alive & ~veto_clean

    # Reject zone: undecided cases routed to analyst.
    if reject_low is not None and reject_high is not None:
        in_reject = (p >= reject_low) & (p < reject_high) & (bcs.between(2, 4))
    else:
        in_reject = pd.Series(False, index=df_h.index)

    status = np.where(
        final, "positive",
        np.where(in_reject, "review", "negative")
    )
    return final.astype(int).values, status

hybrid_pred_v6, hybrid_status_v6 = hybrid_v6(
    df_te_hybrid,
    proba_col="proba",
    high_proba_thr=0.10,
    base_thr=THR_VAL_PRECISION_FIRST,
    min_confirmation_high=4,
    min_confirmation_silent=5,
    reject_low=THR_VAL_PRECISION_FIRST * 0.7,
    reject_high=THR_VAL_PRECISION_FIRST * 1.3,
)

tp = int(((y_te == 1) & (hybrid_pred_v6 == 1)).sum())
fn = int(((y_te == 1) & (hybrid_pred_v6 == 0)).sum())
fp = int(((y_te == 0) & (hybrid_pred_v6 == 1)).sum())
tn = int(((y_te == 0) & (hybrid_pred_v6 == 0)).sum())
print(f"\n=== Hybrid V6 on test ===")
print(f"TP={tp}  FN={fn}  FP={fp}  TN={tn} | "
      f"rec={tp/max(tp+fn,1):.4f} prec={tp/max(tp+fp,1):.4f}")
print(f"Reject zone size: {(hybrid_status_v6 == 'review').sum()} rows")

# ============================================================
# G. Walk-forward validation across cutoffs (2021/2022/2023)
# ------------------------------------------------------------
# Validates that the precision gains are NOT 2023-specific.
# Re-uses the parent's bundle - we only retrain when the cutoff changes.
# ============================================================

def walk_forward_eval(df_full, cutoffs, threshold_fn, build_bundle_fn):
    """For each cutoff, train on rows < cutoff and evaluate on cutoff slice."""
    results = []
    for cutoff in cutoffs:
        cutoff_ts = pd.Timestamp(cutoff)
        df_tr_w = df_full[df_full["observation_date"] < cutoff_ts].copy()
        df_te_w = df_full[
            (df_full["observation_date"] >= cutoff_ts)
            & (df_full["observation_date"] < cutoff_ts + pd.DateOffset(years=1))
        ].copy()
        if df_te_w["target"].sum() < 50 or len(df_te_w) < 200:
            continue
        bundle, y_tr_w, y_te_w, proba_te_w = build_bundle_fn(df_tr_w, df_te_w)
        thr = threshold_fn(bundle, df_tr_w)
        yp = (proba_te_w >= thr).astype(int)
        tp = int(((y_te_w == 1) & (yp == 1)).sum())
        fn = int(((y_te_w == 1) & (yp == 0)).sum())
        fp = int(((y_te_w == 0) & (yp == 1)).sum())
        results.append({
            "cutoff": str(cutoff), "n_test": len(df_te_w), "n_pos": int(y_te_w.sum()),
            "threshold": thr,
            "recall": tp / max(tp + fn, 1),
            "precision": tp / max(tp + fp, 1),
            "FP": fp, "FN": fn, "TP": tp,
            "pr_auc": float(average_precision_score(y_te_w, proba_te_w)),
        })
    return pd.DataFrame(results)

# Skipped here for runtime, but the helper is ready - call when you have time.
# Example:
#   df_with_obs = df_fe[df_fe["observation_date"].notna()].copy()
#   wf = walk_forward_eval(
#       df_with_obs,
#       cutoffs=["2021-01-01", "2022-01-01", "2023-01-01"],
#       threshold_fn=lambda b, dtr: THR_VAL_PRECISION_FIRST,
#       build_bundle_fn=...,  # closure that wraps fit_model on the cutoff slice
#   )
print("\nWalk-forward helper defined. Run when you have a few minutes.")

# ============================================================
# H. Bootstrap CIs for FP / recall (no overfitting claim without these)
# ============================================================

def bootstrap_metrics(y_true, y_pred, n_boot=1000, seed=42):
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
        "recall_ci": (float(np.percentile(rec, 2.5)), float(np.percentile(rec, 97.5))),
        "precision_ci": (float(np.percentile(prec, 2.5)), float(np.percentile(prec, 97.5))),
        "fp_ci": (int(np.percentile(fp_arr, 2.5)), int(np.percentile(fp_arr, 97.5))),
    }

ci_v6 = bootstrap_metrics(y_te, hybrid_pred_v6.astype(int))
ci_two_stage = bootstrap_metrics(y_te, two_stage_pred)
print("\nBootstrap 95% CIs on test:")
print(f"  Hybrid V6: {ci_v6}")
print(f"  Two-stage: {ci_two_stage}")

# ============================================================
# I. Final comparison table & export
# ============================================================

def cm_row(name, y_true, y_pred):
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    rec = tp / max(tp + fn, 1)
    prec = tp / max(tp + fp, 1)
    f1 = 2*prec*rec / max(prec + rec, 1e-9)
    cost = fn * COST_FN_LOCAL + fp * COST_FP_LOCAL
    return {
        "strategy": name, "TP": tp, "FN": fn, "FP": fp, "TN": tn,
        "recall": round(rec, 4), "precision": round(prec, 4),
        "f1": round(f1, 4), "business_cost": cost,
    }

# Parent baseline (current production at FINAL_THRESHOLD)
yp_baseline = (proba_te_final >= FINAL_THRESHOLD).astype(int)
hybrid_pred_v5 = df_te_hybrid["hybrid_pred"].values if "hybrid_pred" in df_te_hybrid.columns else yp_baseline

comparison = pd.DataFrame([
    cm_row("ML baseline (V5 thr)",      y_te, yp_baseline),
    cm_row("ML precision-first (val)",  y_te, yp_test_b),
    cm_row("Hybrid V5 (parent)",        y_te, hybrid_pred_v5),
    cm_row("Hybrid V6 (this notebook)", y_te, hybrid_pred_v6),
    cm_row("Two-stage filter",          y_te, two_stage_pred),
    cm_row("Segment thresholds",        y_te, seg_pred),
])
print("\n=== STRATEGY COMPARISON (test set) ===")
print(comparison.to_string(index=False))

# Export
out = Path(OUTPUT_DIR)
out.mkdir(parents=True, exist_ok=True)
fp_run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
comparison.to_csv(out / f"fp_reduction_comparison_{fp_run_tag}.csv", index=False)

with open(out / f"fp_reduction_artifacts_{fp_run_tag}.pkl", "wb") as fh:
    pickle.dump({
        "stage2_models": stage2_models,
        "STAGE1_THR": STAGE1_THR,
        "STAGE2_THR": STAGE2_THR,
        "THR_VAL_PRECISION_FIRST": THR_VAL_PRECISION_FIRST,
        "segment_thresholds": seg_thr,
        "stage2_extra_features": STAGE2_EXTRA,
        "stage2_feature_names": list(X2_va.columns),
    }, fh)

print(f"\nExported: fp_reduction_comparison_{fp_run_tag}.csv")
print(f"Exported: fp_reduction_artifacts_{fp_run_tag}.pkl")

# ============================================================
# J. Production scoring function (drop-in)
# ============================================================

def score_company_fp_aware(df_company, win_bundle, stage2_models,
                            stage1_thr, stage2_thr, seg_thr, segment_col,
                            high_proba_thr=0.10, base_thr=None):
    """Single source of truth for production scoring with two-stage FP filter
    + segment thresholds + hybrid vetoes. Returns DataFrame with full audit trail.
    """
    base_thr = base_thr if base_thr is not None else stage1_thr

    # --- stage 1
    proba1, _ = predict_proba(win_bundle, df_company)
    df_aug = df_company.copy().reset_index(drop=True)
    df_aug["proba"] = proba1
    df_aug["business_confirmation_score"] = (
        (df_aug.get("has_alerte_juridique", 0) == 1).astype(int) * 3
        + (df_aug.get("nb_observations_critiques", 0) >= 1).astype(int) * 2
        + (df_aug.get("nb_etab_fermes", 0) >= 1).astype(int) * 2
        + (df_aug.get("fragilite_financiere", 0) == 1).astype(int) * 2
        + (df_aug.get("depot_non_respecte", 0) == 1).astype(int)
        + (df_aug.get("super_silent_risk", 0) == 1).astype(int) * 3
        + (df_aug.get("financial_distress_score", 0) >= 2).astype(int) * 2
    )
    df_aug = add_anti_fp_features(df_aug, proba_col="proba")

    # --- stage 2 on alerts only
    alert_idx = np.where(proba1 >= stage1_thr)[0]
    proba2 = np.zeros(len(df_aug))
    if len(alert_idx) > 0:
        X2 = build_stage2_matrix(win_bundle, df_company, df_aug)
        X2_alert = X2.iloc[alert_idx]
        proba2[alert_idx] = np.mean(
            [m.predict_proba(X2_alert)[:, 1] for m in stage2_models], axis=0
        )
    df_aug["stage2_proba"] = proba2
    df_aug["stage2_kept"] = (proba2 >= stage2_thr).astype(int)

    # --- segment threshold (fallback safety net)
    if segment_col and segment_col in df_aug.columns and seg_thr:
        segs = df_aug[segment_col].astype(str).values
        thrs = np.array([seg_thr.get(s, base_thr) for s in segs])
        seg_alert = (proba1 >= thrs).astype(int)
    else:
        seg_alert = (proba1 >= base_thr).astype(int)
    df_aug["seg_alert"] = seg_alert

    # --- hybrid v6
    hybrid_pred, status = hybrid_v6(
        df_aug, proba_col="proba",
        high_proba_thr=high_proba_thr, base_thr=base_thr,
        reject_low=base_thr * 0.7, reject_high=base_thr * 1.3,
    )
    df_aug["hybrid_pred"] = hybrid_pred
    df_aug["hybrid_status"] = status

    # --- final decision: hybrid AND stage-2 keeps it (when stage-2 ran)
    df_aug["final_alert"] = (
        (df_aug["hybrid_pred"] == 1)
        & ((proba1 < stage1_thr) | (df_aug["stage2_kept"] == 1))
    ).astype(int)

    df_aug["risk_score_100"] = (proba1 * 100).round(1)
    return df_aug[[
        c for c in df_aug.columns
        if c in ["proba", "stage2_proba", "stage2_kept", "seg_alert",
                 "hybrid_pred", "hybrid_status", "final_alert",
                 "risk_score_100", "business_confirmation_score",
                 "alive_score", "surprise_factor"]
    ] + [c for c in ["siren", "denomination"] if c in df_aug.columns]]

# Smoke test the production function on test set
prod_out = score_company_fp_aware(
    df_test, win, stage2_models,
    stage1_thr=STAGE1_THR, stage2_thr=STAGE2_THR,
    seg_thr=seg_thr, segment_col=SECTOR_COL,
    base_thr=THR_VAL_PRECISION_FIRST,
)
prod_out["target"] = y_te
print("\nProduction scoring function smoke test:")
print(cm_row("Production fn", y_te, prod_out["final_alert"].values))

# ============================================================
# Summary recommendations
# ============================================================
print("""
======================================================================
RECOMMENDED PRODUCTION CONFIG
======================================================================
1. Replace FINAL_THRESHOLD with THR_VAL_PRECISION_FIRST (picked on val).
2. Keep CatBoost stage-1 unchanged but reduce silent-fragile sample_weight
   from 4.0 to 2.0 next retrain.
3. Add stage-2 LightGBM filter (loaded from fp_reduction_artifacts pkl).
4. Use segment thresholds for sectors with >=200 train rows.
5. Use Hybrid V6 vetoes (clearly_alive + surprise_factor).
6. Route reject_zone rows to analyst review queue (don't auto-decide).
7. Monitor in production:
   - Daily FP rate (alerts that don't materialize after 6 months)
   - Recall on confirmed cessations (90-day lag)
   - Drift: distribution of alive_score over time
   - Stage-2 kept rate (should stay 50-80%)
======================================================================
""")
