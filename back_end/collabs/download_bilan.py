from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import (
    DATAGOUV_API_BASE,
    DEFAULT_DRIVE_ROOT,
    FINANCIAL_DATASET_SLUG,
    download_resumable,
    install_deps,
    paths,
    read_json_url,
    write_json,
)


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    p = paths(args.drive_root)
    if args.install_deps:
        install_deps(repo_dir)

    resource = latest_financial_resource()
    url = str(resource.get("url") or resource.get("latest"))
    source_file = p["source_archives"] / "financials" / "data_gouv" / Path(url.split("?", 1)[0]).name
    download_resumable(url, source_file, overwrite=args.overwrite)
    write_json(
        source_file.with_suffix(source_file.suffix + ".manifest.json"),
        {
            "source": "data.gouv.fr",
            "dataset_slug": FINANCIAL_DATASET_SLUG,
            "resource_id": resource.get("id"),
            "resource_title": resource.get("title"),
            "resource_url": url,
            "resource_last_modified": resource.get("last_modified") or resource.get("published"),
            "resource_filesize": resource.get("filesize"),
            "size_bytes": source_file.stat().st_size,
        },
    )

    if args.copy_to_raw:
        raw_dir = p["data_lake"] / "raw" / "financials" / source_file.stem
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / source_file.name
        if args.overwrite or not raw_file.exists():
            shutil.copy2(source_file, raw_file)
        write_json(
            raw_dir / "_manifest.json",
            {
                "source": "data.gouv.fr",
                "dataset_slug": FINANCIAL_DATASET_SLUG,
                "source_archive_file": str(source_file),
                "output_file": str(raw_file),
                "size_bytes": raw_file.stat().st_size,
            },
        )
        print(f"[bilan] raw ready: {raw_file}")


def latest_financial_resource() -> dict:
    meta = read_json_url(f"{DATAGOUV_API_BASE}/datasets/{FINANCIAL_DATASET_SLUG}/")
    resources = []
    for item in meta.get("resources", []):
        fmt = str(item.get("format") or "").lower()
        url = str(item.get("url") or item.get("latest") or "")
        if fmt == "parquet" and url:
            resources.append(item)
    if not resources:
        raise RuntimeError(f"no Parquet resources found for {FINANCIAL_DATASET_SLUG}")
    return sorted(
        resources,
        key=lambda item: (str(item.get("last_modified") or item.get("published") or ""), int(item.get("filesize") or 0)),
        reverse=True,
    )[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download financial/bilan Parquet data in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--copy-to-raw", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
