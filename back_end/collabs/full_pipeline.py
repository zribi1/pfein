from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import DEFAULT_DRIVE_ROOT, INSEE_RESOURCES, append_status, install_deps, run


STEP_CHOICES = (
    "all",
    "download_insee",
    "export_raw_insee",
    "download_bilan",
    "export_raw_bilan",
    "download_inpi",
    "export_raw_inpi",
    "download_bodacc",
    "export_raw_bodacc",
    "build_ml_data",
)

SOURCE_CHOICES = ("insee", "bilan", "financials", "inpi", "bodacc")

SOURCE_STEPS = {
    "insee": ("download_insee", "export_raw_insee"),
    "bilan": ("download_bilan", "export_raw_bilan"),
    "financials": ("download_bilan", "export_raw_bilan"),
    "inpi": ("download_inpi", "export_raw_inpi"),
    "bodacc": ("download_bodacc", "export_raw_bodacc"),
}


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    if args.install_deps:
        install_deps(repo_dir)

    base = [f"--drive-root={args.drive_root}", f"--repo-dir={repo_dir}"]
    if args.work_dir:
        base.append(f"--work-dir={args.work_dir}")
    failures: list[str] = []

    if args.source:
        ok = run_source_pipeline(args, failures, args.source, repo_dir, base)
        print_source_status_hint(args, source=args.source, ok=ok)
        return

    if args.step != "all":
        ok = run_named_step(args, failures, args.step, repo_dir, base)
        print_status_hint(args, ok=ok)
        return

    if args.insee:
        run_source_pipeline(args, failures, "insee", repo_dir, base)
    if args.bilan:
        run_source_pipeline(args, failures, "bilan", repo_dir, base)
    inpi_ok = True
    if args.inpi:
        inpi_ok = run_named_step(args, failures, "download_inpi", repo_dir, base)
        if inpi_ok:
            run_named_step(args, failures, "export_raw_inpi", repo_dir, base)
        else:
            append_status(args.drive_root, step="export_raw_inpi", status="skipped", details={"reason": "download_inpi failed"})
    if args.bodacc:
        bodacc_ok = run_named_step(args, failures, "download_bodacc", repo_dir, base)
        if bodacc_ok:
            run_named_step(args, failures, "export_raw_bodacc", repo_dir, base)
        else:
            append_status(args.drive_root, step="export_raw_bodacc", status="skipped", details={"reason": "download_bodacc failed"})
    can_build = not failures or args.build_after_failures
    if args.build and can_build:
        run_named_step(args, failures, "build_ml_data", repo_dir, base)
    elif args.build:
        append_status(
            args.drive_root,
            step="build_ml_data",
            status="skipped",
            details={"reason": "previous step failed", "failures": failures},
        )
    if failures:
        print("\n[pipeline] completed with failures. Inspect:")
        print_status_paths(args)


def run_named_step(
    args: argparse.Namespace,
    failures: list[str],
    step: str,
    repo_dir: Path,
    base: list[str],
) -> bool:
    return run_pipeline_step(args, failures, step, command_for_step(args, step, base), repo_dir)


def run_source_pipeline(
    args: argparse.Namespace,
    failures: list[str],
    source: str,
    repo_dir: Path,
    base: list[str],
) -> bool:
    ok = True
    for step in SOURCE_STEPS[source]:
        if not ok:
            append_status(
                args.drive_root,
                step=step,
                status="skipped",
                details={"reason": f"previous {source} source step failed"},
            )
            continue
        ok = run_named_step(args, failures, step, repo_dir, base)
    return ok


