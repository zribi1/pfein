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
    # employee_size_bracket is intentionally NOT mapped here: the INSEE
    # `stock_unite_legale_historique` feed does not publish tranche_effectifs as
    # a time-versioned column. It is only available as a current snapshot in
    # `stock_unite_legale`, which is what V1 used and what caused the leakage
    # this rebuild was meant to fix. Re-introducing the snapshot would defeat
    # V2's purpose, so we drop the feature.
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
    snapshot_dir: Path | None = None,
    overwrite: bool = False,
    duckdb_temp_dir: Path | None = None,
) -> dict[str, Any]:
    """Build the period-aware identity table. Returns audit stats.

    ``creation_date`` is intentionally sourced from the current
    ``stock_unite_legale`` snapshot (``snapshot_dir``) rather than from the
    historique input — INSEE does not publish ``date_creation_unite_legale``
    in the periodic file. Creation date is immutable per SIREN, so
    broadcasting the snapshot value onto every period row is safe (no
    time-varying leak), and matches what the V1 ``build_clean_core_sources``
    already did for the same reason.
    """
    raw_dir = raw_dir.resolve()
    out_dir = out_dir.resolve()
    snapshot_dir = snapshot_dir.resolve() if snapshot_dir is not None else None

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
    # Conservative cap: with a 52 GB Colab High-RAM runtime, leaving 25+ GB
    # free avoids OOM when the kernel's Drive-FUSE page cache balloons while
    # uploading the output parquet. The build only needs ~10–15 GB peak.
    con.execute("PRAGMA memory_limit='25GB'")
    con.execute("PRAGMA enable_progress_bar")
    logger.info("DuckDB configured: threads=%s memory_limit=25GB", threads)

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

    # creation_date broadcast from the current stock_unite_legale snapshot.
    # The historique file does not carry date_creation_unite_legale (V1 hit
    # the same wall — see app/tools/build_clean_core_sources.py:100-116).
    # creation_date is immutable per SIREN, so reading it from the snapshot
    # and broadcasting onto every period row is leak-free.
    snapshot_creation_rows = 0
    snapshot_glob_used: str | None = None
    if snapshot_dir is not None and any(snapshot_dir.glob("**/*.parquet")):
        snapshot_glob = str(snapshot_dir / "**/*.parquet").replace("\\", "/")
        snapshot_glob_used = snapshot_glob
        snap_cols = (
            con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{snapshot_glob}', union_by_name=true) LIMIT 0"
            )
            .df()["column_name"]
            .tolist()
        )
        snap_lower = {c.lower(): c for c in snap_cols}
        siren_actual = next(
            (snap_lower[c] for c in ("siren",) if c in snap_lower), None
        )
        creation_actual = next(
            (
                snap_lower[c]
                for c in (
                    "date_creation_unite_legale",
                    "datecreationunitelegale",
                    "creation_date",
                    "date_creation",
                )
                if c in snap_lower
            ),
            None,
        )
        if siren_actual and creation_actual:
            logger.info(
                "Loading snapshot creation_date from %s (siren=%s, creation=%s)",
                snapshot_dir, siren_actual, creation_actual,
            )
            con.execute(
                f"""
                CREATE TEMP TABLE siren_creation AS
                SELECT
                    TRIM(CAST("{siren_actual}" AS VARCHAR)) AS siren,
                    -- bound to plausible window so 0001-01-01 / 9202-style
                    -- corruption dates don't survive into the output
                    CASE
                        WHEN TRY_CAST("{creation_actual}" AS DATE) BETWEEN {date_lo} AND {date_hi}
                        THEN TRY_CAST("{creation_actual}" AS DATE)
                        ELSE NULL
                    END AS creation_date
                FROM read_parquet('{snapshot_glob}', union_by_name=true)
                WHERE "{siren_actual}" IS NOT NULL
                QUALIFY row_number() OVER (PARTITION BY TRIM(CAST("{siren_actual}" AS VARCHAR))) = 1
                """
            )
            snapshot_creation_rows = con.execute(
                "SELECT COUNT(*) FROM siren_creation WHERE creation_date IS NOT NULL"
            ).fetchone()[0]
            logger.info(
                "Snapshot creation_date loaded: %s SIRENs with non-null creation_date",
                snapshot_creation_rows,
            )
        else:
            logger.warning(
                "Snapshot dir %s present but expected columns missing "
                "(siren=%s, creation=%s). creation_date will fall back to "
                "historique source (likely NULL).",
                snapshot_dir, siren_actual, creation_actual,
            )
            con.execute(
                "CREATE TEMP TABLE siren_creation AS "
                "SELECT NULL::VARCHAR AS siren, NULL::DATE AS creation_date WHERE FALSE"
            )
    else:
        if snapshot_dir is not None:
            logger.warning(
                "Snapshot dir %s has no parquet — creation_date will be NULL.",
                snapshot_dir,
            )
        else:
            logger.warning(
                "No snapshot_dir provided — creation_date will be NULL "
                "(historique does not publish date_creation_unite_legale)."
            )
        con.execute(
            "CREATE TEMP TABLE siren_creation AS "
            "SELECT NULL::VARCHAR AS siren, NULL::DATE AS creation_date WHERE FALSE"
        )

    out_path = (out_dir / "company_identity_periodic.parquet").as_posix()
    logger.info("Writing periodic identity to %s", out_path)
    con.execute(
        f"""
        COPY (
            SELECT
                s.siren,
                s.period_start,
                COALESCE(
                    LEAD(s.period_start) OVER w,
                    DATE '9999-12-31'
                ) AS period_end,
                s.denomination,
                s.activity_code,
                s.legal_category_code,
                s.administrative_status,
                -- snapshot wins (historique is known-NULL for this column);
                -- COALESCE keeps the door open if INSEE ever populates it.
                COALESCE(sc.creation_date, s.creation_date) AS creation_date,
                LEAD(s.period_start) OVER w IS NULL AS is_latest_period
            FROM source s
            LEFT JOIN siren_creation sc USING (siren)
            WINDOW w AS (PARTITION BY s.siren ORDER BY s.period_start)
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

    # Post-write coverage audit for creation_date (the broadcast attribute).
    creation_audit = con.execute(
        f"""
        SELECT
            COUNT(*) AS rows,
            COUNT(creation_date) AS rows_with_creation_date,
            COUNT(DISTINCT CASE WHEN creation_date IS NOT NULL THEN siren END) AS sirens_with_creation_date
        FROM read_parquet('{out_path}')
        """
    ).fetchone()
    rows_with_cd = int(creation_audit[1])
    sirens_with_cd = int(creation_audit[2])

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
        "snapshot_dir": str(snapshot_dir) if snapshot_dir else None,
        "snapshot_glob_used": snapshot_glob_used,
        "snapshot_sirens_with_creation_date": int(snapshot_creation_rows),
        "out_rows_with_creation_date": rows_with_cd,
        "out_sirens_with_creation_date": sirens_with_cd,
        "out_creation_date_coverage": round(rows_with_cd / max(total_rows, 1), 6),
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
        "--snapshot-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing the current INSEE stock_unite_legale "
            "snapshot. Used to broadcast date_creation_unite_legale "
            "(immutable per SIREN) onto every period row, since the "
            "historique file does not publish that column. Recommended: "
            "data-lake/raw/insee/bulk/stock_unite_legale. If omitted, "
            "creation_date will be NULL in the output."
        ),
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
        snapshot_dir=args.snapshot_dir,
        overwrite=args.overwrite,
        duckdb_temp_dir=args.duckdb_temp_dir,
    )
    print(json.dumps(stats, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
