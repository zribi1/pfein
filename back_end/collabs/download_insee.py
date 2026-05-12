from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import (
    DEFAULT_DRIVE_ROOT,
    INSEE_RESOURCES,
    download_resumable,
    install_deps,
    pipeline_env,
    seed_file_from_drive,
    storage_paths,
    sync_file_to_drive,
    sync_tree_to_drive,
    run,
)


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    drive_p, work_p = storage_paths(args.drive_root, args.work_dir)
    p = work_p
    if args.install_deps:
        install_deps(repo_dir)

    downloaded = []
    print(f"[insee] preparing {len(INSEE_RESOURCES)} bulk resource(s)")
    for index, (dataset_type, url) in enumerate(INSEE_RESOURCES, start=1):
        path = p["source_archives"] / "insee" / "bulk" / dataset_type / Path(url).name
        phase = "download" if args.download else "prepare"
        print(f"[insee] {phase} {index}/{len(INSEE_RESOURCES)} dataset={dataset_type}")
        if args.work_dir and seed_file_from_drive(path, p["drive_root"], drive_p["drive_root"]):
            print(f"[insee] seeded local work file from Drive: {path.name}")
        if args.download:
            download_resumable(url, path, overwrite=args.overwrite)
        elif not path.exists():
            raise FileNotFoundError(f"INSEE source file missing; run download first: {path}")
        if args.download and args.work_dir:
            synced = sync_file_to_drive(path, p["drive_root"], drive_p["drive_root"])
            print(f"[insee] synced archive to Drive: {synced}")
        downloaded.append((dataset_type, path))
    print(f"[insee] source phase done files={len(downloaded)}")

    if args.export_raw:
        env = pipeline_env(p["drive_root"])
        print(f"[insee] raw export phase start files={len(downloaded)}")
        for index, (dataset_type, path) in enumerate(downloaded, start=1):
            print(f"[insee] export {index}/{len(downloaded)} dataset={dataset_type}")
            cmd = [
                sys.executable,
                "-m",
                "app.tools.insee_bulk_to_parquet",
                "--input",
                str(path),
                "--output-dir",
                str(p["data_lake"]),
                "--dataset-type",
                dataset_type,
            ]
            if args.overwrite_raw:
                cmd.append("--overwrite")
            run(cmd, repo_dir, env=env)
            if args.work_dir:
                raw_dir = p["data_lake"] / "raw" / "insee" / "bulk" / dataset_type
                if raw_dir.exists():
                    sync_tree_to_drive(raw_dir, p["drive_root"], drive_p["drive_root"])
        print("[insee] raw export phase done")
    else:
        print("[insee] raw export phase skipped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download/export INSEE Sirene bulk data in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--work-dir", help="Optional fast local staging root, for example /content/pfe_work.")
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--export-raw", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite-raw", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
