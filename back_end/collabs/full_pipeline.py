from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import DEFAULT_DRIVE_ROOT, install_deps, run


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    if args.install_deps:
        install_deps(repo_dir)

    base = [f"--drive-root={args.drive_root}", f"--repo-dir={repo_dir}"]
    if args.insee:
        run([sys.executable, "collabs/download_insee.py", *base, "--export-raw"], repo_dir)
    if args.bilan:
        run([sys.executable, "collabs/download_bilan.py", *base, "--copy-to-raw"], repo_dir)
    if args.inpi:
        run(
            [
                sys.executable,
                "collabs/download_inpi.py",
                *base,
                f"--categories={args.inpi_categories}",
                f"--niveaux={args.inpi_niveaux}",
            ],
            repo_dir,
        )
        run([sys.executable, "collabs/export_raw_sources.py", *base, "--no-insee", "--inpi", "--no-bodacc"], repo_dir)
    if args.bodacc:
        run([sys.executable, "collabs/download_bodacc.py", *base], repo_dir)
    if args.build:
        cmd = [
            sys.executable,
            "collabs/build_ml_data.py",
            *base,
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(args.end_year),
        ]
        if args.train:
            cmd.append("--train")
        run(cmd, repo_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Colab preparation blocks in order.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--insee", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bilan", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--inpi", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--bodacc", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--build", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--inpi-categories", default="comptes_annuels,formalites")
    parser.add_argument("--inpi-niveaux", default="standard,niveau1")
    return parser.parse_args()


if __name__ == "__main__":
    main()
