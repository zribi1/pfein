from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import DEFAULT_DRIVE_ROOT, install_deps, paths, pipeline_env, print_outputs, run


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    p = paths(args.drive_root)
    env = pipeline_env(args.drive_root)
    if args.install_deps:
        install_deps(repo_dir)

    if args.clean_core:
        run(
            [
                sys.executable,
                "-m",
                "app.tools.build_clean_core_sources",
                "--data-lake-dir",
                str(p["data_lake"]),
                "--overwrite",
            ],
            repo_dir,
            env=env,
        )

    if args.clean_financials:
        run(
            [
                sys.executable,
                "-m",
                "app.tools.build_clean_financials",
                "--data-lake-dir",
                str(p["data_lake"]),
                "--overwrite",
            ],
            repo_dir,
            env=env,
        )

    feature_command = [
        sys.executable,
        "-m",
        "app.tools.build_company_year_features",
        "--data-lake-dir",
        str(p["data_lake"]),
        "--start-year",
        str(args.start_year),
        "--end-year",
        str(args.end_year),
        "--overwrite",
    ]
    if args.max_companies:
        feature_command.extend(["--max-companies", str(args.max_companies)])
    run(feature_command, repo_dir, env=env)

    if args.train:
        run(
            [
                sys.executable,
                "-m",
                "app.tools.train_continuity_model",
                "--data-lake-dir",
                str(p["data_lake"]),
                "--artifacts-dir",
                str(p["artifacts"]),
                "--min-rows",
                str(args.min_rows),
            ],
            repo_dir,
            env=env,
        )

    if args.audit:
        audit_command = [
            sys.executable,
            "collabs/audit_data_lake.py",
            "--drive-root",
            str(args.drive_root),
            "--max-columns",
            str(args.audit_max_columns),
            "--sample-rows",
            str(args.audit_sample_rows),
        ]
        if args.audit_output_md:
            audit_command.extend(["--output-md", args.audit_output_md])
        if args.audit_output_json:
            audit_command.extend(["--output-json", args.audit_output_json])
        run(audit_command, repo_dir, env=env)

    print_outputs(args.drive_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ML feature/label tables in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--clean-core", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--clean-financials", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-companies", type=int, help="Optional smoke-test cap for feature generation.")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--min-rows", type=int, default=1000)
    parser.add_argument("--audit", action="store_true", help="Generate the data-lake audit report after building features.")
    parser.add_argument("--audit-max-columns", type=int, default=25)
    parser.add_argument("--audit-sample-rows", type=int, default=2)
    parser.add_argument("--audit-output-md", help="Optional Markdown report path. Defaults to <drive-root>/reports/data_lake_audit.md.")
    parser.add_argument("--audit-output-json", help="Optional JSON report path. Defaults to <drive-root>/reports/data_lake_audit.json.")
    return parser.parse_args()


if __name__ == "__main__":
    main()
