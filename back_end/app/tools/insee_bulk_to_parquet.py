"""Export INSEE Sirene stock files to raw Parquet.

This is the preferred full-history INSEE path. Use the API exporter only for
targeted refreshes or smoke checks.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("insee_bulk_to_parquet")

DATASET_TYPES = {
    "stock_unite_legale",
    "stock_unite_legale_historique",
    "stock_etablissement",
    "stock_etablissement_historique",
    "stock_etablissement_liens_succession",
}


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    export_insee_bulk_file(
        input_path=Path(args.input),
        output_base=Path(args.output_dir or settings.DATA_LAKE_DIR),
        dataset_type=args.dataset_type,
        overwrite=args.overwrite,
        count_rows=args.count_rows,
    )


def export_insee_bulk_file(
    *,
    input_path: Path,
    output_base: Path,
    dataset_type: str,
    overwrite: bool,
    count_rows: bool,
) -> Path:
    import duckdb

    if not input_path.exists():
        raise FileNotFoundError(input_path)
    detected_type = _detect_dataset_type(input_path) if dataset_type == "auto" else dataset_type
    output_dir = output_base / "raw" / "insee" / "bulk" / detected_type / _source_stem(input_path)
    _prepare_output_dir(output_dir, output_base, overwrite)

    output_file = output_dir / "part-00001.parquet"
    source_sql = _source_sql(input_path)
    con = duckdb.connect()
    try:
        logger.info("export start input=%s output=%s type=%s", input_path, output_file, detected_type)
        target = _sql_string(str(output_file).replace("\\", "/"))
        con.execute(
            f"""
            COPY ({source_sql})
            TO '{target}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
        rows = None
        if count_rows:
            rows = con.execute(f"SELECT COUNT(*) FROM ({source_sql})").fetchone()[0]
    finally:
        con.close()

    manifest = {
        "source": "INSEE Sirene bulk stock file",
        "input_path": str(input_path),
        "dataset_type": detected_type,
        "output_file": str(output_file),
        "rows": rows,
        "count_rows": count_rows,
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (output_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("export done output=%s rows=%s", output_file, rows)
    return output_dir


def _source_sql(input_path: Path) -> str:
    path = _sql_string(str(input_path).replace("\\", "/"))
    lower = input_path.name.lower()
    if lower.endswith(".parquet"):
        return f"SELECT * FROM read_parquet('{path}', union_by_name=true)"
    if lower.endswith(".csv") or lower.endswith(".csv.gz") or lower.endswith(".txt") or lower.endswith(".txt.gz"):
        return f"SELECT * FROM read_csv_auto('{path}', all_varchar=true, header=true, ignore_errors=true)"
    raise ValueError(
        "unsupported INSEE bulk file format; expected .csv, .csv.gz, .txt, .txt.gz, or .parquet"
    )


def _detect_dataset_type(input_path: Path) -> str:
    name = input_path.name.lower()
    normalized = name.replace("-", "_").replace(".", "_")
    if "lienssuccession" in normalized or "liens_succession" in normalized:
        return "stock_etablissement_liens_succession"
    if "etablissementhistorique" in normalized or "etablissement_historique" in normalized:
        return "stock_etablissement_historique"
    if "unitelegalehistorique" in normalized or "unite_legale_historique" in normalized:
        return "stock_unite_legale_historique"
    if "etablissement" in normalized:
        return "stock_etablissement"
    if "unitelegale" in normalized or "unite_legale" in normalized:
        return "stock_unite_legale"
    raise ValueError(
        f"could not infer INSEE dataset type from {input_path.name}; pass --dataset-type explicitly"
    )


def _source_stem(input_path: Path) -> str:
    name = input_path.name
    for suffix in (".csv.gz", ".txt.gz", ".parquet", ".csv", ".txt"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return input_path.stem


def _prepare_output_dir(path: Path, data_lake_dir: Path, overwrite: bool) -> None:
    if path.exists() and overwrite:
        resolved = path.resolve()
        root = data_lake_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise RuntimeError(f"refusing to delete output outside data lake: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export INSEE Sirene bulk stock file to Parquet.")
    parser.add_argument("--input", required=True, help="Path to an INSEE stock CSV/CSV.GZ/Parquet file.")
    parser.add_argument("--output-dir", help="Base data-lake directory. Defaults to DATA_LAKE_DIR.")
    parser.add_argument(
        "--dataset-type",
        default="auto",
        choices=("auto", *sorted(DATASET_TYPES)),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--count-rows",
        action="store_true",
        help="Count rows for the manifest. Disabled by default to avoid a second full scan.",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
