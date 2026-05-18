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
import os
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
    threads = max(os.cpu_count() or 4, 4)
    con.execute(f"PRAGMA threads={threads}")
    con.execute("PRAGMA memory_limit='40GB'")
    con.execute("PRAGMA enable_progress_bar")
    logger.info("DuckDB configured: threads=%s memory_limit=40GB", threads)

    cols = _resolve_columns(con, glob)
    logger.info("Resolved input columns: %s", cols)

    def col_or_null(canonical: str, cast_to: str | None = None) -> str:
        actual = cols.get(canonical)
        expr = f'"{actual}"' if actual else "NULL"
        if cast_to:
            expr = f"CAST({expr} AS {cast_to})"
        return f"{expr} AS {canonical}"

    # Cache the projected input as an in-memory table. We keep
    # `source_period_end` (the raw INSEE period_end) so the audit can validate
    # *input* contiguity. The output's `period_end` is synthesized via LEAD and
    # is contiguous by construction, so auditing the output would be tautological.
    period_end_actual = cols.get("period_end")
    source_period_end_expr = (
        f'CAST("{period_end_actual}" AS DATE) AS source_period_end'
        if period_end_actual
        else "CAST(NULL AS DATE) AS source_period_end"
    )
    source_select = ", ".join(
        [
            col_or_null("siren", "VARCHAR"),
            col_or_null("period_start", "DATE"),
            source_period_end_expr,
            col_or_null("denomination", "VARCHAR"),
            col_or_null("activity_code", "VARCHAR"),
            col_or_null("legal_category_code", "VARCHAR"),
            col_or_null("employee_size_bracket", "VARCHAR"),
            col_or_null("administrative_status", "VARCHAR"),
            col_or_null("creation_date", "DATE"),
        ]
    )

    # Date sanity filter. INSEE bulk data contains placeholder/corruption dates
    # (e.g. 0001-01-01, year 9202) that would poison downstream temporal joins.
    # We clip to a plausible SIRENE coverage window and report how many rows
    # were dropped.
    period_start_col = cols.get("period_start")
    date_lo = "DATE '1900-01-01'"
    date_hi = "DATE '2030-01-01'"

    if period_start_col:
        invalid_date_count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{glob}')
            WHERE {cols.get('siren', 'NULL')} IS NOT NULL
              AND "{period_start_col}" IS NOT NULL
              AND ("{period_start_col}" < {date_lo}
                OR "{period_start_col}" > {date_hi})
            """
        ).fetchone()[0]
        logger.info(
            "Date sanity filter will drop %s rows outside [%s, %s]",
            invalid_date_count, date_lo, date_hi,
        )
    else:
        invalid_date_count = 0

    logger.info("Loading source parquet into in-memory cache")
    date_predicate = (
        f' AND "{period_start_col}" BETWEEN {date_lo} AND {date_hi}'
        if period_start_col
        else ""
    )
    con.execute(
        f"""
        CREATE TEMP TABLE source AS
        SELECT {source_select}
        FROM read_parquet('{glob}')
        WHERE {cols.get('siren', 'NULL')} IS NOT NULL
          AND {cols.get('period_start', 'NULL')} IS NOT NULL
          {date_predicate}
        """
    )

    out_path = (out_dir / "company_identity_periodic.parquet").as_posix()
    logger.info("Writing periodic identity to %s", out_path)
    con.execute(
        f"""
        COPY (
            SELECT
                siren,
                period_start,
                COALESCE(
                    LEAD(period_start) OVER w,
                    DATE '9999-12-31'
                ) AS period_end,
                denomination,
                activity_code,
                legal_category_code,
                employee_size_bracket,
                administrative_status,
                creation_date,
                LEAD(period_start) OVER w IS NULL AS is_latest_period
            FROM source
            WINDOW w AS (PARTITION BY siren ORDER BY period_start)
        )
        TO '{out_path}'
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 256000)
        """
    )

    # Single combined audit pass on the cached input table. Overlap/gap are
    # measured against `source_period_end` (the raw INSEE field), not the
    # synthesized output `period_end`.
    #
    # INSEE convention: `date_fin` is INCLUSIVE (the last day the state was
    # active). The next period starts on `date_fin + 1 day`. So:
    #   - overlap = period_start <= prev_source_end
    #   - gap     = period_start >  prev_source_end + 1 day
    #   - contiguous = period_start == prev_source_end + 1 day
    audit = con.execute(
        """
        WITH audit_base AS (
            SELECT
                siren,
                period_start,
                source_period_end,
                LAG(source_period_end) OVER w AS prev_source_end,
                LEAD(period_start)     OVER w AS next_period_start
            FROM source
            WINDOW w AS (PARTITION BY siren ORDER BY period_start)
        )
        SELECT
            COUNT(*)                                                          AS total_rows,
            COUNT(DISTINCT siren)                                             AS unique_sirens,
            SUM(CASE WHEN next_period_start IS NULL THEN 1 ELSE 0 END)        AS latest_period_rows,
            MIN(period_start)                                                 AS min_period_start,
            MAX(period_start)                                                 AS max_period_start,
            AVG(EXTRACT(YEAR FROM next_period_start) - EXTRACT(YEAR FROM period_start))
                FILTER (WHERE next_period_start IS NOT NULL)                  AS avg_period_years,
            SUM(CASE WHEN prev_source_end IS NOT NULL
                      AND period_start <= prev_source_end
                     THEN 1 ELSE 0 END)                                       AS rows_with_overlap,
            SUM(CASE WHEN prev_source_end IS NOT NULL
                      AND period_start  > prev_source_end + INTERVAL 1 DAY
                     THEN 1 ELSE 0 END)                                       AS rows_with_gap,
            SUM(CASE WHEN prev_source_end IS NOT NULL
                      AND period_start = prev_source_end + INTERVAL 1 DAY
                     THEN 1 ELSE 0 END)                                       AS rows_contiguous,
            SUM(CASE WHEN source_period_end IS NULL THEN 1 ELSE 0 END)        AS rows_with_null_source_period_end
        FROM audit_base
        """
    ).fetchone()

    total_rows = int(audit[0])
    unique_sirens = int(audit[1])
    overlaps = int(audit[6])
    gaps = int(audit[7])
    contiguous = int(audit[8])
    non_first_rows = total_rows - unique_sirens  # rows that have a predecessor

    stats: dict[str, Any] = {
        "total_rows": total_rows,
        "unique_sirens": unique_sirens,
        "latest_period_rows": int(audit[2]),
        "min_period_start": str(audit[3]),
        "max_period_start": str(audit[4]),
        "avg_period_years": float(audit[5]) if audit[5] is not None else None,
        "rows_with_overlap": overlaps,
        "rows_with_gap": gaps,
        "rows_contiguous": contiguous,
        "rows_with_null_source_period_end": int(audit[9]),
        "rows_dropped_invalid_date": int(invalid_date_count),
        "date_sanity_lo": "1900-01-01",
        "date_sanity_hi": "2030-01-01",
        "overlap_rate": round(overlaps / max(total_rows, 1), 6),
        "gap_rate": round(gaps / max(total_rows, 1), 6),
        # Among rows that have a predecessor (non-first rows), what fraction
        # are perfectly contiguous? This is the metric to compare against the
        # roadmap's "≥95% SIRENs with contiguous periods" criterion.
        "contiguous_rate_non_first": round(contiguous / max(non_first_rows, 1), 6),
        "rows_per_siren": round(total_rows / max(unique_sirens, 1), 3),
        "audit_basis": "input_parquet_source_period_end_inclusive",
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
