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
    for dataset_type, url in INSEE_RESOURCES:
        path = p["source_archives"] / "insee" / "bulk" / dataset_type / Path(url).name
        download_resumable(url, path, overwrite=args.overwrite)
        downloaded.append((dataset_type, path))

    if args.export_raw:
        env = pipeline_env(args.drive_root)
        for dataset_type, path in downloaded:
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
