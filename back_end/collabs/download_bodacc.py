from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
import sys
from pathlib import Path

from common import (
    DEFAULT_DRIVE_ROOT,
    download_resumable,
    install_deps,
    pipeline_env,
    seed_file_from_drive,
    storage_paths,
    sync_file_to_drive,
    sync_tree_to_drive,
    run,
)


CURRENT_BASE_URL = "https://echanges.dila.gouv.fr/OPENDATA/BODACC/FluxAnneeCourante/"
HISTORICAL_BASE_URL = "https://echanges.dila.gouv.fr/OPENDATA/BODACC/FluxHistorique/"
ARCHIVE_EXTENSIONS = (".taz", ".tar", ".tar.gz")
FULL_YEAR_FAMILY = "FULL"


@dataclass(frozen=True)
class BodaccRemoteArchive:
    url: str
    year: int | None
    family: str


class HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    drive_p, work_p = storage_paths(args.drive_root, args.work_dir)
    p = work_p
    if args.install_deps:
        install_deps(repo_dir)

    bodacc_dir = p["source_archives"] / "bodacc"
    drive_bodacc_dir = drive_p["source_archives"] / "bodacc"
    if args.download:
        print(
            "[bodacc] download phase start "
            f"mode={args.mode} families={args.families} years={args.start_year or '*'}-{args.end_year or '*'}"
        )
        download_archives(
            bodacc_dir,
            mode=args.mode,
            families=_split_csv(args.families),
            start_year=args.start_year,
            end_year=args.end_year,
            max_files=args.max_files,
            overwrite=args.overwrite_download,
            drive_root=drive_bodacc_dir if args.work_dir else None,
        )
        print("[bodacc] download phase done")
    else:
        print("[bodacc] download phase skipped")

    if not args.export:
        print("[bodacc] raw export phase skipped")
        return

    print(f"[bodacc] raw export phase start input_dir={bodacc_dir}")
    archives = sorted(
        [*bodacc_dir.rglob("*.taz"), *bodacc_dir.rglob("*.tar"), *bodacc_dir.rglob("*.tar.gz")]
    )
    if not archives:
        print(f"[bodacc] no local archives found under {bodacc_dir}")
        print("[bodacc] no DILA/BODACC archives were downloaded or found.")
        return
    print(f"[bodacc] raw export will scan local archives={len(archives)}")

    cmd = [
        sys.executable,
            "-m",
            "app.tools.bodacc_archives_to_parquet",
            "--input-dir",
            str(bodacc_dir),
            "--output-dir",
            str(p["data_lake"]),
            "--progress-file",
            str(p["data_lake"] / "raw" / "bodacc" / "_batch_progress.json"),
        "--mode",
        args.mode,
        "--families",
        *_split_csv(args.families),
    ]
    if args.year:
        cmd.extend(["--year", str(args.year)])
    cmd.append("--no-skip-existing" if args.overwrite_raw else "--skip-existing")
    run(cmd, repo_dir, env=pipeline_env(p["drive_root"]))
    if args.work_dir:
        print("[bodacc] syncing raw Parquet output to Drive")
        raw_bodacc = p["data_lake"] / "raw" / "bodacc"
        if raw_bodacc.exists():
            sync_tree_to_drive(raw_bodacc, p["drive_root"], drive_p["drive_root"])
        print("[bodacc] raw Parquet sync done")


