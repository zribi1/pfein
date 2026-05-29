"""V2 Layer 2 -- unsupervised anomaly detector (Isolation Forest).

Trains on V2 features *without using labels*. Labels are loaded only at
validation time to measure enrichment of high-anomaly rows in subsequent
risk events. Standard methodology in fraud / network anomaly detection.

Output per (siren, prediction_year):
- raw anomaly score (higher = more anomalous; we negate sklearn's
  decision_function so higher is bad, which matches user intuition)
- global percentile rank (vs all scored rows)
- peer-group percentile rank within NAF 2-digit prefix (e.g. all "47.xx"
  retail companies). The peer-group framing is what the action-taker
  product surfaces: "top 3% most anomalous *restaurants* in 2023" beats
  "top 3% most anomalous companies overall".

Validation contract: for each Phase 4 label (continuity, legal_distress,
radiation, financial_weakness -- filing_anomaly excluded since it's
demoted to a dormancy flag), compute lift at top-K% by anomaly score.
A useful detector should show lift >= 3 on at least one of the labels;
the roadmap acceptance criterion is lift >= 3 on all four.

CategoricalCardinalityCapper is duplicated from V1 / Phase 4 -- same
rationale (joblib portability, no V1 module dependency at load time).
But Isolation Forest needs *numeric* input, so categoricals are
OneHot-encoded with min_frequency=50 rather than left as pandas
Categorical.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("train_anomaly_detector_v2")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Labels used for *validation only*. filing_anomaly excluded -- per the
# 2026-05-25 pivot it's a dormancy flag, not a risk signal worth chasing.
VALIDATION_LABELS = (
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
)

# Same V1-observed degeneracies excluded as in Phase 4. The risk labels
# don't appear here because they live in a separate parquet and are NOT
# loaded for training -- only for validation, in a separate pass.
EXCLUDE_COLUMNS = {
    "siren",
    "prediction_date",
    "first_future_legal_event_date",
    "company_name",
    "has_confidential_financials",
    "formalities_count_all",
    "formalities_count_12m",
    "cessation_formalities_count_all",
    "latest_equity_ratio",
}

CATEGORICAL_COLUMNS = (
    "activity_code",
    "legal_category_code",
    "administrative_status_at_cutoff",
)


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    train_anomaly_detector(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        artifacts_dir=Path(args.artifacts_dir or settings.ML_ARTIFACTS_DIR) / "v2" / "anomaly_detector",
        train_start_year=args.train_start_year,
        train_end_year=args.train_end_year,
        test_year=args.test_year,
        max_rows=args.max_rows,
        n_estimators=args.n_estimators,
        contamination=args.contamination,
        random_state=args.random_state,
    )
    return 0


def train_anomaly_detector(
    *,
    data_lake_dir: Path,
    artifacts_dir: Path,
    train_start_year: int = 2017,
    train_end_year: int = 2022,
    test_year: int = 2023,
    max_rows: int | None = 2_000_000,
    n_estimators: int = 100,
    contamination: Any = "auto",
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit Isolation Forest on V2 features, score test_year, validate against labels.

    Returns metadata dict; also written to disk under artifacts_dir.
    """
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import IsolationForest
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    features_path = data_lake_dir / "features" / "company_year_features_v2"
    labels_path = data_lake_dir / "features" / "risk_labels_v2"
    if not _has_parquet(features_path):
        raise FileNotFoundError(f"missing V2 features parquet under {features_path}")
    if not _has_parquet(labels_path):
        raise FileNotFoundError(f"missing V2 labels parquet under {labels_path}")

    # -- 1. Load TRAIN features (no labels). ------------------------------
    logger.info("loading train features years=[%d,%d] max_rows=%s",
                train_start_year, train_end_year, max_rows)
    train_df = _load_features(
        features_path=features_path,
        year_lo=train_start_year,
        year_hi=train_end_year,
        max_rows=max_rows,
    )
    logger.info("train rows=%d", len(train_df))

    # -- 2. Load TEST features. -------------------------------------------
    logger.info("loading test features year=%d (full population, no sampling)", test_year)
    test_df = _load_features(
        features_path=features_path,
        year_lo=test_year,
        year_hi=test_year,
        max_rows=None,
    )
    logger.info("test rows=%d", len(test_df))

    # -- 3. Feature selection. --------------------------------------------
    feature_cols = [
        c for c in train_df.columns
        if c not in EXCLUDE_COLUMNS and c != "prediction_year"
    ]
    # Some "feature" columns are useless to the model but kept in the
    # dataframe for bookkeeping (prediction_year is dropped above; siren
    # already in EXCLUDE_COLUMNS). Ensure test_df has the same columns
    # (it should, since same parquet schema).
    cat_cols = [c for c in CATEGORICAL_COLUMNS if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    # HGB-style: cast booleans to float so the imputer treats them as numeric.
    for c in num_cols:
        if pd.api.types.is_bool_dtype(train_df[c]):
            train_df[c] = train_df[c].astype(float)
            test_df[c] = test_df[c].astype(float)

    logger.info("feature_count=%d (%d num, %d cat)",
                len(feature_cols), len(num_cols), len(cat_cols))

    # -- 4. Pipeline (preproc -> Isolation Forest). -----------------------
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale",  StandardScaler()),
            ]), num_cols),
            ("cat", Pipeline([
                ("impute", SimpleImputer(strategy="constant", fill_value="__missing__")),
                # min_frequency=50 collapses the long tail of activity_code
                # (~922 NAF codes -- without this we'd have 1000+ dummy cols).
                ("ohe",    OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    min_frequency=50,
                    sparse_output=True,
                )),
            ]), cat_cols),
        ],
        remainder="drop",
    )

    # sklearn IsolationForest default: max_samples=min(256, n_samples). Tiny
    # subsample is deliberate (each tree learns a coarse approximation; the
    # ensemble averages out). Override only if validation shows poor lift.
    iforest = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )

    pipeline = Pipeline([
        ("prep", preprocessor),
        ("iforest", iforest),
    ])

    logger.info("fitting Isolation Forest n_estimators=%d contamination=%s",
                n_estimators, contamination)
    t0 = datetime.now(tz=timezone.utc)
    pipeline.fit(train_df[feature_cols])
    fit_seconds = (datetime.now(tz=timezone.utc) - t0).total_seconds()
    logger.info("fit done in %.1fs", fit_seconds)

    # -- 5. Score test set. -----------------------------------------------
    # sklearn convention: decision_function is higher for *normal* samples.
    # We negate so anomaly_score is "higher = more anomalous" (intuitive
    # for the action-taker UI).
    raw_decision = pipeline.decision_function(test_df[feature_cols])
    anomaly_score = -raw_decision

    # Global percentile (vs all test rows).
    global_pct = (pd.Series(anomaly_score).rank(method="average", pct=True).to_numpy()) * 100.0

    # Peer-group percentile: rank within NAF 2-digit prefix. Companies
    # whose activity_code is null fall into the "__missing__" bucket and
    # get their own peer group; small groups (< MIN_PEER_GROUP_SIZE) fall
    # back to global percentile so a 5-company NAF bucket doesn't produce
    # noisy ranks.
    MIN_PEER_GROUP_SIZE = 200
    naf_prefix = (
        test_df["activity_code"].astype("string")
        .str.replace(".", "", regex=False)
        .str.replace("Z", "", regex=False)
        .str.slice(0, 2)
        .fillna("__missing__")
    )
    score_df = pd.DataFrame({
        "siren": test_df["siren"].to_numpy(),
        "prediction_year": test_df["prediction_year"].to_numpy(),
        "anomaly_score": anomaly_score,
        "global_percentile": global_pct,
        "naf_prefix": naf_prefix.to_numpy(),
    })
    peer_sizes = score_df.groupby("naf_prefix")["anomaly_score"].transform("size")
    peer_rank = score_df.groupby("naf_prefix")["anomaly_score"].rank(method="average", pct=True) * 100.0
    # Where peer group is too small, fall back to global percentile.
    score_df["peer_percentile"] = peer_rank.where(peer_sizes >= MIN_PEER_GROUP_SIZE, score_df["global_percentile"])
    score_df["peer_group_size"] = peer_sizes.astype(int)

    logger.info("scored %d test rows (global pct + peer pct over %d NAF buckets)",
                len(score_df), score_df["naf_prefix"].nunique())

    # -- 6. Validation: load labels at test_year, compute lift. -----------
    logger.info("loading labels for validation (NOT used in training)")
    labels_df = _load_labels(labels_path=labels_path, year=test_year,
                             columns=("siren", "prediction_year") + VALIDATION_LABELS)

    merged = score_df.merge(labels_df, on=["siren", "prediction_year"], how="inner")
    logger.info("validation merge: score_rows=%d label_rows=%d joined=%d",
                len(score_df), len(labels_df), len(merged))

    validation = _validate_against_labels(merged)

    # -- 7. Persist artifacts. --------------------------------------------
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    trained_at = datetime.now(tz=timezone.utc)
    model_version = trained_at.strftime("anomaly-v2-%Y%m%d-%H%M%S")

    bundle = {
        "pipeline": pipeline,
        "model_version": model_version,
        "feature_columns": feature_cols,
        "numeric_columns": num_cols,
        "categorical_columns": cat_cols,
        "trained_at": trained_at.isoformat(),
        "model_family": "isolation_forest",
        "n_estimators": n_estimators,
        "contamination": str(contamination),
        "random_state": random_state,
    }
    model_path = artifacts_dir / "model.joblib"
    joblib.dump(bundle, model_path)

    scores_path = artifacts_dir / "test_scores.parquet"
    score_df.to_parquet(scores_path, index=False)

    metadata = {
        "model_version": model_version,
        "trained_at": trained_at.isoformat(),
        "fit_seconds": fit_seconds,
        "data_lake_dir": str(data_lake_dir),
        "features_path": str(features_path),
        "labels_path": str(labels_path),
        "train_start_year": train_start_year,
        "train_end_year": train_end_year,
        "test_year": test_year,
        "max_rows_train": max_rows,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "validation_rows": int(len(merged)),
        "feature_count": len(feature_cols),
        "numeric_columns": num_cols,
        "categorical_columns": cat_cols,
        "n_estimators": n_estimators,
        "contamination": str(contamination),
        "random_state": random_state,
        "min_peer_group_size": MIN_PEER_GROUP_SIZE,
        "peer_groups_count": int(score_df["naf_prefix"].nunique()),
        "validation": validation,
        "artifacts": {
            "model_joblib": str(model_path),
            "test_scores_parquet": str(scores_path),
        },
    }
    (artifacts_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    _write_run_summary(artifacts_dir / "run_summary.md", metadata)

    logger.info("done. validation summary: %s",
                {k: validation[k] for k in validation if "_top_5pct_lift" in k})
    return metadata


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_against_labels(merged: Any) -> dict[str, Any]:
    """For each VALIDATION_LABEL: compute lift at top-K%, AP and AUC against
    the unsupervised anomaly score. The anomaly model has NOT seen these
    labels at training time; this is pure held-out evaluation.
    """
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score

    result: dict[str, Any] = {}
    score = merged["anomaly_score"].to_numpy()

    for label in VALIDATION_LABELS:
        y = merged[label].astype(int).to_numpy()
        base_rate = float(y.mean()) if len(y) else 0.0
        per_label: dict[str, Any] = {
            "base_rate": base_rate,
            "positives": int(y.sum()),
            "total": int(len(y)),
        }

        # AP / AUC of the unsupervised score against this label.
        per_label["ap_anomaly_vs_label"] = _safe(average_precision_score, y, score)
        per_label["auc_anomaly_vs_label"] = _safe(roc_auc_score, y, score)

        # Lift at top-K%.
        for top_k in (1, 5, 10):
            threshold = float(np.quantile(score, 1.0 - top_k / 100.0))
            in_top = score >= threshold
            top_size = int(in_top.sum())
            top_positives = int(y[in_top].sum())
            top_precision = (top_positives / top_size) if top_size else 0.0
            lift = (top_precision / base_rate) if base_rate else 0.0
            per_label[f"top_{top_k}pct"] = {
                "threshold": threshold,
                "size": top_size,
                "positives": top_positives,
                "precision": top_precision,
                "lift": lift,
                "recall": (top_positives / int(y.sum())) if int(y.sum()) else 0.0,
            }

        result[label] = per_label

    # Gate check: lift_top_5pct >= 3 on every label (roadmap criterion).
    result["gate"] = {
        "criterion": "lift_top_5pct >= 3 on all VALIDATION_LABELS",
        "pass": all(
            result[label]["top_5pct"]["lift"] >= 3.0 for label in VALIDATION_LABELS
        ),
        "per_label_top_5pct_lift": {
            label: result[label]["top_5pct"]["lift"] for label in VALIDATION_LABELS
        },
    }
    return result


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_features(
    *,
    features_path: Path,
    year_lo: int,
    year_hi: int,
    max_rows: int | None,
) -> Any:
    import duckdb

    con = duckdb.connect()
    try:
        all_cols = _list_columns(con, _glob(features_path))
        # Always pull siren + prediction_year for the temporal split and
        # downstream label join. Other columns: everything in the parquet
        # (we project EXCLUDE_COLUMNS out *after* loading because some of
        # them might be useful for bookkeeping later, e.g. company_name).
        select_cols = list(all_cols)
        select_sql = ", ".join(f'"{c}"' for c in select_cols)

        where_sql = f"prediction_year BETWEEN {int(year_lo)} AND {int(year_hi)}"
        total = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true) "
            f"WHERE {where_sql}"
        ).fetchone()[0]
        logger.info("eligible feature rows for years [%d,%d]: %d", year_lo, year_hi, total)

        sample_sql = ""
        order_sql = "ORDER BY prediction_year, siren"
        limit_sql = ""
        if max_rows and total > max_rows:
            modulus = 1_000_000
            threshold = math.ceil((int(max_rows) / total) * modulus * 1.15)
            threshold = max(1, min(modulus, threshold))
            row_hash = "hash(siren || '|' || prediction_year)"
            sample_sql = f" AND ({row_hash}) % {modulus} < {threshold}"
            order_sql = f"ORDER BY {row_hash}"
            limit_sql = f"LIMIT {int(max_rows)}"
            logger.info("sampling threshold=%d/%d target=%d", threshold, modulus, max_rows)

        df = con.execute(
            f"""
            SELECT {select_sql}
            FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true)
            WHERE {where_sql}{sample_sql}
            {order_sql}
            {limit_sql}
            """
        ).df()
    finally:
        con.close()
    return df


