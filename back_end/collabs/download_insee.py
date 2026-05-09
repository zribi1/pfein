from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import DEFAULT_DRIVE_ROOT, INSEE_RESOURCES, download_resumable, install_deps, paths, pipeline_env, run


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    p = paths(args.drive_root)
    if args.install_deps:
        install_deps(repo_dir)

    downloaded = []
    print(f"[insee] preparing {len(INSEE_RESOURCES)} bulk resource(s)")
    for index, (dataset_type, url) in enumerate(INSEE_RESOURCES, start=1):
        path = p["source_archives"] / "insee" / "bulk" / dataset_type / Path(url).name
        print(f"[insee] download {index}/{len(INSEE_RESOURCES)} dataset={dataset_type}")
        download_resumable(url, path, overwrite=args.overwrite)
        downloaded.append((dataset_type, path))
    print(f"[insee] download phase done files={len(downloaded)}")

    if args.export_raw:
        env = pipeline_env(args.drive_root)
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
        print("[insee] raw export phase done")
    else:
        print("[insee] raw export phase skipped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download/export INSEE Sirene bulk data in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--export-raw", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite-raw", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