def command_for_step(args: argparse.Namespace, step: str, base: list[str]) -> list[str]:
    if step == "download_insee":
        return [sys.executable, "collabs/download_insee.py", *base, "--download", "--no-export-raw"]
    if step == "export_raw_insee":
        return [sys.executable, "collabs/download_insee.py", *base, "--no-download", "--export-raw"]
    if step == "download_bilan":
        return [sys.executable, "collabs/download_bilan.py", *base, "--download", "--no-copy-to-raw"]
    if step == "export_raw_bilan":
        return [sys.executable, "collabs/download_bilan.py", *base, "--no-download", "--copy-to-raw"]
    if step == "download_inpi":
        return [
            sys.executable,
            "collabs/download_inpi.py",
            *base,
            f"--categories={args.inpi_categories}",
            f"--niveaux={args.inpi_niveaux}",
            f"--retries={args.inpi_retries}",
        ]
    if step == "export_raw_inpi":
        return [sys.executable, "collabs/export_raw_sources.py", *base, "--no-insee", "--inpi", "--no-bodacc"]
    if step in {"download_bodacc", "export_raw_bodacc"}:
        return bodacc_command(args, base, export=(step == "export_raw_bodacc"))
    if step == "build_ml_data":
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
        if args.year_batch_size:
            cmd.extend(["--year-batch-size", str(args.year_batch_size)])
        if args.audit:
            cmd.append("--audit")
            cmd.extend(["--audit-max-columns", str(args.audit_max_columns)])
            cmd.extend(["--audit-sample-rows", str(args.audit_sample_rows)])
            if args.audit_output_md:
                cmd.extend(["--audit-output-md", args.audit_output_md])
            if args.audit_output_json:
                cmd.extend(["--audit-output-json", args.audit_output_json])
        return cmd
    raise ValueError(f"unknown pipeline step: {step}")


def bodacc_command(args: argparse.Namespace, base: list[str], *, export: bool) -> list[str]:
    bodacc_families = ",".join(args.bodacc_families)
    cmd = [
        sys.executable,
        "collabs/download_bodacc.py",
        *base,
        f"--mode={args.bodacc_mode}",
        f"--families={bodacc_families}",
        "--no-download" if export else "--download",
        "--export" if export else "--no-export",
    ]
    start_year, end_year = bodacc_year_bounds(args)
    if start_year:
        cmd.extend(["--start-year", str(start_year)])
    if end_year:
        cmd.extend(["--end-year", str(end_year)])
    if args.bodacc_max_files and not export:
        cmd.extend(["--max-files", str(args.bodacc_max_files)])
    if args.bodacc_overwrite_download and not export:
        cmd.append("--overwrite-download")
    if args.bodacc_overwrite_raw and export:
        cmd.append("--overwrite-raw")
    return cmd


def bodacc_year_bounds(args: argparse.Namespace) -> tuple[int | None, int | None]:
    if args.bodacc_all_years:
        return args.bodacc_start_year, args.bodacc_end_year
    start_year = args.bodacc_start_year if args.bodacc_start_year is not None else args.start_year
    end_year = args.bodacc_end_year if args.bodacc_end_year is not None else args.end_year
    return start_year, end_year


def print_status_hint(args: argparse.Namespace, *, ok: bool) -> None:
    state = "succeeded" if ok else "failed"
    print(f"\n[pipeline] step {state}. Inspect:")
    print_status_paths(args)


def print_source_status_hint(args: argparse.Namespace, *, source: str, ok: bool) -> None:
    state = "succeeded" if ok else "failed"
    print(f"\n[pipeline] source pipeline {source} {state}. Inspect:")
    print_status_paths(args)


def print_status_paths(args: argparse.Namespace) -> None:
    print(f"- {Path(args.drive_root) / 'reports' / 'pipeline_status.md'}")
    print(f"- {Path(args.drive_root) / 'reports' / 'pipeline_status.json'}")


def run_pipeline_step(
    args: argparse.Namespace,
    failures: list[str],
    step: str,
    command: list[str],
    repo_dir: Path,
) -> bool:
    if not args.force and step_is_done(args, step):
        print(f"[pipeline] step already done in Drive: {step}")
        append_status(
            args.drive_root,
            step=step,
            status="skipped",
            command=command,
            details={"reason": "already done in Drive"},
        )
        return True
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


