"""Train a V2 HGB model targeted at a single risk label.

V2 vs V1 differences (vs `app/tools/train_continuity_model.py`):
- HGB only. V1 compared 4 boosting libraries; V2 has picked HGB based on
  V1 Phase B sweep results, so the multi-family dispatcher is removed.
- No `class_weight='balanced'`. V1 used it; V2 leaves probabilities un-
  scaled so Phase 5 (threshold tuning) and Phase 8 (calibration) operate
  on the raw distribution. The cost of imbalance is paid via the
  decision threshold instead of via the loss reweighting -- cleaner
  calibration target.
- Reads `features/company_year_features_v2/` and `features/risk_labels_v2/`.
- Writes artifacts under `ml-artifacts/v2/per_label/<label>/` so the 5
  runs (one per label) sit side-by-side.
- Persists test-set predictions so Phase 6 can bootstrap CIs without
  reloading the model.

The CategoricalCardinalityCapper is duplicated from V1 rather than
imported, so the saved joblib bundle does not pin V2 to V1's module
path at load time (FastAPI loader, eventual V1 cleanup).
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

logger = logging.getLogger("train_label_specific_model_v2")


# ---------------------------------------------------------------------------
# Categorical preprocessor (kept self-contained so the joblib bundle does
# not depend on V1's training module being importable).
# ---------------------------------------------------------------------------


class CategoricalCardinalityCapper:
    """Cap categorical column cardinality to fit HGB's ``max_bins`` and cast
    to pandas Categorical so HGB picks the columns up via
    ``categorical_features='from_dtype'``.

    Values outside the top-N most frequent in *training data* (and values
    never seen at training time) are folded into ``__OTHER__``. NaN is left
    as NaN and handled by HGB's native missing-value bin.

    Parameters are stored verbatim for sklearn ``clone()`` compatibility.
    """

    def __init__(
        self,
        categorical_columns: list[str],
        max_categories: int = 250,
        other_label: str = "__OTHER__",
    ) -> None:
        self.categorical_columns = categorical_columns
        self.max_categories = max_categories
        self.other_label = other_label

    def fit(self, X: Any, y: Any = None) -> "CategoricalCardinalityCapper":
        max_categories = int(self.max_categories)
        self.top_categories_: dict[str, set[str]] = {}
        for column in list(self.categorical_columns):
            if column not in X.columns:
                continue
            counts = X[column].dropna().astype(str).value_counts()
            self.top_categories_[column] = set(
                counts.head(max_categories).index.tolist()
            )
        return self

    def transform(self, X: Any) -> Any:
        other_label = str(self.other_label)
        X = X.copy()
        for column in list(self.categorical_columns):
            if column not in X.columns:
                continue
            allowed = self.top_categories_.get(column, set())
            series = X[column].astype(object).where(X[column].notna(), None)
            mapped = series.map(
                lambda value, _allowed=allowed, _other=other_label: (
                    value if (value is None or value in _allowed) else _other
                )
            )
            X[column] = mapped.astype("category")
        return X

    def fit_transform(self, X: Any, y: Any = None) -> Any:
        return self.fit(X, y).transform(X)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {
            "categorical_columns": self.categorical_columns,
            "max_categories": self.max_categories,
            "other_label": self.other_label,
        }

    def set_params(self, **params: Any) -> "CategoricalCardinalityCapper":
        for key, value in params.items():
            setattr(self, key, value)
        return self


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


ALLOWED_TARGETS = (
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
)

# Columns excluded from the feature matrix. The five `*_risk_12m_label`
# columns shouldn't be in the features parquet anyway (labels live in a
# separate file), but we exclude them defensively in case a future build
# joins them in. Other entries reproduce V1's decisions
# (`app/tools/train_continuity_model.py:EXCLUDE_COLUMNS`):
# - identifiers / dates that aren't features
# - degenerate columns observed in V1 Run 8 (collinear / zero-variance)
EXCLUDE_COLUMNS = {
    "siren",
    "prediction_date",
    "first_future_legal_event_date",
    "company_name",
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
    # V1-observed degeneracies (see V1 EXCLUDE_COLUMNS comments)
    "has_confidential_financials",
    "formalities_count_all",
    "formalities_count_12m",
    "cessation_formalities_count_all",
    "latest_equity_ratio",
}


# HGB defaults -- match V1's Run 8 baseline so V2 metrics are directly
# comparable. Overridable via --params-file (e.g. tuned_params_hgb.json).
# Note the absence of `class_weight`: V2 design decision (see module
# docstring).
HGB_DEFAULTS: dict[str, Any] = {
    "max_iter": 400,
    "learning_rate": 0.05,
    "max_leaf_nodes": 63,
    "min_samples_leaf": 50,
    "l2_regularization": 1.0,
    "categorical_features": "from_dtype",
    "early_stopping": True,
    "validation_fraction": 0.1,
    "n_iter_no_change": 20,
    "random_state": 42,
}


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    params: dict[str, Any] | None = None
    if args.params_file:
        params = json.loads(Path(args.params_file).read_text(encoding="utf-8"))
    train_label_specific_model(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        artifacts_dir=Path(args.artifacts_dir or settings.ML_ARTIFACTS_DIR) / "v2" / "per_label",
        target=args.target,
        min_rows=args.min_rows,
        max_rows=args.max_rows,
        train_start_year=args.train_start_year,
        train_end_year=args.train_end_year,
        hgb_param_overrides=params,
    )
    return 0


def train_label_specific_model(
    *,
    data_lake_dir: Path,
    artifacts_dir: Path,
    target: str,
    min_rows: int = 1000,
    max_rows: int | None = None,
    train_start_year: int | None = None,
    train_end_year: int | None = None,
    hgb_param_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Train one V2 HGB model. Returns a metadata dict (also written to disk).

    Output layout::

        artifacts_dir / <label> /
            model.joblib
            metadata.json
            run_summary.md
            test_predictions.parquet
    """
    if target not in ALLOWED_TARGETS:
        raise ValueError(
            f"unknown target {target!r}; expected one of {ALLOWED_TARGETS}"
        )

    import duckdb
    import joblib
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.pipeline import Pipeline

    features_path = data_lake_dir / "features" / "company_year_features_v2"
    labels_path = data_lake_dir / "features" / "risk_labels_v2"
    if not _has_parquet(features_path):
        raise FileNotFoundError(f"missing V2 features parquet under {features_path}")
    if not _has_parquet(labels_path):
        raise FileNotFoundError(f"missing V2 labels parquet under {labels_path}")

    logger.info("loading V2 features+labels target=%s years=[%s,%s] max_rows=%s",
                target, train_start_year, train_end_year, max_rows)
    df = _load_dataset(
        features_path=features_path,
        labels_path=labels_path,
        target=target,
        train_start_year=train_start_year,
        train_end_year=train_end_year,
        max_rows=max_rows,
    )
    if len(df) < min_rows:
        raise RuntimeError(
            f"not enough rows for training: {len(df)} < {min_rows}"
        )

    y = df[target].astype(int)
    if y.nunique() < 2:
        raise RuntimeError(
            f"target {target} has one class only in the sample: "
            f"{y.value_counts().to_dict()}"
        )

    feature_columns = [
        c for c in df.columns if c not in EXCLUDE_COLUMNS and c != target
    ]
    X = df[feature_columns].copy()
    # HGB rejects object dtype on boolean columns arriving as 0/1/None; cast.
    for col in X.columns:
        if pd.api.types.is_bool_dtype(X[col]):
            X[col] = X[col].astype(float)

    numeric_columns = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    categorical_columns = [c for c in X.columns if c not in numeric_columns]

    # Temporal split: train on years < latest, test on latest.
    latest_year = int(df["prediction_year"].max())
    train_mask = df["prediction_year"] < latest_year
    if train_mask.sum() < min_rows:
        raise RuntimeError(
            f"after temporal split, train has only {int(train_mask.sum())} rows; "
            f"need at least {min_rows}. Adjust --train-start-year / --train-end-year."
        )
    if y[train_mask].nunique() < 2 or y[~train_mask].nunique() < 2:
        raise RuntimeError(
            "after temporal split, train or test has only one class; "
            "check label distribution by year"
        )

    X_train = X[train_mask]
    X_test = X[~train_mask]
    y_train = y[train_mask]
    y_test = y[~train_mask]

    hgb_params = dict(HGB_DEFAULTS)
    if hgb_param_overrides:
        hgb_params.update(hgb_param_overrides)

    pipeline = Pipeline(steps=[
        (
            "prepare_categoricals",
            CategoricalCardinalityCapper(categorical_columns, max_categories=250),
        ),
        ("classifier", HistGradientBoostingClassifier(**hgb_params)),
    ])

    logger.info(
        "fitting HGB train_rows=%d test_rows=%d positives_train=%d positives_test=%d",
        len(X_train), len(X_test), int(y_train.sum()), int(y_test.sum()),
    )
    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    tn, fp, fn, tp = [
        int(v) for v in confusion_matrix(y_test, predictions, labels=[0, 1]).ravel()
    ]
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "roc_auc": _safe(roc_auc_score, y_test, probabilities),
        "average_precision": _safe(average_precision_score, y_test, probabilities),
        "f1_at_0_5": float(f1_score(y_test, predictions, zero_division=0)),
        "precision_at_0_5": float(precision_score(y_test, predictions, zero_division=0)),
        "recall_at_0_5": float(recall_score(y_test, predictions, zero_division=0)),
        "test_positive_rate": float(y_test.mean()),
        "confusion_matrix_at_0_5": {
            "true_negative": tn, "false_positive": fp,
            "false_negative": fn, "true_positive": tp,
        },
    }
    threshold_table = _threshold_analysis(y_test, probabilities)
    metrics["threshold_analysis"] = threshold_table

    # Persist artifacts.
    label_dir = artifacts_dir / target
    label_dir.mkdir(parents=True, exist_ok=True)

    trained_at = datetime.now(tz=timezone.utc)
    model_version = trained_at.strftime("v2-%Y%m%d-%H%M%S")
    bundle = {
        "pipeline": pipeline,
        "target": target,
        "model_version": model_version,
        "feature_columns": feature_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "trained_at": trained_at.isoformat(),
        "horizon_months": 12,
        "model_family": "hgb",
        "class_weight": None,  # explicit -- design decision
    }
    model_path = label_dir / "model.joblib"
    joblib.dump(bundle, model_path)

    # Test predictions for Phase 6 bootstrap (no need to reload the model).
    pred_df = pd.DataFrame({
        "siren": df.loc[~train_mask, "siren"].to_numpy() if "siren" in df.columns else None,
        "prediction_year": df.loc[~train_mask, "prediction_year"].to_numpy(),
        "y_true": y_test.to_numpy(),
        "y_score": probabilities,
    })
    pred_path = label_dir / "test_predictions.parquet"
    pred_df.to_parquet(pred_path, index=False)

    metadata = {
        "target": target,
        "model_version": model_version,
        "model_family": "hgb",
        "class_weight": None,
        "hgb_params": hgb_params,
        "hgb_params_overridden": bool(hgb_param_overrides),
        "trained_at": trained_at.isoformat(),
        "horizon_months": 12,
        "data_lake_dir": str(data_lake_dir),
        "features_path": str(features_path),
        "labels_path": str(labels_path),
        "train_start_year": train_start_year,
        "train_end_year": train_end_year,
        "max_rows": max_rows,
        "sample_rows": int(len(df)),
        "split_strategy": f"time_split_latest_year_{latest_year}",
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "train_positives": int(y_train.sum()),
        "test_positives": int(y_test.sum()),
        "feature_count": int(len(feature_columns)),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "metrics": metrics,
        "artifacts": {
            "model_joblib": str(model_path),
            "test_predictions_parquet": str(pred_path),
        },
    }
    (label_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    _write_run_summary(label_dir / "run_summary.md", metadata)

    logger.info(
        "trained target=%s ap=%.4f auc=%.4f model=%s",
        target,
        metrics.get("average_precision") or 0.0,
        metrics.get("roc_auc") or 0.0,
        model_path,
    )
    return metadata


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_dataset(
    *,
    features_path: Path,
    labels_path: Path,
    target: str,
    train_start_year: int | None,
    train_end_year: int | None,
    max_rows: int | None,
) -> Any:
    import duckdb

    con = duckdb.connect()
    try:
        feature_columns = _list_columns(con, _glob(features_path))
        select_cols = [c for c in feature_columns if c not in EXCLUDE_COLUMNS]
        # `siren` and `prediction_year` are driven by the JOIN and may not be
        # in the model features, but we want them in the dataframe for the
        # temporal split and for Phase 6 prediction bookkeeping.
        for required in ("siren", "prediction_year"):
            if required not in select_cols and required in feature_columns:
                select_cols.append(required)
        select_sql = ", ".join(f'f."{c}"' for c in select_cols)

        where = [f'l."{target}" IS NOT NULL']
        if train_start_year is not None:
            where.append(f"f.prediction_year >= {int(train_start_year)}")
        if train_end_year is not None:
            where.append(f"f.prediction_year <= {int(train_end_year)}")
        where_sql = " AND ".join(where)

        total = con.execute(f"""
            SELECT COUNT(*)
            FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true) f
            JOIN read_parquet('{_sql_string(_glob(labels_path))}', union_by_name=true) l
              USING (siren, prediction_year)
            WHERE {where_sql}
        """).fetchone()[0]
        logger.info("eligible_rows=%d", total)

        sample_sql = ""
        order_sql = "ORDER BY f.prediction_year, f.siren"
        limit_sql = ""
        if max_rows and total > max_rows:
            modulus = 1_000_000
            # 15% oversample so we hit max_rows after the LIMIT (mild buffer).
            threshold = math.ceil((int(max_rows) / total) * modulus * 1.15)
            threshold = max(1, min(modulus, threshold))
            row_hash = "hash(f.siren || '|' || f.prediction_year)"
            sample_sql = f" AND ({row_hash}) % {modulus} < {threshold}"
            order_sql = f"ORDER BY {row_hash}"
            limit_sql = f"LIMIT {int(max_rows)}"
            logger.info(
                "sampling: threshold=%d/%d, target rows=%d",
                threshold, modulus, max_rows,
            )

        query = f"""
            SELECT {select_sql}, l."{target}"
            FROM read_parquet('{_sql_string(_glob(features_path))}', union_by_name=true) f
            JOIN read_parquet('{_sql_string(_glob(labels_path))}', union_by_name=true) l
              USING (siren, prediction_year)
            WHERE {where_sql}{sample_sql}
            {order_sql}
            {limit_sql}
        """
        df = con.execute(query).df()
    finally:
        con.close()
    return df


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


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def _safe(func: Any, y_true: Any, y_score: Any) -> float | None:
    try:
        return float(func(y_true, y_score))
    except Exception:
        return None


def _threshold_analysis(
    y_true: Any,
    y_score: Any,
    thresholds: tuple[float, ...] = (
        0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50,
    ),
) -> list[dict[str, float | int]]:
    import numpy as np

    yt = np.asarray(y_true, dtype=int)
    ys = np.asarray(y_score, dtype=float)
    total = int(len(yt))
    positives = int(yt.sum())
    negatives = total - positives
    rows: list[dict[str, float | int]] = []
    for t in thresholds:
        pred = ys >= t
        tp = int(((pred == 1) & (yt == 1)).sum())
        fp = int(((pred == 1) & (yt == 0)).sum())
        fn = int(((pred == 0) & (yt == 1)).sum())
        tn = int(((pred == 0) & (yt == 0)).sum())
        flagged = tp + fp
        rows.append({
            "threshold": float(t),
            "predicted_positive": flagged,
            "flagged_rate": _safe_divide(flagged, total),
            "precision": _safe_divide(tp, flagged),
            "recall": _safe_divide(tp, positives),
            "false_positive_rate": _safe_divide(fp, negatives),
            "f1": _safe_divide(2 * tp, 2 * tp + fp + fn),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        })
    return rows


def _safe_divide(num: float | int, den: float | int) -> float:
    return float(num / den) if den else 0.0


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------


def _write_run_summary(path: Path, meta: dict[str, Any]) -> None:
    m = meta["metrics"]
    lines: list[str] = []
    a = lines.append
    a(f"# V2 per-label model -- `{meta['target']}`")
    a("")
    a(f"- **Trained at**: {meta['trained_at']}")
    a(f"- **Model family**: HGB (sklearn HistGradientBoostingClassifier)")
    a(f"- **class_weight**: `None` (V2 design decision, see Phase 4 module docstring)")
    a(f"- **Model version**: `{meta['model_version']}`")
    a("")
    a("## Dataset")
    a("")
    a(f"- Features: `{meta['features_path']}`")
    a(f"- Labels  : `{meta['labels_path']}`")
    a(f"- Year range used: [{meta.get('train_start_year')}, {meta.get('train_end_year')}]")
    a(f"- Sample rows: {meta['sample_rows']:,}  (max_rows = {meta.get('max_rows')})")
    a(f"- Split: {meta['split_strategy']}")
    a(f"- Train rows: {meta['train_rows']:,}  (positives = {meta['train_positives']:,})")
    a(f"- Test rows : {meta['test_rows']:,}   (positives = {meta['test_positives']:,})")
    a(f"- Feature count: {meta['feature_count']}")
    a("")
    a("## Headline metrics (test set, threshold = 0.5)")
    a("")
    a("| Metric | Value |")
    a("|---|---:|")
    a(f"| Average precision | {(m.get('average_precision') or 0):.4f} |")
    a(f"| ROC AUC           | {(m.get('roc_auc') or 0):.4f} |")
    a(f"| Accuracy          | {m['accuracy']:.4f} |")
    a(f"| Precision @ 0.5   | {m['precision_at_0_5']:.4f} |")
    a(f"| Recall    @ 0.5   | {m['recall_at_0_5']:.4f} |")
    a(f"| F1        @ 0.5   | {m['f1_at_0_5']:.4f} |")
    a(f"| Test positive rate| {m['test_positive_rate']:.4f} |")
    a("")
    cm = m["confusion_matrix_at_0_5"]
    a(f"Confusion matrix @ 0.5: TN={cm['true_negative']}, FP={cm['false_positive']}, "
      f"FN={cm['false_negative']}, TP={cm['true_positive']}.")
    a("")
    a("## Threshold sweep (test set)")
    a("")
    a("| Threshold | Flagged rate | Precision | Recall | F1 |")
    a("|---:|---:|---:|---:|---:|")
    for row in m["threshold_analysis"]:
        a(f"| {row['threshold']:.3f} | {row['flagged_rate']:.4%} | "
          f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |")
    a("")
    a("## HGB hyperparameters")
    a("")
    a("```json")
    a(json.dumps(meta["hgb_params"], indent=2, default=_json_default))
    a("```")
    path.write_text("\n".join(lines), encoding="utf-8")


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
        description="Train a V2 HGB model for one risk label (no class_weight)."
    )
    parser.add_argument("--data-lake-dir", help="Defaults to settings.DATA_LAKE_DIR.")
    parser.add_argument("--artifacts-dir", help="Defaults to settings.ML_ARTIFACTS_DIR.")
    parser.add_argument(
        "--target",
        choices=ALLOWED_TARGETS,
        required=True,
        help="Which label to train against.",
    )
    parser.add_argument("--min-rows", type=int, default=1000)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap (hash-deterministic sampling). Omit for full V2.",
    )
    parser.add_argument(
        "--train-start-year",
        type=int,
        default=2017,
        help="First prediction_year to include.",
    )
    parser.add_argument(
        "--train-end-year",
        type=int,
        default=2023,
        help="Last prediction_year to include. 2024 has incomplete 12m-forward labels.",
    )
    parser.add_argument(
        "--params-file",
        default=None,
        help="JSON file with HGB hyperparameter overrides (e.g. tuned_params_hgb.json).",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
