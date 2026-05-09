from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import (
    DEFAULT_DRIVE_ROOT,
    INSEE_RESOURCES,
    install_deps,
    pipeline_env,
    seed_file_from_drive,
    storage_paths,
    sync_tree_to_drive,
    run,
)


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    drive_p, work_p = storage_paths(args.drive_root, args.work_dir)
    p = work_p
    env = pipeline_env(p["drive_root"])
    if args.install_deps:
        install_deps(repo_dir)

    if args.insee:
        print("[export] INSEE raw export phase start")
        for dataset_type, url in INSEE_RESOURCES:
            path = p["source_archives"] / "insee" / "bulk" / dataset_type / Path(url).name
            if args.work_dir:
                seed_file_from_drive(path, p["drive_root"], drive_p["drive_root"])
            if not path.exists():
                print(f"[insee] missing {path}; run collabs/download_insee.py first")
                continue
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
            if args.overwrite:
                cmd.append("--overwrite")
            run(cmd, repo_dir, env=env)
            if args.work_dir:
                raw_dir = p["data_lake"] / "raw" / "insee" / "bulk" / dataset_type
                if raw_dir.exists():
                    sync_tree_to_drive(raw_dir, p["drive_root"], drive_p["drive_root"])
        print("[export] INSEE raw export phase done")
    else:
        print("[export] INSEE raw export phase skipped")

    if args.inpi:
        if args.work_dir and not (p["source_archives"] / "inpi").exists() and (drive_p["source_archives"] / "inpi").exists():
            print("[export] seeding INPI archives from Drive to local work dir")
            shutil.copytree(drive_p["source_archives"] / "inpi", p["source_archives"] / "inpi")
        inpi_archives = sorted((p["source_archives"] / "inpi").rglob("*.zip"))
        print(f"[export] INPI raw export phase start archives={len(inpi_archives)}")
        for index, path in enumerate(inpi_archives, start=1):
            print(f"[export] INPI export {index}/{len(inpi_archives)} {path.name}")
            run(
                [
                    sys.executable,
                    "-m",
                    "app.tools.inpi_to_parquet",
                    "--input",
                    str(path),
                    "--output-dir",
                    str(p["data_lake"]),
                    "--no-include-raw-json",
                ],
                repo_dir,
                env=env,
            )
        if args.work_dir and (p["data_lake"] / "raw" / "inpi").exists():
            print("[export] syncing INPI raw output to Drive")
            sync_tree_to_drive(p["data_lake"] / "raw" / "inpi", p["drive_root"], drive_p["drive_root"])
        print("[export] INPI raw export phase done")
    else:
        print("[export] INPI raw export phase skipped")

    if args.bodacc:
        bodacc_dir = p["source_archives"] / "bodacc"
        if args.work_dir and not bodacc_dir.exists() and (drive_p["source_archives"] / "bodacc").exists():
            print("[export] seeding BODACC archives from Drive to local work dir")
            shutil.copytree(drive_p["source_archives"] / "bodacc", bodacc_dir)
        if bodacc_dir.exists():
            archive_count = sum(1 for _ in bodacc_dir.rglob("*") if _.suffix.lower() in {".taz", ".tar", ".gz"})
            print(f"[export] BODACC raw export phase start archives={archive_count}")
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
            ]
            cmd.append("--no-skip-existing" if args.overwrite else "--skip-existing")
            run(cmd, repo_dir, env=env)
            if args.work_dir and (p["data_lake"] / "raw" / "bodacc").exists():
                print("[export] syncing BODACC raw output to Drive")
                sync_tree_to_drive(p["data_lake"] / "raw" / "bodacc", p["drive_root"], drive_p["drive_root"])
            print("[export] BODACC raw export phase done")
        else:
            print(f"[export] BODACC source directory missing: {bodacc_dir}")
    else:
        print("[export] BODACC raw export phase skipped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export existing source archives to raw Parquet.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--work-dir", help="Optional fast local staging root, for example /content/pfe_work.")
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--insee", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--inpi", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bodacc", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