def step_is_done(args: argparse.Namespace, step: str) -> bool:
    drive_root = Path(args.drive_root).resolve()
    if step == "download_insee":
        return insee_download_done(drive_root)
    if step == "export_raw_insee":
        return insee_export_done(drive_root)
    if step == "download_bilan":
        return financial_download_done(drive_root)
    if step == "export_raw_bilan":
        return financial_export_done(drive_root)
    if step == "download_inpi":
        return inpi_download_done(drive_root, args)
    if step == "export_raw_inpi":
        return inpi_export_done(drive_root, args)
    if step == "download_bodacc":
        return bodacc_download_done(drive_root, args)
    if step == "export_raw_bodacc":
        return bodacc_export_done(drive_root, args)
    return False


def insee_download_done(drive_root: Path) -> bool:
    return all(
        valid_file(drive_root / "source-archives" / "insee" / "bulk" / dataset_type / Path(url).name)
        for dataset_type, url in INSEE_RESOURCES
    )


def insee_export_done(drive_root: Path) -> bool:
    return all(
        has_manifest_with_parquet(drive_root / "data-lake" / "raw" / "insee" / "bulk" / dataset_type)
        for dataset_type, _ in INSEE_RESOURCES
    )


def financial_download_done(drive_root: Path) -> bool:
    source_dir = drive_root / "source-archives" / "financials" / "data_gouv"
    return any(valid_file(path) for path in source_dir.glob("*.parquet")) if source_dir.exists() else False


def financial_export_done(drive_root: Path) -> bool:
    return has_manifest_with_parquet(drive_root / "data-lake" / "raw" / "financials")


def inpi_download_done(drive_root: Path, args: argparse.Namespace) -> bool:
    source_dir = drive_root / "source-archives" / "inpi"
    requested = requested_inpi_pairs(args)
    found: set[tuple[str, str]] = set()
    for manifest_path in source_dir.rglob("*.zip.manifest.json") if source_dir.exists() else []:
        zip_path = manifest_path.with_name(manifest_path.name[: -len(".manifest.json")])
        if not valid_file(zip_path):
            continue
        payload = read_json_silent(manifest_path)
        category = str(payload.get("category") or "").lower()
        niveau = str(payload.get("niveau") or "").lower()
        if category and niveau:
            found.add((category, niveau))
    return bool(found) if not requested else requested.issubset(found)


def inpi_export_done(drive_root: Path, args: argparse.Namespace) -> bool:
    raw_dir = drive_root / "data-lake" / "raw" / "inpi"
    requested = requested_inpi_pairs(args)
    found: set[tuple[str, str]] = set()
    if raw_dir.exists():
        for manifest_path in raw_dir.rglob("_manifest.json"):
            payload = read_json_silent(manifest_path)
            category = str(payload.get("category") or "").lower()
            niveau = str(payload.get("niveau") or "").lower()
            if category and niveau and has_parquet_file(manifest_path.parent):
                found.add((category, niveau))
    return bool(found) if not requested else requested.issubset(found)


def bodacc_download_done(drive_root: Path, args: argparse.Namespace) -> bool:
    archive_root = drive_root / "source-archives" / "bodacc" / args.bodacc_mode
    start_year, end_year = bodacc_year_bounds(args)
    families = {family.upper() for family in args.bodacc_families}
    if start_year and end_year:
        return all(bodacc_year_has_archive(archive_root, year, families) for year in range(start_year, end_year + 1))
    return any(is_archive_file(path) and valid_file(path) for path in archive_root.rglob("*")) if archive_root.exists() else False


def bodacc_export_done(drive_root: Path, args: argparse.Namespace) -> bool:
    raw_root = drive_root / "data-lake" / "raw" / "bodacc" / args.bodacc_mode
    start_year, end_year = bodacc_year_bounds(args)
    if start_year and end_year:
        return all(has_manifest_with_parquet(raw_root / str(year)) for year in range(start_year, end_year + 1))
    return has_manifest_with_parquet(raw_root)