def download_archives(
    output_dir: Path,
    *,
    mode: str,
    families: list[str],
    start_year: int | None,
    end_year: int | None,
    max_files: int | None,
    overwrite: bool,
    drive_root: Path | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_url = CURRENT_BASE_URL if mode == "current" else HISTORICAL_BASE_URL
    archives = discover_archives(base_url, recursive=(mode == "historical"))
    family_set = set(families)
    selected = [
        archive
        for archive in archives
        if archive.family in family_set or archive.family == FULL_YEAR_FAMILY
        and (start_year is None or (archive.year is not None and archive.year >= start_year))
        and (end_year is None or (archive.year is not None and archive.year <= end_year))
    ]
    if max_files is not None:
        selected = selected[:max_files]

    print(
        "[bodacc] discovered="
        f"{len(archives)} selected={len(selected)} mode={mode} "
        f"families={','.join(families)} years={start_year or '*'}-{end_year or '*'}"
    )
    for archive in selected:
        local_path = local_path_for(output_dir, archive, mode)
        if drive_root is not None and seed_file_from_drive(local_path, output_dir, drive_root):
            print(f"[bodacc] seeded local work file from Drive: {local_path.name}")
        download_resumable(archive.url, local_path, overwrite=overwrite)
        if drive_root is not None:
            synced = sync_file_to_drive(local_path, output_dir, drive_root)
            print(f"[bodacc] synced archive to Drive: {synced}")


def discover_archives(base_url: str, *, recursive: bool) -> list[BodaccRemoteArchive]:
    from urllib.request import Request, urlopen

    base_url = ensure_trailing_slash(base_url)
    seen_dirs: set[str] = set()
    found: dict[str, BodaccRemoteArchive] = {}

    def read_html(url: str) -> str:
        request = Request(url, headers={"User-Agent": "pfe-colab-ml-pipeline/1.0"})
        with urlopen(request, timeout=120) as response:
            return response.read().decode("utf-8", errors="replace")

    def walk(url: str) -> None:
        normalized_url = ensure_trailing_slash(url)
        if normalized_url in seen_dirs:
            return
        seen_dirs.add(normalized_url)
        if len(seen_dirs) == 1 or len(seen_dirs) % 25 == 0:
            print(f"[bodacc] scanning directory {len(seen_dirs)}: {normalized_url}")
        parser = HrefParser()
        parser.feed(read_html(normalized_url))
        for href in parser.hrefs:
            if href.startswith(("#", "?", "mailto:")):
                continue
            child = urljoin(normalized_url, href)
            if not is_under_base(base_url, child):
                continue
            name = Path(unquote(urlparse(child).path).rstrip("/")).name
            if not name or name in (".", ".."):
                continue
            if child.endswith("/"):
                if recursive:
                    walk(child)
                continue
            if not is_archive_name(name):
                continue
            family = family_from_name(name)
            if family == "other":
                continue
            found[child] = BodaccRemoteArchive(
                url=child,
                year=year_from_name(name) or year_from_url(child),
                family=family,
            )
            if len(found) % 100 == 0:
                print(f"[bodacc] discovered archives={len(found)} directories={len(seen_dirs)}")

    walk(base_url)
    print(f"[bodacc] discovery done directories={len(seen_dirs)} archives={len(found)}")
    return sorted(found.values(), key=lambda item: item.url)


def local_path_for(output_dir: Path, archive: BodaccRemoteArchive, mode: str) -> Path:
    name = Path(unquote(urlparse(archive.url).path)).name
    year = str(archive.year or "unknown")
    return output_dir / mode / year / archive.family / name


def is_archive_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def family_from_name(name: str) -> str:
    value = name.upper().replace("_", "-")
    if value.startswith("PCL-BXA") or value.startswith("PCL-"):
        return "PCL"
    if value.startswith("RCS-B-BXB") or value.startswith("RCSB-BXB") or value.startswith("RCS-B"):
        return "RCS-B"
    if value.startswith("RCS-A-BXA") or value.startswith("RCSA-BXA") or value.startswith("RCS-A"):
        return "RCS-A"
    if value.startswith("BILAN-BXC") or value.startswith("BILAN-"):
        return "BILAN"
    if value.startswith("BODACC-") or value.startswith("BODACC."):
        return FULL_YEAR_FAMILY
    stem = value
    for suffix in (".TAR.GZ", ".TAZ", ".TAR"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem.isdigit() and len(stem) == 4:
        return FULL_YEAR_FAMILY
    return "other"


def year_from_name(name: str) -> int | None:
    tokens = "".join(ch if ch.isdigit() else " " for ch in name).split()
    for token in tokens:
        if len(token) >= 4:
            year = int(token[:4])
            if 1900 <= year <= 2100:
                return year
    return None


def year_from_url(url: str) -> int | None:
    parts = [part for part in unquote(urlparse(url).path).split("/") if part]
    for part in reversed(parts):
        year = year_from_name(part)
        if year is not None:
            return year
    return None


def ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def is_under_base(base_url: str, url: str) -> bool:
    return url.startswith(base_url)


def _split_csv(value: str) -> list[str]:
    return [part.strip().upper() for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and export BODACC archives in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--work-dir", help="Optional fast local staging root, for example /content/pfe_work.")
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--mode", choices=("current", "historical"), default="current")
    parser.add_argument("--year", type=int)
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--families", default="PCL,RCS-B")
    parser.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--export", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--overwrite-download", action="store_true")
    parser.add_argument("--overwrite-raw", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
