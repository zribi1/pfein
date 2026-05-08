"""Export INPI RNE ZIP/JSON files to chunked Parquet.

This is the raw-file/data-lake path for bulk INPI data. It reuses the same
record iterator already validated by Mongo ingestion, but writes batch files
instead of inserting millions of nested documents into MongoDB.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.config import settings
from app.services.company_identity_helpers import extract_denomination, extract_siren
from app.services.inpi_ingestion_service import (
    InpiFileTarget,
    InpiIngestionService,
    _iter_records_zip,
    _record_key,
)

logger = logging.getLogger("inpi_to_parquet")


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    target = _target_from_args(args, input_path)
    output_base = Path(args.output_dir or settings.DATA_LAKE_DIR) / "raw" / "inpi"
    output_dir = output_base / target.category / target.niveau / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "export start input=%s output=%s category=%s niveau=%s batch_size=%d include_raw_json=%s",
        input_path,
        output_dir,
        target.category,
        target.niveau,
        args.batch_size,
        args.include_raw_json,
    )

    started_at = datetime.now(tz=timezone.utc)
    total_rows = export_inpi_file_to_parquet(
        input_path=input_path,
        output_dir=output_dir,
        target=target,
        batch_size=args.batch_size,
        max_records=args.max_records,
        include_raw_json=args.include_raw_json,
    )
    elapsed = datetime.now(tz=timezone.utc) - started_at
    logger.info("export done rows=%d elapsed=%s output=%s", total_rows, elapsed, output_dir)


def export_inpi_file_to_parquet(
    *,
    input_path: Path,
    output_dir: Path,
    target: InpiFileTarget,
    batch_size: int = 100_000,
    max_records: int | None = None,
    include_raw_json: bool = True,
) -> int:
    total = 0
    part = 0
    batch: list[dict[str, Any]] = []

    for raw in _iter_input_records(input_path):
        row = _row_from_record(raw, target, input_path.name, include_raw_json)
        if row is None:
            continue

        batch.append(row)
        if len(batch) >= batch_size:
            part += 1
            _write_batch(batch, output_dir, part)
            total += len(batch)
            logger.info("wrote part=%05d batch_rows=%d total_rows=%d", part, len(batch), total)
            _write_progress(output_dir, input_path, target, total, part, include_raw_json, done=False)
            batch.clear()

        if max_records is not None and total + len(batch) >= max_records:
            break

    if batch:
        part += 1
        _write_batch(batch, output_dir, part)
        total += len(batch)
        logger.info("wrote part=%05d batch_rows=%d total_rows=%d", part, len(batch), total)
        _write_progress(output_dir, input_path, target, total, part, include_raw_json, done=False)

    manifest = {
        "input_path": str(input_path),
        "category": target.category,
        "niveau": target.niveau,
        "rows": total,
        "parts": part,
        "include_raw_json": include_raw_json,
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (output_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_progress(output_dir, input_path, target, total, part, include_raw_json, done=True)
    return total


def _iter_input_records(input_path: Path) -> Iterable[dict[str, Any]]:
    if input_path.name.lower().endswith(".zip"):
        yield from _iter_records_zip(input_path)
        return
    raise ValueError(f"unsupported INPI input file: {input_path}")


def _row_from_record(
    raw: dict[str, Any],
    target: InpiFileTarget,
    source_file: str,
    include_raw_json: bool,
) -> dict[str, Any] | None:
    siren = extract_siren("inpi", raw)
    if siren is None:
        return None

    row: dict[str, Any] = {
        "record_key": _record_key(target, raw),
        "siren": siren,
        "denomination": extract_denomination("inpi", raw),
        "category": target.category,
        "niveau": target.niveau,
        "source_file": source_file,
        "inpi_id": _as_str(raw.get("id")),
        "updated_at_source": _as_str(raw.get("updatedAt")),
        "date_depot": _as_str(raw.get("dateDepot")),
        "date_cloture": _as_str(raw.get("dateCloture")),
        "type_bilan": _as_str(raw.get("typeBilan")),
        "confidentiality": _as_str(raw.get("confidentiality")),
        "deleted": _as_bool(raw.get("deleted")),
        "exported_at": datetime.now(tz=timezone.utc),
    }
    if include_raw_json:
        row["raw_json"] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), default=str)
    return row


def _write_batch(rows: list[dict[str, Any]], output_dir: Path, part: int) -> None:
    table = pa.Table.from_pylist(rows, schema=_schema("raw_json" in rows[0]))
    target = output_dir / f"part-{part:05d}.parquet"
    tmp = target.with_suffix(".parquet.tmp")
    pq.write_table(
        table,
        tmp,
        compression="zstd",
        compression_level=6,
        use_dictionary=True,
        write_statistics=True,
    )
    tmp.replace(target)


def _write_progress(
    output_dir: Path,
    input_path: Path,
    target: InpiFileTarget,
    rows: int,
    parts: int,
    include_raw_json: bool,
    *,
    done: bool,
) -> None:
    progress = {
        "input_path": str(input_path),
        "category": target.category,
        "niveau": target.niveau,
        "rows": rows,
        "parts": parts,
        "include_raw_json": include_raw_json,
        "done": done,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    tmp = output_dir / "_progress.json.tmp"
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(output_dir / "_progress.json")


def _schema(include_raw_json: bool) -> pa.Schema:
    fields = [
        pa.field("record_key", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("denomination", pa.string()),
        pa.field("category", pa.string()),
        pa.field("niveau", pa.string()),
        pa.field("source_file", pa.string()),
        pa.field("inpi_id", pa.string()),
        pa.field("updated_at_source", pa.string()),
        pa.field("date_depot", pa.string()),
        pa.field("date_cloture", pa.string()),
        pa.field("type_bilan", pa.string()),
        pa.field("confidentiality", pa.string()),
        pa.field("deleted", pa.bool_()),
        pa.field("exported_at", pa.timestamp("us", tz="UTC")),
    ]
    if include_raw_json:
        fields.append(pa.field("raw_json", pa.string()))
    return pa.schema(fields)


def _target_from_args(args: argparse.Namespace, input_path: Path) -> InpiFileTarget:
    if args.category and args.niveau:
        return InpiFileTarget(
            category=args.category,
            niveau=args.niveau,
            collection="parquet",
        )
    detected = InpiIngestionService._target_for_path(input_path.name)
    if detected is None:
        raise ValueError(
            "could not infer INPI file category; pass --category and --niveau explicitly"
        )
    return detected


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export INPI RNE bulk data to Parquet.")
    parser.add_argument("--input", required=True, help="Path to an INPI .zip file.")
    parser.add_argument(
        "--output-dir",
        help=(
            "Base data-lake directory. Defaults to DATA_LAKE_DIR and writes under "
            "<DATA_LAKE_DIR>/raw/inpi/..."
        ),
    )
    parser.add_argument(
        "--category",
        choices=("comptes_annuels", "formalites"),
        help="Override detected category.",
    )
    parser.add_argument(
        "--niveau",
        choices=("standard", "niveau1"),
        help="Override detected level.",
    )
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--max-records", type=int)
    parser.add_argument(
        "--include-raw-json",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Store the full source record as compressed JSON text. Disabled by default "
            "because the original ZIP is kept as the raw source of truth."
        ),
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
