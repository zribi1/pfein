"""Delete locally cached INPI RNE downloads (.zip + optional .part files).

Standalone host-side cleanup. Does not touch MongoDB, does not touch the
ingestion pipeline, does not need Docker. Just walks a directory and removes
files matching the INPI download patterns.

Defaults to dry-run — pass --apply to actually delete.

Examples (run from back_end/):

    # See what would be deleted in your Docker volume on Windows
    python scripts/cleanup_inpi.py --dir C:/PFE_volumes/inpi-data

    # Actually delete every .zip there
    python scripts/cleanup_inpi.py --dir C:/PFE_volumes/inpi-data --apply

    # Only the big ones (>= 500 MiB)
    python scripts/cleanup_inpi.py --dir C:/PFE_volumes/inpi-data --apply --min-mb 500

    # Also remove .part files (only safe when no ingestion is running)
    python scripts/cleanup_inpi.py --dir C:/PFE_volumes/inpi-data --apply --include-partial

If --dir is omitted the script reads INPI_LOCAL_DATA_DIR from app settings,
which is typically a path inside the container ("/app/data/inpi") and will
likely NOT exist on the Windows host — pass --dir explicitly in that case.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger("cleanup_inpi")


def _human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def _resolve_dir(cli_dir: str | None) -> Path:
    if cli_dir:
        return Path(cli_dir)
    try:
        from app.core.config import settings  # noqa: WPS433 (deferred import is intentional)
        return Path(settings.INPI_LOCAL_DATA_DIR)
    except Exception as exc:
        logger.warning("could not load app settings (%s); pass --dir explicitly", exc)
        raise SystemExit(2)


def delete_inpi_files(
    base_dir: Path,
    *,
    apply: bool = False,
    min_bytes: int = 0,
    include_partial: bool = False,
) -> tuple[int, int]:
    """Walk `base_dir` recursively and remove .zip (and optionally .part) files.

    Returns ``(file_count, bytes_freed)``. With ``apply=False`` nothing is deleted —
    the function just reports what it *would* remove.
    """
    if not base_dir.exists():
        logger.warning("base dir does not exist: %s", base_dir)
        return 0, 0
    if not base_dir.is_dir():
        logger.error("not a directory: %s", base_dir)
        return 0, 0

    patterns = ["*.zip"]
    if include_partial:
        patterns += ["*.part", "*.zip.part"]

    seen: set[Path] = set()
    candidates: list[Path] = []
    for pat in patterns:
        for path in base_dir.rglob(pat):
            if path in seen:
                continue
            seen.add(path)
            candidates.append(path)

    count = 0
    freed = 0
    for path in candidates:
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            logger.warning("cannot stat %s: %s", path, exc)
            continue
        if min_bytes and size < min_bytes:
            continue
        action = "DELETE" if apply else "WOULD DELETE"
        logger.info("%s %s (%s)", action, path, _human(size))
        if apply:
            try:
                path.unlink()
            except OSError as exc:
                logger.error("failed to delete %s: %s", path, exc)
                continue
        count += 1
        freed += size

    logger.info(
        "summary: %d file(s), %s %s (base=%s)",
        count,
        _human(freed),
        "freed" if apply else "would be freed",
        base_dir,
    )
    return count, freed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete locally cached INPI RNE downloads (.zip [+ .part])."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete files (default: dry-run).",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Base directory to clean (default: settings.INPI_LOCAL_DATA_DIR).",
    )
    parser.add_argument(
        "--min-mb",
        type=float,
        default=0.0,
        help="Only delete files >= N MiB (default: 0 = no minimum).",
    )
    parser.add_argument(
        "--include-partial",
        action="store_true",
        help="Also delete .part files (only safe when no ingestion is running).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    base = _resolve_dir(args.dir)
    logger.info(
        "scanning %s (apply=%s, min_mb=%s, include_partial=%s)",
        base, args.apply, args.min_mb, args.include_partial,
    )
    delete_inpi_files(
        base,
        apply=args.apply,
        min_bytes=int(args.min_mb * 1024 * 1024),
        include_partial=args.include_partial,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