def _load_labels(*, labels_path: Path, year: int, columns: tuple[str, ...]) -> Any:
    import duckdb

    con = duckdb.connect()
    try:
        select_sql = ", ".join(f'"{c}"' for c in columns)
        df = con.execute(
            f"""
            SELECT {select_sql}
            FROM read_parquet('{_sql_string(_glob(labels_path))}', union_by_name=true)
            WHERE prediction_year = {int(year)}
            """
        ).df()
    finally:
        con.close()
    return df


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _write_run_summary(path: Path, meta: dict[str, Any]) -> None:
    v = meta["validation"]
    gate = v["gate"]
    lines: list[str] = []
    a = lines.append

    a("# V2 Layer 2 -- Anomaly detector (Isolation Forest)")
    a("")
    a(f"- **Trained at**: {meta['trained_at']}  ({meta['fit_seconds']:.1f}s fit)")
    a(f"- **Model version**: `{meta['model_version']}`")
    a(f"- **n_estimators**: {meta['n_estimators']}  | **contamination**: `{meta['contamination']}`  | **random_state**: {meta['random_state']}")
    a(f"- **Train**: years [{meta['train_start_year']}, {meta['train_end_year']}], rows = {meta['train_rows']:,} (max_rows={meta['max_rows_train']})")
    a(f"- **Test** : year {meta['test_year']}, rows = {meta['test_rows']:,}")
    a(f"- **Features**: {meta['feature_count']} ({len(meta['numeric_columns'])} num + {len(meta['categorical_columns'])} cat)")
    a(f"- **Peer groups (NAF 2-digit prefix)**: {meta['peer_groups_count']} buckets (min size for peer-pct = {meta['min_peer_group_size']})")
    a("")
    a("## Validation against held-out labels")
    a("")
    a("**Methodology.** The model was trained without using any risk label. ")
    a("For each label below, we measure whether companies flagged as anomalous ")
    a("by the unsupervised score are over-represented in the actual risk events. ")
    a("A useful detector should show lift >= 3 at the top 5% (i.e. 5%-most-anomalous ")
    a("companies are 3x+ more likely to hit the risk event than the base rate).")
    a("")
    a(f"**Gate** ({gate['criterion']}): " +
      ("[OK] PASS" if gate["pass"] else "[KO] FAIL"))
    a("")
    a("| Label | Base rate | AP (anomaly→label) | AUC | Lift @ top 1% | Lift @ top 5% | Lift @ top 10% |")
    a("|---|---:|---:|---:|---:|---:|---:|")
    for label in VALIDATION_LABELS:
        d = v[label]
        a(f"| `{label}` | {d['base_rate']:.4%} | "
          f"{(d['ap_anomaly_vs_label'] or 0):.4f} | {(d['auc_anomaly_vs_label'] or 0):.4f} | "
          f"{d['top_1pct']['lift']:.2f}x | {d['top_5pct']['lift']:.2f}x | {d['top_10pct']['lift']:.2f}x |")
    a("")
    a("## Detail at top 5% (recall, precision)")
    a("")
    a("| Label | Top-5% size | Top-5% positives | Precision | Recall |")
    a("|---|---:|---:|---:|---:|")
    for label in VALIDATION_LABELS:
        d = v[label]["top_5pct"]
        a(f"| `{label}` | {d['size']:,} | {d['positives']:,} | {d['precision']:.4f} | {d['recall']:.4f} |")
    a("")
    a("## Interpretation hints")
    a("")
    a("- **AP and AUC measure the *full ranking* by anomaly score against each label.** ")
    a("  Lower than the Phase 4 supervised AP per label is *expected* -- the anomaly ")
    a("  detector hasn't been told what to look for. Worth investigating only if it ")
    a("  performs *worse than random* (AUC < 0.5).")
    a("- **Lift @ top-K% is the action-taker metric.** If the top 5% by anomaly score ")
    a("  has 3-10x the base rate of legal_distress, the detector adds clear value as ")
    a("  an early-warning system, even though its raw AP is well below the supervised ")
    a("  classifier's.")
    a("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_columns(con: Any, glob: str) -> list[str]:
    return con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{glob}', union_by_name=true) LIMIT 0"
    ).df()["column_name"].tolist()


