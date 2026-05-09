from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import DEFAULT_DRIVE_ROOT, append_status, install_deps, run


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    if args.install_deps:
        install_deps(repo_dir)

    base = [f"--drive-root={args.drive_root}", f"--repo-dir={repo_dir}"]
    if args.work_dir:
        base.append(f"--work-dir={args.work_dir}")
    failures: list[str] = []
    if args.insee:
        run_pipeline_step(args, failures, "download_insee", [sys.executable, "collabs/download_insee.py", *base, "--export-raw"], repo_dir)
    if args.bilan:
        run_pipeline_step(args, failures, "download_bilan", [sys.executable, "collabs/download_bilan.py", *base, "--copy-to-raw"], repo_dir)
    inpi_ok = True
    if args.inpi:
        inpi_ok = run_pipeline_step(
            args,
            failures,
            "download_inpi",
            [
                sys.executable,
                "collabs/download_inpi.py",
                *base,
                f"--categories={args.inpi_categories}",
                f"--niveaux={args.inpi_niveaux}",
                f"--retries={args.inpi_retries}",
            ],
            repo_dir,
        )
        if inpi_ok:
            run_pipeline_step(
                args,
                failures,
                "export_raw_inpi",
                [sys.executable, "collabs/export_raw_sources.py", *base, "--no-insee", "--inpi", "--no-bodacc"],
                repo_dir,
            )
        else:
            append_status(args.drive_root, step="export_raw_inpi", status="skipped", details={"reason": "download_inpi failed"})
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
        run_pipeline_step(args, failures, "download_bodacc", cmd, repo_dir)
    can_build = not failures or args.build_after_failures
    if args.build and can_build:
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
        run_pipeline_step(args, failures, "build_ml_data", cmd, repo_dir)
    elif args.build:
        append_status(
            args.drive_root,
            step="build_ml_data",
            status="skipped",
            details={"reason": "previous step failed", "failures": failures},
        )
    if failures:
        print("\n[pipeline] completed with failures. Inspect:")
        print(f"- {Path(args.drive_root) / 'reports' / 'pipeline_status.md'}")
        print(f"- {Path(args.drive_root) / 'reports' / 'pipeline_status.json'}")


def run_pipeline_step(
    args: argparse.Namespace,
    failures: list[str],
    step: str,
    command: list[str],
    repo_dir: Path,
) -> bool:
    append_status(args.drive_root, step=step, status="started", command=command)
    try:
        run(command, repo_dir)
    except (subprocess.CalledProcessError, RuntimeError, OSError) as exc:
        failures.append(step)
        append_status(args.drive_root, step=step, status="failed", command=command, error=exc)
        print(f"[pipeline] step failed: {step}. Status report written under {Path(args.drive_root) / 'reports'}")
        if not args.continue_on_error:
            raise
        return False
    append_status(args.drive_root, step=step, status="succeeded", command=command)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Colab preparation blocks in order.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--work-dir", help="Optional fast local staging root, for example /content/pfe_work.")
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
    parser.add_argument("--inpi-retries", type=int, default=6)
    parser.add_argument("--continue-on-error", action="store_true", help="Write status reports and continue independent steps after a source failure.")
    parser.add_argument("--build-after-failures", action="store_true", help="Build features even if a previous source step failed.")
    return parser.parse_args()


if __name__ == "__main__":
    main()
