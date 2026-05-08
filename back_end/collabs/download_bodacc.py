from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import DEFAULT_DRIVE_ROOT, install_deps, paths, pipeline_env, run


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    p = paths(args.drive_root)
    if args.install_deps:
        install_deps(repo_dir)

    bodacc_dir = p["source_archives"] / "bodacc"
    archives = sorted([*bodacc_dir.rglob("*.taz"), *bodacc_dir.rglob("*.tar")])
    if not archives:
        print(f"[bodacc] no local archives found under {bodacc_dir}")
        print("[bodacc] put DILA/BODACC .taz or .tar files there, then rerun this script.")
        return

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
        *args.families.split(","),
    ]
    if args.year:
        cmd.extend(["--year", str(args.year)])
    cmd.append("--no-skip-existing" if args.overwrite_raw else "--skip-existing")
    run(cmd, repo_dir, env=pipeline_env(args.drive_root))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export local BODACC archives in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--mode", choices=("current", "historical"), default="current")
    parser.add_argument("--year", type=int)
    parser.add_argument("--families", default="PCL,RCS-B")
    parser.add_argument("--overwrite-raw", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