def _glob(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def _has_parquet(path: Path) -> bool:
    return path.exists() and any(path.rglob("*.parquet"))


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _safe(func: Any, y_true: Any, y_score: Any) -> float | None:
    try:
        return float(func(y_true, y_score))
    except Exception:
        return None


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train V2 Layer 2 anomaly detector (Isolation Forest, unsupervised).",
    )
    parser.add_argument("--data-lake-dir", help="Defaults to settings.DATA_LAKE_DIR.")
    parser.add_argument("--artifacts-dir", help="Defaults to settings.ML_ARTIFACTS_DIR.")
    parser.add_argument("--train-start-year", type=int, default=2017)
    parser.add_argument("--train-end-year",   type=int, default=2022)
    parser.add_argument("--test-year",        type=int, default=2023)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=2_000_000,
        help="Train-row cap (hash-deterministic sampling). Set 0 or pass --no-cap for full V2.",
    )
    parser.add_argument(
        "--no-cap",
        action="store_true",
        help="Disable --max-rows and train on the full V2 train years.",
    )
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument(
        "--contamination",
        default="auto",
        help="sklearn IsolationForest contamination ('auto' or a float in (0, 0.5]).",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    if args.no_cap or args.max_rows == 0:
        args.max_rows = None
    # contamination: try float, else keep string
    if args.contamination not in ("auto",):
        try:
            args.contamination = float(args.contamination)
        except ValueError:
            pass
    return args


if __name__ == "__main__":
    raise SystemExit(main())
