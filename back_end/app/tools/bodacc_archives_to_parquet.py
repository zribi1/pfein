"""Batch export BODACC archives to Parquet with resumable progress."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.tools.bodacc_to_parquet import export_bodacc_archive_to_parquet

logger = logging.getLogger("bodacc_archives_to_parquet")


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    input_dir = Path(args.input_dir)
    output_base = Path(args.output_dir or settings.DATA_LAKE_DIR) / "raw" / "bodacc"
    progress_path = Path(args.progress_file)
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    archives = _discover_archives(input_dir, set(args.families))
    logger.info(
        "batch export discovered=%d input_dir=%s families=%s",
        len(archives),
        input_dir,
        ",".join(args.families),
    )

    stats = {
        "status": "running",
        "discovered": len(archives),
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "rows": 0,
        "current_file": "",
        "failed_files": [],
        "updated_at": "",
    }
    _write_progress(progress_path, stats)

    for archive in archives:
        stats["current_file"] = str(archive)
        _write_progress(progress_path, stats)

        year = args.year or _infer_year(archive.name)
        output_dir = output_base / args.mode / str(year or "unknown") / archive.stem

        if args.skip_existing and _manifest_done(output_dir / "_manifest.json"):
            stats["skipped"] += 1
            logger.info("skip existing archive=%s output=%s", archive, output_dir)
            _write_progress(progress_path, stats)
            continue

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            rows = export_bodacc_archive_to_parquet(
                input_path=archive,
                output_dir=output_dir,
                mode=args.mode,
                year=year,
                batch_size=args.batch_size,
                include_raw_json=args.include_raw_json,
            )
            stats["processed"] += 1
            stats["rows"] += rows
            logger.info("exported archive=%s rows=%d", archive, rows)
        except Exception as exc:
            stats["failed"] += 1
            stats["failed_files"].append(str(archive))
            logger.exception("failed archive=%s error=%s", archive, exc)

        _write_progress(progress_path, stats)

    stats["status"] = "done" if stats["failed"] == 0 else "done_with_failures"
    stats["current_file"] = ""
    _write_progress(progress_path, stats)
    logger.info(
        "batch export finished status=%s processed=%d skipped=%d failed=%d rows=%d",
        stats["status"],
        stats["processed"],
        stats["skipped"],
        stats["failed"],
        stats["rows"],
    )


def _discover_archives(input_dir: Path, families: set[str]) -> list[Path]:
    archives: list[Path] = []
    candidates = [
        *input_dir.rglob("*.taz"),
        *input_dir.rglob("*.tar"),
        *input_dir.rglob("*.tar.gz"),
    ]
    for path in candidates:
        family = _family_from_name(path.name)
        if family in families:
            archives.append(path)
    return sorted(archives)


def _family_from_name(name: str) -> str:
    value = name.upper().replace("_", "-")
    if value.startswith("PCL-BXA") or value.startswith("PCL-"):
        return "PCL"
    if value.startswith("RCS-B-BXB") or value.startswith("RCSB-BXB"):
        return "RCS-B"
    if value.startswith("RCS-A-BXA") or value.startswith("RCSA-BXA"):
        return "RCS-A"
    if value.startswith("BILAN-BXC"):
        return "BILAN"
    return "other"


def _infer_year(name: str) -> int | None:
    digits = "".join(ch if ch.isdigit() else " " for ch in name).split()
    for token in digits:
        if len(token) >= 4:
            year = int(token[:4])
            if 1900 <= year <= 2100:
                return year
    return None


def _manifest_done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return int(data.get("rows") or 0) > 0


def _write_progress(path: Path, stats: dict[str, Any]) -> None:
    stats["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch export BODACC archives to Parquet.")
    parser.add_argument("--input-dir", required=True, help="Directory containing .taz archives.")
    parser.add_argument(
        "--output-dir",
        help="Base data-lake directory. Defaults to DATA_LAKE_DIR.",
    )
    parser.add_argument("--mode", choices=("current", "historical"), default="current")
    parser.add_argument("--year", type=int)
    parser.add_argument("--families", nargs="+", default=["PCL", "RCS-B"])
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--progress-file", default="/data-lake/raw/bodacc/_batch_progress.json")
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-raw-json", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
