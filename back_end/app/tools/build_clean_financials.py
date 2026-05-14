"""Normalize raw financial Parquet resources into clean financial rows."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("build_clean_financials")
MIN_REASONABLE_DATE = "1900-01-01"
FUTURE_DATE_SLACK_DAYS = 366


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    build_clean_financials(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        overwrite=args.overwrite,
        max_rows=args.max_rows,
    )


def build_clean_financials(
    *,
    data_lake_dir: Path,
    overwrite: bool,
    max_rows: int | None = None,
) -> None:
    import duckdb

    raw_root = _first_dataset(data_lake_dir / "raw" / "financials", data_lake_dir / "raw" / "financial")
    if raw_root is None:
        raise RuntimeError("no raw financial Parquet found")

    output_dir = data_lake_dir / "clean" / "financials"
    _prepare_output_dir(output_dir, data_lake_dir, overwrite)

    con = duckdb.connect()
    try:
        temp_dir = _duckdb_temp_dir(data_lake_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"SET temp_directory = '{_sql_string(str(temp_dir).replace('\\', '/'))}'")
        con.execute("PRAGMA enable_progress_bar")
        raw_glob = _duckdb_glob(raw_root)
        limit_sql = f"LIMIT {int(max_rows)}" if max_rows else ""
        output_file = output_dir / "financials.parquet"
        target = _sql_string(str(output_file).replace("\\", "/"))
        logger.info("clean financials reading raw_root=%s", raw_root)
        logger.info("clean financials writing output=%s", output_file)
        con.execute(
            f"""
            COPY (
                WITH parsed AS (
                    SELECT
                        NULLIF(TRIM(siren), '')::VARCHAR AS siren,
                        TRY_CAST(date_cloture_exercice AS DATE) AS raw_closing_date,
                        type_bilan::VARCHAR AS account_type,
                        confidentiality::VARCHAR AS confidentiality,
                        TRY_CAST(map_extract(liasse, 'FL')[1] AS DOUBLE) AS revenue,
                        TRY_CAST(map_extract(liasse, 'HN')[1] AS DOUBLE) AS net_result,
                        TRY_CAST(map_extract(liasse, 'DL')[1] AS DOUBLE) AS equity,
                        TRY_CAST(map_extract(liasse, 'EC')[1] AS DOUBLE) AS debt,
                        TRY_CAST(map_extract(liasse, 'EE')[1] AS DOUBLE) AS total_liabilities_and_equity,
                        TRY_CAST(map_extract(liasse, 'CO')[1] AS DOUBLE) AS total_assets,
                        TRY_CAST(map_extract(liasse, 'DA')[1] AS DOUBLE) AS share_capital,
                        TRY_CAST(map_extract(liasse, 'FJ')[1] AS DOUBLE) AS goods_sales,
                        TRY_CAST(map_extract(liasse, 'FK')[1] AS DOUBLE) AS services_sales,
                        filename::VARCHAR AS source_file
                    FROM read_parquet('{_sql_string(raw_glob)}', union_by_name=true, filename=true)
                    WHERE siren IS NOT NULL
                    {limit_sql}
                ),
                base AS (
                    SELECT
                        siren,
                        CASE
                            WHEN raw_closing_date BETWEEN DATE '{MIN_REASONABLE_DATE}'
                             AND CAST(CURRENT_DATE + INTERVAL {FUTURE_DATE_SLACK_DAYS} DAY AS DATE)
                            THEN raw_closing_date
                            ELSE NULL
                        END AS closing_date,
                        account_type,
                        confidentiality,
                        revenue,
                        net_result,
                        equity,
                        debt,
                        total_liabilities_and_equity,
                        total_assets,
                        share_capital,
                        goods_sales,
                        services_sales,
                        source_file
                    FROM parsed
                )
                SELECT
                    NULLIF(TRIM(siren), '')::VARCHAR AS siren,
                    closing_date,
                    YEAR(closing_date)::INTEGER AS financial_year,
                    account_type,
                    confidentiality,
                    revenue,
                    net_result,
                    equity,
                    debt,
                    total_liabilities_and_equity,
                    total_assets,
                    share_capital,
                    goods_sales,
                    services_sales,
                    CASE WHEN revenue IS NULL OR revenue = 0 THEN NULL ELSE net_result / revenue END AS net_margin,
                    CASE WHEN total_assets IS NULL OR total_assets = 0 THEN NULL ELSE debt / total_assets END AS debt_to_assets,
                    CASE WHEN total_assets IS NULL OR total_assets = 0 THEN NULL ELSE equity / total_assets END AS equity_ratio,
                    CASE WHEN equity IS NULL OR equity = 0 THEN NULL ELSE debt / equity END AS debt_to_equity,
                    (net_result < 0)::BOOLEAN AS has_negative_result,
                    (equity < 0)::BOOLEAN AS has_negative_equity,
                    'data_gouv_financial_parquet'::VARCHAR AS source,
                    source_file,
                    now() AS exported_at
                FROM base
                WHERE closing_date IS NOT NULL
            )
            TO '{target}'
            (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE TRUE)
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{_sql_string(_duckdb_glob(output_dir))}', union_by_name=true)"
            ).fetchone()[0]
        )
        logger.info("clean financials rows=%d output=%s", row_count, output_dir)
    finally:
        con.close()

    _write_manifest(
        output_dir,
        {
            "dataset": "clean_financials",
            "rows": row_count,
            "raw_root": str(raw_root),
            "schema_version": 1,
            "liasse_mappings": {
                "revenue": "FL",
                "net_result": "HN",
                "equity": "DL",
                "debt": "EC",
                "total_liabilities_and_equity": "EE",
                "total_assets": "CO",
                "share_capital": "DA",
                "goods_sales": "FJ",
                "services_sales": "FK",
            },
            "derived_columns": [
                "net_margin",
                "debt_to_assets",
                "equity_ratio",
                "debt_to_equity",
                "has_negative_result",
                "has_negative_equity",
            ],
        },
    )


def _first_dataset(*roots: Path) -> Path | None:
    for root in roots:
        if root.exists() and any(root.rglob("*.parquet")):
            return root
    return None


def _duckdb_temp_dir(data_lake_dir: Path) -> Path:
    configured = os.environ.get("DUCKDB_TEMP_DIRECTORY")
    if configured:
        return Path(configured)
    if str(data_lake_dir).startswith("/content/drive/"):
        return Path("/content/pfein_duckdb_tmp")
    return data_lake_dir / "tmp" / "duckdb"


def _duckdb_glob(root: Path) -> str:
    return str(root / "**" / "*.parquet").replace("\\", "/")


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _prepare_output_dir(path: Path, data_lake_dir: Path, overwrite: bool) -> None:
    if path.exists() and overwrite:
        resolved = path.resolve()
        root = data_lake_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise RuntimeError(f"refusing to delete output outside data lake: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_manifest(output_dir: Path, payload: dict[str, Any]) -> None:
    payload = {
        **payload,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (output_dir / "_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build clean financial Parquet from raw financial source.")
    parser.add_argument("--data-lake-dir", help="Defaults to DATA_LAKE_DIR.")
    parser.add_argument("--max-rows", type=int, help="Optional smoke-test cap.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
