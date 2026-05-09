"""Build clean, grouped Parquet datasets from raw INSEE, INPI, and BODACC exports."""

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

logger = logging.getLogger("build_clean_core_sources")


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    build_clean_core_sources(
        data_lake_dir=Path(args.data_lake_dir or settings.DATA_LAKE_DIR),
        overwrite=args.overwrite,
        max_rows=args.max_rows,
    )


def build_clean_core_sources(
    *,
    data_lake_dir: Path,
    overwrite: bool,
    max_rows: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Normalize raw source-oriented exports into stable clean datasets.

    Raw exports intentionally stay source-file/run oriented for traceability.
    This builder creates the consumption layer used by feature building:
    company identity, legal events, INPI formalities, and INPI annual accounts.
    """

    import duckdb

    outputs: dict[str, dict[str, Any]] = {}
    con = duckdb.connect()
    try:
        _configure_duckdb(con, data_lake_dir)
        logger.info("clean core build started data_lake=%s overwrite=%s", data_lake_dir, overwrite)
        outputs["company_identity"] = _build_company_identity(con, data_lake_dir, overwrite, max_rows)
        outputs["legal_events"] = _build_legal_events(con, data_lake_dir, overwrite, max_rows)
        outputs["formalities_events"] = _build_formalities_events(con, data_lake_dir, overwrite, max_rows)
        outputs["annual_accounts"] = _build_annual_accounts(con, data_lake_dir, overwrite, max_rows)
        logger.info("clean core build finished datasets=%s", ",".join(outputs))
    finally:
        con.close()
    return outputs


def _build_company_identity(
    con: Any,
    data_lake_dir: Path,
    overwrite: bool,
    max_rows: int | None,
) -> dict[str, Any]:
    raw_root = _first_dataset(
        data_lake_dir / "raw" / "insee" / "unites_legales",
        data_lake_dir / "raw" / "insee" / "bulk" / "stock_unite_legale",
    )
    output_dir = data_lake_dir / "clean" / "company_identity"
    if raw_root is None:
        expected_root = data_lake_dir / "raw" / "insee"
        return _write_skipped_manifest(output_dir, "company_identity", expected_root)

    _prepare_output_dir(output_dir, data_lake_dir, overwrite)
    path = _duckdb_glob(raw_root)
    available = _parquet_columns(con, path)
    limit_sql = f"LIMIT {int(max_rows)}" if max_rows else ""
    output_file = output_dir / "company_identity.parquet"
    logger.info("clean dataset=company_identity reading raw_root=%s", raw_root)

    siren = _coalesce_expr(available, ("siren",), "VARCHAR")
    nic_siege = _coalesce_expr(available, ("nic_siege",), "VARCHAR")
    source_updated = _coalesce_expr(available, ("source_updated_at", "exported_at"), "TIMESTAMP")
    exported_at = _coalesce_expr(available, ("exported_at",), "TIMESTAMP")
    status_period_start = _coalesce_expr(
        available,
        ("last_insee_period_start", "status_period_start", "date_debut_periode"),
        "DATE",
    )

    logger.info("clean dataset=company_identity writing output=%s", output_file)
    con.execute(
        f"""
        COPY (
            WITH normalized AS (
                SELECT
                    {siren} AS siren,
                    {_coalesce_expr(available, ("company_name", "denomination", "denomination_periode", "nom"), "VARCHAR")} AS company_name,
                    {_coalesce_expr(available, ("activity_code", "activite_principale", "activite_principale_periode"), "VARCHAR")} AS activity_code,
                    {_coalesce_expr(available, ("legal_category_code", "categorie_juridique"), "VARCHAR")} AS legal_category_code,
                    {_coalesce_expr(available, ("administrative_status", "etat_administratif"), "VARCHAR")} AS administrative_status,
                    {_coalesce_expr(available, ("creation_date", "date_creation"), "DATE")} AS creation_date,
                    {_coalesce_expr(available, ("closure_date", "date_cessation", "date_cessation_activite"), "DATE")} AS closure_date,
                    {status_period_start} AS status_period_start,
                    {_coalesce_expr(available, ("employee_size_bracket", "tranche_effectifs"), "VARCHAR")} AS employee_size_bracket,
                    {_coalesce_expr(available, ("employee_size_year", "annee_effectifs"), "INTEGER")} AS employee_size_year,
                    CASE
                        WHEN length({siren}) = 9 AND length({nic_siege}) = 5 THEN {siren} || {nic_siege}
                        ELSE NULL
                    END AS head_office_siret,
                    {source_updated} AS source_updated_at,
                    {_coalesce_expr(available, ("filename", "source_file"), "VARCHAR")} AS source_file,
                    {exported_at} AS exported_at
                FROM read_parquet('{_sql_string(path)}', union_by_name=true, filename=true)
                WHERE {siren} IS NOT NULL
            ),
            deduped AS (
                SELECT *
                FROM normalized
                QUALIFY row_number() OVER (
                    PARTITION BY siren
                    ORDER BY source_updated_at DESC NULLS LAST, status_period_start DESC NULLS LAST, exported_at DESC NULLS LAST
                ) = 1
            )
            SELECT * FROM deduped
            {limit_sql}
        )
        TO '{_sql_string(str(output_file).replace("\\", "/"))}'
        (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE TRUE)
        """
    )
    rows = _count_output(con, output_dir)
    return _write_manifest(
        output_dir,
        {
            "dataset": "company_identity",
            "rows": rows,
            "raw_root": str(raw_root),
            "schema_version": 1,
            "grain": "one row per SIREN",
        },
    )


def _build_legal_events(
    con: Any,
    data_lake_dir: Path,
    overwrite: bool,
    max_rows: int | None,
) -> dict[str, Any]:
    raw_root = data_lake_dir / "raw" / "bodacc"
    output_dir = data_lake_dir / "clean" / "legal_events"
    if not _has_parquet(raw_root):
        return _write_skipped_manifest(output_dir, "legal_events", raw_root)

    _prepare_output_dir(output_dir, data_lake_dir, overwrite)
    path = _duckdb_glob(raw_root)
    available = _parquet_columns(con, path)
    limit_sql = f"LIMIT {int(max_rows)}" if max_rows else ""
    siren = _coalesce_expr(available, ("siren",), "VARCHAR")
    event_date = _coalesce_expr(available, ("event_date", "eventDate", "date_parution", "dateParution"), "DATE")
    event_category = _coalesce_expr(available, ("event_category", "eventCategory", "bodacc_family", "bodaccFamily"), "VARCHAR")
    logger.info("clean dataset=legal_events reading raw_root=%s", raw_root)

    logger.info("clean dataset=legal_events writing partitioned output=%s", output_dir)
    con.execute(
        f"""
        COPY (
            SELECT
                {siren} AS siren,
                {event_date} AS event_date,
                YEAR({event_date})::INTEGER AS event_year,
                COALESCE({event_category}, 'unknown') AS event_category,
                {_coalesce_expr(available, ("event_type", "eventType", "jugement_nature", "jugementNature"), "VARCHAR")} AS event_type,
                {_coalesce_expr(available, ("is_risk_event", "isRiskEvent"), "BOOLEAN")} AS is_risk_event,
                {_coalesce_expr(available, ("is_radiation", "isRadiation"), "BOOLEAN")} AS is_radiation,
                {_coalesce_expr(available, ("flag_liquidation", "liquidation"), "BOOLEAN")} AS flag_liquidation,
                {_coalesce_expr(available, ("flag_redressement", "redressement"), "BOOLEAN")} AS flag_redressement,
                {_coalesce_expr(available, ("flag_sauvegarde", "sauvegarde"), "BOOLEAN")} AS flag_sauvegarde,
                {_coalesce_expr(available, ("flag_procedure_collective", "procedureCollective"), "BOOLEAN")} AS flag_procedure_collective,
                {_coalesce_expr(available, ("flag_cessation_paiement", "cessationPaiement"), "BOOLEAN")} AS flag_cessation_paiement,
                {_coalesce_expr(available, ("nojo",), "VARCHAR")} AS nojo,
                {_coalesce_expr(available, ("denomination",), "VARCHAR")} AS denomination,
                {_coalesce_expr(available, ("archive_name", "filename", "source_file"), "VARCHAR")} AS source_file,
                {_coalesce_expr(available, ("archive_member_name",), "VARCHAR")} AS source_member,
                {_coalesce_expr(available, ("exported_at",), "TIMESTAMP")} AS exported_at
            FROM read_parquet('{_sql_string(path)}', union_by_name=true, filename=true)
            WHERE {siren} IS NOT NULL
              AND {event_date} IS NOT NULL
            {limit_sql}
        )
        TO '{_sql_string(str(output_dir).replace("\\", "/"))}'
        (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (event_year, event_category), OVERWRITE_OR_IGNORE TRUE)
        """
    )
    rows = _count_output(con, output_dir)
    return _write_manifest(
        output_dir,
        {
            "dataset": "legal_events",
            "rows": rows,
            "raw_root": str(raw_root),
            "schema_version": 1,
            "grain": "one row per BODACC announcement",
            "partitioned_by": ["event_year", "event_category"],
        },
    )


def _build_formalities_events(
    con: Any,
    data_lake_dir: Path,
    overwrite: bool,
    max_rows: int | None,
) -> dict[str, Any]:
    raw_root = data_lake_dir / "raw" / "inpi" / "formalites"
    output_dir = data_lake_dir / "clean" / "formalities_events"
    if not _has_parquet(raw_root):
        return _write_skipped_manifest(output_dir, "formalities_events", raw_root)

    _prepare_output_dir(output_dir, data_lake_dir, overwrite)
    path = _duckdb_glob(raw_root)
    available = _parquet_columns(con, path)
    limit_sql = f"LIMIT {int(max_rows)}" if max_rows else ""
    siren = _coalesce_expr(available, ("siren",), "VARCHAR")
    event_date = _coalesce_expr(available, ("event_date", "date_depot", "dateDepot", "updated_at_source"), "DATE")
    logger.info("clean dataset=formalities_events reading raw_root=%s", raw_root)

    logger.info("clean dataset=formalities_events writing partitioned output=%s", output_dir)
    con.execute(
        f"""
        COPY (
            SELECT
                {siren} AS siren,
                {event_date} AS event_date,
                YEAR({event_date})::INTEGER AS event_year,
                {_coalesce_expr(available, ("event_type", "type_formalite", "formality_type", "category"), "VARCHAR")} AS event_type,
                {_coalesce_expr(available, ("event_text", "formality_label", "denomination", "category"), "VARCHAR")} AS event_text,
                {_coalesce_expr(available, ("niveau",), "VARCHAR")} AS niveau,
                {_coalesce_expr(available, ("record_key",), "VARCHAR")} AS record_key,
                {_coalesce_expr(available, ("inpi_id",), "VARCHAR")} AS inpi_id,
                {_coalesce_expr(available, ("source_file", "filename"), "VARCHAR")} AS source_file,
                {_coalesce_expr(available, ("exported_at",), "TIMESTAMP")} AS exported_at
            FROM read_parquet('{_sql_string(path)}', union_by_name=true, filename=true)
            WHERE {siren} IS NOT NULL
              AND {event_date} IS NOT NULL
            {limit_sql}
        )
        TO '{_sql_string(str(output_dir).replace("\\", "/"))}'
        (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (event_year, niveau), OVERWRITE_OR_IGNORE TRUE)
        """
    )
    rows = _count_output(con, output_dir)
    return _write_manifest(
        output_dir,
        {
            "dataset": "formalities_events",
            "rows": rows,
            "raw_root": str(raw_root),
            "schema_version": 1,
            "grain": "one row per INPI formality record",
            "partitioned_by": ["event_year", "niveau"],
        },
    )


def _build_annual_accounts(
    con: Any,
    data_lake_dir: Path,
    overwrite: bool,
    max_rows: int | None,
) -> dict[str, Any]:
    raw_root = data_lake_dir / "raw" / "inpi" / "comptes_annuels"
    output_dir = data_lake_dir / "clean" / "annual_accounts"
    if not _has_parquet(raw_root):
        return _write_skipped_manifest(output_dir, "annual_accounts", raw_root)

    _prepare_output_dir(output_dir, data_lake_dir, overwrite)
    path = _duckdb_glob(raw_root)
    available = _parquet_columns(con, path)
    limit_sql = f"LIMIT {int(max_rows)}" if max_rows else ""
    siren = _coalesce_expr(available, ("siren",), "VARCHAR")
    filing_date = _coalesce_expr(available, ("filing_date", "date_depot", "dateDepot", "updated_at_source"), "DATE")
    closing_date = _coalesce_expr(available, ("closing_date", "date_cloture", "dateCloture"), "DATE")
    logger.info("clean dataset=annual_accounts reading raw_root=%s", raw_root)

    logger.info("clean dataset=annual_accounts writing partitioned output=%s", output_dir)
    con.execute(
        f"""
        COPY (
            SELECT
                {siren} AS siren,
                {filing_date} AS filing_date,
                {closing_date} AS closing_date,
                COALESCE(YEAR({filing_date}), YEAR({closing_date}))::INTEGER AS filing_year,
                {_coalesce_expr(available, ("account_type", "type_bilan", "typeBilan"), "VARCHAR")} AS account_type,
                {_coalesce_expr(available, ("confidentiality",), "VARCHAR")} AS confidentiality,
                {_coalesce_expr(available, ("niveau",), "VARCHAR")} AS niveau,
                {_coalesce_expr(available, ("record_key",), "VARCHAR")} AS record_key,
                {_coalesce_expr(available, ("inpi_id",), "VARCHAR")} AS inpi_id,
                {_coalesce_expr(available, ("deleted",), "BOOLEAN")} AS deleted,
                {_coalesce_expr(available, ("source_file", "filename"), "VARCHAR")} AS source_file,
                {_coalesce_expr(available, ("exported_at",), "TIMESTAMP")} AS exported_at
            FROM read_parquet('{_sql_string(path)}', union_by_name=true, filename=true)
            WHERE {siren} IS NOT NULL
              AND ({filing_date} IS NOT NULL OR {closing_date} IS NOT NULL)
            {limit_sql}
        )
        TO '{_sql_string(str(output_dir).replace("\\", "/"))}'
        (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (filing_year, niveau), OVERWRITE_OR_IGNORE TRUE)
        """
    )
    rows = _count_output(con, output_dir)
    return _write_manifest(
        output_dir,
        {
            "dataset": "annual_accounts",
            "rows": rows,
            "raw_root": str(raw_root),
            "schema_version": 1,
            "grain": "one row per INPI annual account filing",
            "partitioned_by": ["filing_year", "niveau"],
        },
    )


def _coalesce_expr(available: set[str], candidates: tuple[str, ...], sql_type: str) -> str:
    exprs = []
    for candidate in candidates:
        match = _find_column(available, candidate)
        if match:
            expr = f"TRY_CAST({_quote_ident(match)} AS {sql_type})"
            if sql_type == "VARCHAR":
                expr = f"NULLIF(TRIM({expr}), '')"
            exprs.append(expr)
    if not exprs:
        return f"NULL::{sql_type}"
    if len(exprs) == 1:
        return exprs[0]
    return f"COALESCE({', '.join(exprs)})"


def _find_column(available: set[str], candidate: str) -> str | None:
    lowered = {column.lower(): column for column in available}
    return lowered.get(candidate.lower())


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _parquet_columns(con: Any, glob_path: str) -> set[str]:
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{_sql_string(glob_path)}', union_by_name=true, filename=true)"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _has_parquet(root: Path) -> bool:
    return root.exists() and any(root.rglob("*.parquet"))


def _first_dataset(*roots: Path) -> Path | None:
    for root in roots:
        if _has_parquet(root):
            return root
    return None


def _duckdb_glob(root: Path) -> str:
    return str(root / "**" / "*.parquet").replace("\\", "/")


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _prepare_output_dir(path: Path, data_lake_dir: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise FileExistsError(f"clean output already exists: {path}")
        resolved = path.resolve()
        root = data_lake_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise RuntimeError(f"refusing to delete output outside data lake: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _count_output(con: Any, output_dir: Path) -> int:
    if not _has_parquet(output_dir):
        return 0
    return int(
        con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{_sql_string(_duckdb_glob(output_dir))}', union_by_name=true, hive_partitioning=true)"
        ).fetchone()[0]
    )


def _write_manifest(output_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    payload = {
        **payload,
        "source_found": True,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("clean dataset=%s rows=%s output=%s", payload["dataset"], payload["rows"], output_dir)
    return payload


def _write_skipped_manifest(output_dir: Path, dataset: str, raw_root: Path) -> dict[str, Any]:
    payload = {
        "dataset": dataset,
        "rows": 0,
        "raw_root": str(raw_root),
        "source_found": False,
        "skipped_reason": "no raw Parquet found",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("clean dataset=%s skipped: no raw Parquet found under %s", dataset, raw_root)
    return payload


def _configure_duckdb(con: Any, data_lake_dir: Path) -> None:
    temp_dir = _duckdb_temp_dir(data_lake_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{_sql_string(str(temp_dir).replace('\\', '/'))}'")
    con.execute("PRAGMA enable_progress_bar")


def _duckdb_temp_dir(data_lake_dir: Path) -> Path:
    configured = os.environ.get("DUCKDB_TEMP_DIRECTORY")
    if configured:
        return Path(configured)
    if str(data_lake_dir).startswith("/content/drive/"):
        return Path("/content/pfein_duckdb_tmp")
    return data_lake_dir / "tmp" / "duckdb"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build clean INSEE/INPI/BODACC Parquet datasets.")
    parser.add_argument("--data-lake-dir", help="Defaults to DATA_LAKE_DIR.")
    parser.add_argument("--max-rows", type=int, help="Optional smoke-test cap per clean dataset.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
