"""Score latest company features and publish prediction documents to MongoDB."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, MongoClient, UpdateOne

from app.core.config import settings

logger = logging.getLogger("publish_prediction_results")


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    publish_predictions(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        artifacts_dir=Path(args.artifacts_dir or settings.ML_ARTIFACTS_DIR),
        model_file=args.model_file or settings.ML_MODEL_FILE,
        mongo_uri=args.mongo_uri or settings.MONGO_URI,
        mongo_db=args.mongo_db or settings.MONGO_DB,
        collection=args.collection or settings.PREDICTION_RESULTS_COLLECTION,
        limit=args.limit,
        batch_size=args.batch_size,
    )


def publish_predictions(
    *,
    data_lake_dir: Path,
    artifacts_dir: Path,
    model_file: str,
    mongo_uri: str,
    mongo_db: str,
    collection: str,
    limit: int | None,
    batch_size: int,
) -> int:
    import duckdb
    import joblib

    model_path = artifacts_dir / model_file
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    company_features_dir = data_lake_dir / "features" / "company_features"
    if not _has_parquet(company_features_dir):
        raise FileNotFoundError(f"missing company features under {company_features_dir}")

    bundle = joblib.load(model_path)
    model = bundle["pipeline"]
    feature_columns = list(bundle["feature_columns"])
    model_version = str(bundle["model_version"])
    target = str(bundle.get("target", "continuity_risk_12m_label")).replace("_label", "")
    horizon_months = int(bundle.get("horizon_months", 12))

    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    con = duckdb.connect()
    try:
        df = con.execute(
            f"""
            SELECT *
            FROM read_parquet('{_sql_string(_glob(company_features_dir))}', union_by_name=true)
            ORDER BY siren
            {limit_sql}
            """
        ).df()
    finally:
        con.close()

    missing_columns = [col for col in feature_columns if col not in df.columns]
    if missing_columns:
        raise RuntimeError(f"company features missing model columns: {missing_columns}")

    probabilities = model.predict_proba(df[feature_columns])[:, 1]
    scored_at = datetime.now(tz=timezone.utc)

    client = MongoClient(mongo_uri)
    try:
        coll = client[mongo_db][collection]
        coll.create_index(
            [("siren", ASCENDING), ("target", ASCENDING), ("horizon_months", ASCENDING)],
            unique=True,
        )

        ops: list[UpdateOne] = []
        published = 0
        for idx, probability in enumerate(probabilities):
            row = df.iloc[idx].to_dict()
            siren = str(row.get("siren") or "").strip()
            if not siren:
                continue

            doc = {
                "siren": siren,
                "target": target,
                "horizon_months": horizon_months,
                "model_version": model_version,
                "prediction_year": _json_value(row.get("prediction_year")),
                "probability": float(probability),
                "score_percent": round(float(probability) * 100, 2),
                "risk_bucket": _risk_bucket(float(probability)),
                "explanation_factors": _explanation_factors(row),
                "scored_at": scored_at,
                "updated_at": scored_at,
            }
            ops.append(
                UpdateOne(
                    {
                        "siren": siren,
                        "target": target,
                        "horizon_months": horizon_months,
                    },
                    {"$set": doc, "$setOnInsert": {"created_at": scored_at}},
                    upsert=True,
                )
            )
            if len(ops) >= batch_size:
                batch_count = len(ops)
                coll.bulk_write(ops, ordered=False)
                published += batch_count
                ops.clear()

        if ops:
            batch_count = len(ops)
            coll.bulk_write(ops, ordered=False)
            published += batch_count

        logger.info("published prediction docs=%d collection=%s", published, collection)
        return published
    finally:
        client.close()


def _explanation_factors(row: dict[str, Any]) -> list[dict[str, Any]]:
    factors: list[dict[str, Any]] = []
    _add_factor(
        factors,
        "legal_distress_history",
        row.get("legal_distress_events_count_all"),
        "Past legal distress events",
        higher_is_risk=True,
    )
    _add_factor(
        factors,
        "recent_legal_events",
        row.get("legal_events_count_12m"),
        "Recent BODACC/legal activity",
        higher_is_risk=True,
    )
    _add_factor(
        factors,
        "radiation_history",
        row.get("radiation_events_count_all"),
        "Past radiation events",
        higher_is_risk=True,
    )
    _add_factor(
        factors,
        "filing_gap",
        row.get("days_since_last_account_filing"),
        "Days since latest annual account filing",
        higher_is_risk=True,
    )
    _add_factor(
        factors,
        "company_age",
        row.get("company_age_years"),
        "Company age in years",
        higher_is_risk=False,
    )
    _add_factor(
        factors,
        "latest_net_result",
        row.get("latest_net_result"),
        "Latest net result",
        higher_is_risk=False,
    )
    return factors


def _add_factor(
    factors: list[dict[str, Any]],
    code: str,
    value: Any,
    label: str,
    *,
    higher_is_risk: bool,
) -> None:
    value = _json_value(value)
    if value is None:
        return
    direction = "risk" if higher_is_risk else "protective"
    if isinstance(value, (int, float)) and value < 0:
        direction = "risk" if not higher_is_risk else "protective"
    factors.append(
        {
            "code": code,
            "label": label,
            "value": value,
            "direction": direction,
        }
    )


def _risk_bucket(probability: float) -> str:
    if probability >= 0.7:
        return "high"
    if probability >= 0.4:
        return "medium"
    return "low"


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        if value != value:
            return None
    except Exception:
        pass
    return value


def _has_parquet(root: Path) -> bool:
    return root.exists() and any(root.rglob("*.parquet"))


def _glob(root: Path) -> str:
    return str(root / "**" / "*.parquet").replace("\\", "/")


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish company prediction results to MongoDB.")
    parser.add_argument("--data-lake-dir", help="Defaults to DATA_LAKE_DIR.")
    parser.add_argument("--artifacts-dir", help="Defaults to ML_ARTIFACTS_DIR.")
    parser.add_argument("--model-file", help="Defaults to ML_MODEL_FILE.")
    parser.add_argument("--mongo-uri", help="Defaults to MONGO_URI.")
    parser.add_argument("--mongo-db", help="Defaults to MONGO_DB.")
    parser.add_argument("--collection", help="Defaults to PREDICTION_RESULTS_COLLECTION.")
    parser.add_argument("--limit", type=int, help="Optional smoke-test cap.")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
