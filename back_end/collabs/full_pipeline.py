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
        bodacc_families = ",".join(args.bodacc_families)
        cmd = [
            sys.executable,
            "collabs/download_bodacc.py",
            *base,
            f"--mode={args.bodacc_mode}",
            f"--families={bodacc_families}",
        ]
        if args.bodacc_start_year:
            cmd.extend(["--start-year", str(args.bodacc_start_year)])
        if args.bodacc_end_year:
            cmd.extend(["--end-year", str(args.bodacc_end_year)])
        if args.bodacc_max_files:
            cmd.extend(["--max-files", str(args.bodacc_max_files)])
        if args.bodacc_overwrite_download:
            cmd.append("--overwrite-download")
        if args.bodacc_overwrite_raw:
            cmd.append("--overwrite-raw")
        run(cmd, repo_dir)
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
        if args.max_companies:
            cmd.extend(["--max-companies", str(args.max_companies)])
        if args.audit:
            cmd.append("--audit")
            cmd.extend(["--audit-max-columns", str(args.audit_max_columns)])
            cmd.extend(["--audit-sample-rows", str(args.audit_sample_rows)])
            if args.audit_output_md:
                cmd.extend(["--audit-output-md", args.audit_output_md])
            if args.audit_output_json:
                cmd.extend(["--audit-output-json", args.audit_output_json])
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
    parser.add_argument("--bodacc-mode", choices=("current", "historical"), default="historical")
    parser.add_argument("--bodacc-families", nargs="+", default=["PCL", "RCS-B"])
    parser.add_argument("--bodacc-start-year", type=int)
    parser.add_argument("--bodacc-end-year", type=int)
    parser.add_argument("--bodacc-max-files", type=int)
    parser.add_argument("--bodacc-overwrite-download", action="store_true")
    parser.add_argument("--bodacc-overwrite-raw", action="store_true")
    parser.add_argument("--build", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--max-companies", type=int, help="Optional smoke-test cap for feature generation.")
    parser.add_argument("--audit", action="store_true", help="Generate the data-lake audit report after building features.")
    parser.add_argument("--audit-max-columns", type=int, default=25)
    parser.add_argument("--audit-sample-rows", type=int, default=2)
    parser.add_argument("--audit-output-md", help="Optional Markdown report path. Defaults to <drive-root>/reports/data_lake_audit.md.")
    parser.add_argument("--audit-output-json", help="Optional JSON report path. Defaults to <drive-root>/reports/data_lake_audit.json.")
    parser.add_argument("--inpi-categories", default="comptes_annuels,formalites")
    parser.add_argument("--inpi-niveaux", default="standard,niveau1")
    return parser.parse_args()


if __name__ == "__main__":
    main()
