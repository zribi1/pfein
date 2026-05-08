from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


LABEL_COLUMNS = (
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
)

FEATURE_COLUMNS_TO_PROFILE = (
    "company_age_years",
    "legal_events_count_all",
    "legal_events_count_12m",
    "legal_risk_events_count_all",
    "legal_distress_events_count_all",
    "radiation_events_count_all",
    "formalities_count_all",
    "annual_accounts_count_all",
    "days_since_last_account_filing",
    "latest_revenue",
    "latest_net_result",
    "latest_equity",
    "latest_debt",
)


def main() -> None:
    args = _parse_args()
    data_lake = Path(args.data_lake_dir or _default_data_lake_dir())
    payload = audit_features(data_lake, max_profile_columns=args.max_profile_columns)

    output = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.json:
        print(output)
    else:
        _print_human(payload)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")


def audit_features(data_lake: Path, *, max_profile_columns: int) -> dict[str, Any]:
    try:
        import duckdb
    except ImportError:
        return _audit_features_with_pyarrow(data_lake)

    feature_root = data_lake / "features"
    company_year_root = feature_root / "company_year_features"
    labels_root = feature_root / "risk_labels"
    company_features_root = feature_root / "company_features"

    con = duckdb.connect()
    try:
        datasets = {
            "company_year_features": _dataset_summary(con, company_year_root),
            "risk_labels": _dataset_summary(con, labels_root),
            "company_features": _dataset_summary(con, company_features_root),
        }

        label_balance = {}
        if datasets["risk_labels"]["exists"]:
            labels_sql = _read_parquet_sql(labels_root)
            columns = set(datasets["risk_labels"]["columns"])
            for label in LABEL_COLUMNS:
                if label not in columns:
                    continue
                row = con.execute(
                    f"""
                    SELECT
                        COUNT(*) AS rows,
                        SUM(CASE WHEN {label} THEN 1 ELSE 0 END) AS positives,
                        SUM(CASE WHEN NOT {label} THEN 1 ELSE 0 END) AS negatives,
                        SUM(CASE WHEN {label} IS NULL THEN 1 ELSE 0 END) AS nulls
                    FROM {labels_sql}
                    """
                ).fetchone()
                total = int(row[0] or 0)
                positives = int(row[1] or 0)
                label_balance[label] = {
                    "rows": total,
                    "positives": positives,
                    "negatives": int(row[2] or 0),
                    "nulls": int(row[3] or 0),
                    "positive_rate": round(positives / total, 6) if total else None,
                }

        feature_profile = {}
        if datasets["company_year_features"]["exists"]:
            features_sql = _read_parquet_sql(company_year_root)
            columns = set(datasets["company_year_features"]["columns"])
            selected = [col for col in FEATURE_COLUMNS_TO_PROFILE if col in columns][:max_profile_columns]
            for column in selected:
                row = con.execute(
                    f"""
                    SELECT
                        COUNT(*) AS rows,
                        SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS nulls,
                        MIN({column}) AS min_value,
                        MAX({column}) AS max_value,
                        AVG(CAST({column} AS DOUBLE)) AS avg_value
                    FROM {features_sql}
                    """
                ).fetchone()
                total = int(row[0] or 0)
                nulls = int(row[1] or 0)
                feature_profile[column] = {
                    "rows": total,
                    "nulls": nulls,
                    "null_rate": round(nulls / total, 6) if total else None,
                    "min": row[2],
                    "max": row[3],
                    "avg": row[4],
                }

        return {
            "data_lake_dir": str(data_lake),
            "datasets": datasets,
            "label_balance": label_balance,
            "feature_profile": feature_profile,
        }
    finally:
        con.close()


