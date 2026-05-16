"""Build the period-aware INSEE identity table for V2.

Reads `data-lake/raw/insee/bulk/stock_unite_legale_historique/**/*.parquet`
(one row per `(siren, period)`) and produces
`data-lake/clean/company_identity_periodic/` with derived `period_start` /
`period_end` columns and a normalized schema ready for time-aware joins.

Key contract for downstream use
-------------------------------
For a given `(siren, prediction_date)`, the unique matching row is:

    period_start <= prediction_date < period_end

`period_end` is set to the next period's `period_start` for each SIREN. The
latest period of a SIREN gets `period_end = 9999-12-31` so the inequality still
matches.

Run
---
    python -m app.tools.v2.build_company_identity_periodic \\
        --raw-dir /data-lake/raw/insee/bulk/stock_unite_legale_historique \\
        --out-dir /data-lake/clean/company_identity_periodic \\
        --overwrite
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger("build_company_identity_periodic")

# --- Column name resolution ---------------------------------------------------
# The INSEE historique parquet is published with snake_case column names on
# data.gouv.fr, e.g. ``siren``, ``date_debut``, ``date_fin``,
# ``activite_principale_unite_legale``, etc. We resolve them at runtime from
# the actual columns present, with fallbacks for slight schema variations.

CANONICAL_COLUMNS = {
    "siren": ("siren",),
    "period_start": ("date_debut", "date_debut_periode", "dateDebut", "dateDebutPeriode"),
    "period_end": ("date_fin", "date_fin_periode", "dateFin", "dateFinPeriode"),
    "denomination": (
        "denomination_unite_legale",
        "denominationUniteLegale",
        "denomination",
    ),
    "activity_code": (
        "activite_principale_unite_legale",
        "activitePrincipaleUniteLegale",
    ),
    "legal_category_code": (
        "categorie_juridique_unite_legale",
        "categorieJuridiqueUniteLegale",
    ),
    "employee_size_bracket": (
        "tranche_effectifs_unite_legale",
        "trancheEffectifsUniteLegale",
    ),
    "administrative_status": (
        "etat_administratif_unite_legale",
        "etatAdministratifUniteLegale",
    ),
    "creation_date": (
        "date_creation_unite_legale",
        "dateCreationUniteLegale",
    ),
}


def _resolve_columns(con: duckdb.DuckDBPyConnection, glob: str) -> dict[str, str]:
    """Return canonical_name -> actual_column_name mapping for the input parquet."""
    actual = (
        con.execute(f"DESCRIBE SELECT * FROM read_parquet('{glob}', union_by_name=true)")
        .df()["column_name"]
        .tolist()
    )
    actual_lower = {c.lower(): c for c in actual}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for canonical, candidates in CANONICAL_COLUMNS.items():
        found = next(
            (actual_lower[c.lower()] for c in candidates if c.lower() in actual_lower),
            None,
        )
        if found is None:
            missing.append(canonical)
        else:
            resolved[canonical] = found
    if missing:
        logger.warning(
            "Columns missing from input parquet (will be NULL in output): %s. "
            "Detected columns: %s",
            missing,
            actual,
        )
    return resolved


def build_company_identity_periodic(
    *,
    raw_dir: Path,
    out_dir: Path,
    overwrite: bool = False,
    duckdb_temp_dir: Path | None = None,
) -> dict[str, Any]:
    """Build the period-aware identity table. Returns audit stats."""
    raw_dir = raw_dir.resolve()
    out_dir = out_dir.resolve()

    if not any(raw_dir.glob("**/*.parquet")):
        raise FileNotFoundError(
            f"No parquet found under {raw_dir}. Run the INSEE bulk ingestion first."
        )

    if out_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"{out_dir} already exists. Pass --overwrite to replace it."
            )
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    glob = str(raw_dir / "**/*.parquet").replace("\\", "/")

    con = duckdb.connect()
    if duckdb_temp_dir is not None:
        duckdb_temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"PRAGMA temp_directory='{duckdb_temp_dir.as_posix()}'")
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA enable_progress_bar")

    cols = _resolve_columns(con, glob)
    logger.info("Resolved input columns: %s", cols)

    def col_or_null(canonical: str, cast_to: str | None = None) -> str:
        actual = cols.get(canonical)
        expr = f'"{actual}"' if actual else "NULL"
        if cast_to:
            expr = f"CAST({expr} AS {cast_to})"
        return f"{expr} AS {canonical}"

    select_clause = ", ".join(
        [
            col_or_null("siren", "VARCHAR"),
            col_or_null("period_start", "DATE"),
            col_or_null("period_end", "DATE"),
            col_or_null("denomination", "VARCHAR"),
            col_or_null("activity_code", "VARCHAR"),
            col_or_null("legal_category_code", "VARCHAR"),
            col_or_null("employee_size_bracket", "VARCHAR"),
            col_or_null("administrative_status", "VARCHAR"),
            col_or_null("creation_date", "DATE"),
        ]
    )

    out_path = (out_dir / "company_identity_periodic.parquet").as_posix()

    logger.info("Reading raw and writing periodic identity to %s", out_path)
    con.execute(
        f"""
        COPY (
            WITH source AS (
                SELECT {select_clause}
                FROM read_parquet('{glob}', union_by_name=true)
                WHERE {cols.get('siren', 'NULL')} IS NOT NULL
            ),
            ordered AS (
                SELECT
                    siren,
                    period_start,
                    LEAD(period_start) OVER (PARTITION BY siren ORDER BY period_start) AS next_period_start,
                    period_end AS source_period_end,
                    denomination,
                    activity_code,
                    legal_category_code,
                    employee_size_bracket,
                    administrative_status,
                    creation_date
                FROM source
                WHERE period_start IS NOT NULL
            )
            SELECT
                siren,
                period_start,
                COALESCE(next_period_start, DATE '9999-12-31') AS period_end,
                denomination,
                activity_code,
                legal_category_code,
                employee_size_bracket,
                administrative_status,
                creation_date,
                next_period_start IS NULL AS is_latest_period
            FROM ordered
        )
        TO '{out_path}'
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 256000)
        """
    )

    # Audit stats
    audit = con.execute(
        f"""
        WITH d AS (SELECT * FROM read_parquet('{out_path}'))
        SELECT
            COUNT(*)                                      AS total_rows,
            COUNT(DISTINCT siren)                         AS unique_sirens,
            SUM(CASE WHEN is_latest_period THEN 1 ELSE 0 END) AS latest_period_rows,
            MIN(period_start)                             AS min_period_start,
            MAX(period_start)                             AS max_period_start,
            AVG(EXTRACT(YEAR FROM period_end) - EXTRACT(YEAR FROM period_start)) AS avg_period_years
        FROM d
        """
    ).fetchone()

    # Overlap detection: a period that starts before the previous period's end
    overlaps = con.execute(
        f"""
        WITH d AS (SELECT * FROM read_parquet('{out_path}')),
        pairs AS (
            SELECT
                siren,
                period_start,
                LAG(period_end) OVER (PARTITION BY siren ORDER BY period_start) AS prev_period_end
            FROM d
        )
        SELECT COUNT(*) FROM pairs WHERE period_start < prev_period_end
        """
    ).fetchone()[0]

    # Gap detection: a period that starts strictly after the previous period's
    # end (period_end is exclusive, so a gap exists iff period_start > prev_end)
    gaps = con.execute(
        f"""
        WITH d AS (SELECT * FROM read_parquet('{out_path}')),
        pairs AS (
            SELECT
                siren,
                period_start,
                LAG(period_end) OVER (PARTITION BY siren ORDER BY period_start) AS prev_period_end
            FROM d
        )
        SELECT COUNT(*) FROM pairs WHERE prev_period_end IS NOT NULL AND period_start > prev_period_end
        """
    ).fetchone()[0]

    stats: dict[str, Any] = {
        "total_rows": int(audit[0]),
        "unique_sirens": int(audit[1]),
        "latest_period_rows": int(audit[2]),
        "min_period_start": str(audit[3]),
        "max_period_start": str(audit[4]),
        "avg_period_years": float(audit[5]) if audit[5] is not None else None,
        "rows_with_overlap": int(overlaps),
        "rows_with_gap": int(gaps),
        "overlap_rate": round(int(overlaps) / max(int(audit[0]), 1), 6),
        "gap_rate": round(int(gaps) / max(int(audit[0]), 1), 6),
        "rows_per_siren": round(int(audit[0]) / max(int(audit[1]), 1), 3),
        "input_columns_resolved": cols,
        "raw_dir": str(raw_dir),
        "out_path": out_path,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }

    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")

    con.close()
    logger.info(
        "Done. rows=%s sirens=%s overlap=%s gap=%s",
        stats["total_rows"],
        stats["unique_sirens"],
        stats["rows_with_overlap"],
        stats["rows_with_gap"],
    )
    return stats


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build period-aware INSEE identity table for V2."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("/data-lake/raw/insee/bulk/stock_unite_legale_historique"),
        help="Directory containing the INSEE historique parquet files.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/data-lake/clean/company_identity_periodic"),
        help="Output directory for the periodic identity parquet.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing output directory if present.",
    )
    parser.add_argument(
        "--duckdb-temp-dir",
        type=Path,
        default=None,
        help="DuckDB temporary directory (useful on Colab to avoid /tmp pressure).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    stats = build_company_identity_periodic(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        overwrite=args.overwrite,
        duckdb_temp_dir=args.duckdb_temp_dir,
    )
    print(json.dumps(stats, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