def bodacc_year_has_archive(archive_root: Path, year: int, families: set[str]) -> bool:
    year_dir = archive_root / str(year)
    if not year_dir.exists():
        return False
    if any(is_archive_file(path) and valid_file(path) for path in (year_dir / "FULL").rglob("*")):
        return True
    return all(
        any(is_archive_file(path) and valid_file(path) for path in (year_dir / family).rglob("*"))
        for family in families
    )


def requested_inpi_pairs(args: argparse.Namespace) -> set[tuple[str, str]]:
    categories = split_filter(args.inpi_categories)
    niveaux = split_filter(args.inpi_niveaux)
    if not categories or not niveaux:
        return set()
    return {(category, niveau) for category in categories for niveau in niveaux}


def split_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def has_manifest_with_parquet(path: Path) -> bool:
    if not path.exists():
        return False
    return any(has_parquet_file(manifest.parent) for manifest in path.rglob("_manifest.json"))


def has_parquet_file(path: Path) -> bool:
    return any(valid_file(file_path) for file_path in path.glob("*.parquet"))


def valid_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def is_archive_file(path: Path) -> bool:
    lower = path.name.lower()
    return lower.endswith((".taz", ".tar", ".tar.gz"))


def read_json_silent(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Colab preparation blocks in order.")
    parser.add_argument("--step", choices=STEP_CHOICES, default="all", help="Run one pipeline step and stop. Default: all.")
    parser.add_argument(
        "--source",
        choices=SOURCE_CHOICES,
        help="Run the full source-prep pipeline for one source, then stop.",
    )
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--work-dir", help="Optional fast local staging root, for example /content/pfe_work.")
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--force", action="store_true", help="Run even if Drive artifacts show the step is already done.")
    parser.add_argument("--insee", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bilan", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--inpi", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--bodacc", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--bodacc-mode", choices=("current", "historical"), default="historical")
    parser.add_argument("--bodacc-families", nargs="+", default=["PCL", "RCS-B"])
    parser.add_argument("--bodacc-start-year", type=int)
    parser.add_argument("--bodacc-end-year", type=int)
    parser.add_argument(
        "--bodacc-all-years",
        action="store_true",
        help="Do not default BODACC to the model --start-year/--end-year window.",
    )
    parser.add_argument("--bodacc-max-files", type=int)
    parser.add_argument("--bodacc-overwrite-download", action="store_true")
    parser.add_argument("--bodacc-overwrite-raw", action="store_true")
    parser.add_argument("--build", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--max-companies", type=int, help="Optional smoke-test cap for feature generation.")
    parser.add_argument("--year-batch-size", type=int, help="Build feature prediction years in smaller batches.")
    parser.add_argument("--audit", action="store_true", help="Generate the data-lake audit report after building features.")
    parser.add_argument("--audit-max-columns", type=int, default=25)
    parser.add_argument("--audit-sample-rows", type=int, default=2)
    parser.add_argument("--audit-output-md", help="Optional Markdown report path. Defaults to <drive-root>/reports/data_lake_audit.md.")
    parser.add_argument("--audit-output-json", help="Optional JSON report path. Defaults to <drive-root>/reports/data_lake_audit.json.")
    parser.add_argument("--inpi-categories", default="comptes_annuels,formalites")
    parser.add_argument("--inpi-niveaux", default="standard,niveau1")
    parser.add_argument(
        "--inpi-retries",
        type=int,
        default=2,
        help="Retry each INPI archive transfer this many times. Reruns resume partial files, so the default stays short.",
    )
    parser.add_argument("--continue-on-error", action="store_true", help="Write status reports and continue independent steps after a source failure.")
    parser.add_argument("--build-after-failures", action="store_true", help="Build features even if a previous source step failed.")
    args = parser.parse_args()
    if args.source and args.step != "all":
        parser.error("--source and --step cannot be used together")
    return args


if __name__ == "__main__":
    main()