def _audit_features_with_pyarrow(data_lake: Path) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit(
            "feature auditing requires duckdb or pyarrow; install project requirements first"
        ) from exc

    feature_root = data_lake / "features"
    datasets = {}
    for name in ("company_year_features", "risk_labels", "company_features"):
        root = feature_root / name
        manifest = _read_json(root / "_manifest.json")
        parquet_files = sorted(root.rglob("*.parquet")) if root.exists() else []
        columns: list[str] = []
        file_rows = 0
        for path in parquet_files:
            metadata = pq.read_metadata(path)
            file_rows += metadata.num_rows
            if not columns:
                columns = metadata.schema.names
        datasets[name] = {
            "exists": bool(parquet_files),
            "root": str(root),
            "manifest": manifest,
            "parquet_files": len(parquet_files),
            "rows": file_rows if parquet_files else None,
            "columns": columns,
            "prediction_years": None,
            "audit_mode": "pyarrow_metadata",
        }

    return {
        "data_lake_dir": str(data_lake),
        "datasets": datasets,
        "label_balance": {},
        "feature_profile": {},
        "warnings": [
            "DuckDB is not installed in this Python environment, so only Parquet metadata was audited.",
            "Install project requirements or run inside the API container for label balance and feature profile scans.",
        ],
    }


def _dataset_summary(con: Any, root: Path) -> dict[str, Any]:
    manifest = _read_json(root / "_manifest.json")
    parquet_files = sorted(root.rglob("*.parquet")) if root.exists() else []
    if not parquet_files:
        return {
            "exists": False,
            "root": str(root),
            "manifest": manifest,
            "parquet_files": 0,
            "rows": None,
            "columns": [],
            "prediction_years": None,
        }

    sql = _read_parquet_sql(root)
    rows = con.execute(f"SELECT COUNT(*) FROM {sql}").fetchone()[0]
    columns = [row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {sql}").fetchall()]
    prediction_years = None
    if "prediction_year" in columns:
        year_row = con.execute(
            f"SELECT MIN(prediction_year), MAX(prediction_year), COUNT(DISTINCT prediction_year) FROM {sql}"
        ).fetchone()
        prediction_years = {
            "min": int(year_row[0]) if year_row[0] is not None else None,
            "max": int(year_row[1]) if year_row[1] is not None else None,
            "distinct": int(year_row[2] or 0),
        }

    return {
        "exists": True,
        "root": str(root),
        "manifest": manifest,
        "parquet_files": len(parquet_files),
        "rows": int(rows or 0),
        "columns": columns,
        "prediction_years": prediction_years,
    }


def _read_parquet_sql(root: Path) -> str:
    pattern = str((root / "**" / "*.parquet")).replace("\\", "/").replace("'", "''")
    return f"read_parquet('{pattern}', union_by_name=true)"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _default_data_lake_dir() -> str:
    if os.environ.get("DATA_LAKE_DIR"):
        return os.environ["DATA_LAKE_DIR"]
    if Path("D:/PFE_volumes/data-lake").exists():
        return "D:/PFE_volumes/data-lake"
    return "/data-lake"


def _print_human(payload: dict[str, Any]) -> None:
    print(f"Data lake: {payload['data_lake_dir']}")
    print()
    for name, dataset in payload["datasets"].items():
        if not dataset["exists"]:
            print(f"[missing] {name}")
            continue
        years = dataset.get("prediction_years")
        year_text = ""
        if years:
            year_text = f", years={years['min']}-{years['max']} ({years['distinct']})"
        print(
            f"[ok] {name}: rows={dataset['rows']:,}, files={dataset['parquet_files']}, "
            f"columns={len(dataset['columns'])}{year_text}"
        )

    if payload["label_balance"]:
        print("\nLabel balance:")
        for label, stats in payload["label_balance"].items():
            print(
                f"  {label}: positives={stats['positives']:,}, "
                f"rate={stats['positive_rate']}"
            )

    if payload["feature_profile"]:
        print("\nFeature profile:")
        for column, stats in payload["feature_profile"].items():
            print(
                f"  {column}: null_rate={stats['null_rate']}, "
                f"min={stats['min']}, max={stats['max']}, avg={stats['avg']}"
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit local ML feature and label Parquet datasets.")
    parser.add_argument("--data-lake-dir", help="Data lake root. Defaults to DATA_LAKE_DIR or D:/PFE_volumes/data-lake.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", help="Write the JSON audit payload to this file.")
    parser.add_argument("--max-profile-columns", type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    main()
