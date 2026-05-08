from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


EXPECTED_INPI_ZIPS = (
    "stock_RNE_comptes_annuels_20250926_1000_v2.zip",
    "stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip",
    "stock_RNE_formalites_20250523_0000.zip",
    "stock_RNE_formalites_NIVEAU1_20260304_1400.zip",
)


@dataclass
class CheckResult:
    name: str
    status: str
    train_blocker: bool
    summary: str
    evidence: dict[str, Any]


def main() -> None:
    args = _parse_args()
    data_lake = Path(args.data_lake_dir or _default_data_lake_dir())
    inpi_source = Path(args.inpi_source_dir or _default_inpi_source_dir())

    results = [
        check_financials(data_lake),
        check_inpi(data_lake, inpi_source),
        check_insee(data_lake),
        check_bodacc(data_lake),
    ]
    results.append(check_features(data_lake, results))

    payload = {
        "data_lake_dir": str(data_lake),
        "inpi_source_dir": str(inpi_source),
        "training_ready": all(not result.train_blocker for result in results),
        "checks": [asdict(result) for result in results],
    }

    if args.json:
        output = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        print(output)
    else:
        _print_human(payload)
        output = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")

    if args.fail_on_not_ready and not payload["training_ready"]:
        raise SystemExit(2)


def check_financials(data_lake: Path) -> CheckResult:
    clean_dir = data_lake / "clean" / "financials"
    manifest = _read_json(clean_dir / "_manifest.json")
    rows = _int_or_none(manifest.get("rows") if manifest else None)
    parquet_files = list(clean_dir.rglob("*.parquet")) if clean_dir.exists() else []

    if rows and rows >= 1_000_000:
        status = "complete"
        blocker = False
        summary = f"clean financials available with {rows:,} rows"
    elif parquet_files:
        status = "partial"
        blocker = True
        summary = "financial Parquet exists, but row-count evidence is missing or too small"
    else:
        status = "missing"
        blocker = True
        summary = "clean financials are missing"

    return CheckResult(
        name="financials",
        status=status,
        train_blocker=blocker,
        summary=summary,
        evidence={
            "clean_dir": str(clean_dir),
            "manifest_rows": rows,
            "parquet_files": len(parquet_files),
            "manifest": manifest,
        },
    )


def check_inpi(data_lake: Path, source_dir: Path) -> CheckResult:
    source_files = {}
    for name in EXPECTED_INPI_ZIPS:
        path = _find_file(source_dir, name)
        part = _find_file(source_dir, f"{name}.part")
        source_files[name] = {
            "zip_exists": path is not None,
            "part_exists": part is not None,
            "zip_path": str(path) if path else None,
            "part_path": str(part) if part else None,
            "zip_size_bytes": path.stat().st_size if path and path.exists() else None,
            "part_size_bytes": part.stat().st_size if part and part.exists() else None,
        }

    missing = [name for name, item in source_files.items() if not item["zip_exists"]]
    downloading = [name for name, item in source_files.items() if item["part_exists"]]

    raw_root = data_lake / "raw" / "inpi"
    manifests = _manifest_index(raw_root)
    exported_roots = {Path(item["path"]).parent.name for item in manifests}

    if downloading:
        status = "in_progress"
        summary = f"{len(downloading)} expected INPI ZIP is still downloading"
    elif missing:
        status = "partial"
        summary = f"{len(missing)} expected INPI ZIP file(s) are missing"
    elif len(manifests) < len(EXPECTED_INPI_ZIPS):
        status = "partial"
        summary = "all expected INPI ZIPs exist, but not all Parquet manifests are present"
    else:
        status = "complete"
        summary = "all expected INPI ZIPs and Parquet manifests are present"

    return CheckResult(
        name="inpi",
        status=status,
        train_blocker=status != "complete",
        summary=summary,
        evidence={
            "expected_zips": source_files,
            "missing_zips": missing,
            "downloading_zips": downloading,
            "raw_root": str(raw_root),
            "manifest_count": len(manifests),
            "exported_roots": sorted(exported_roots),
        },
    )


def check_insee(data_lake: Path) -> CheckResult:
    raw_root = data_lake / "raw" / "insee"
    manifests = _manifest_index(raw_root)
    rows = sum(_int_or_none(item["manifest"].get("rows")) or 0 for item in manifests)
    sources = [str(item["manifest"].get("source") or "") for item in manifests]
    has_bulk = any("bulk" in source.lower() or "stock" in source.lower() for source in sources)

    if has_bulk and rows > 1_000_000:
        status = "complete"
        blocker = False
        summary = f"bulk INSEE evidence available with {rows:,} rows"
    elif rows:
        status = "smoke"
        blocker = True
        summary = f"only API/smoke INSEE evidence is present with {rows:,} rows"
    else:
        status = "missing"
        blocker = True
        summary = "INSEE raw evidence is missing"

    return CheckResult(
        name="insee",
        status=status,
        train_blocker=blocker,
        summary=summary,
        evidence={"raw_root": str(raw_root), "rows": rows, "manifest_count": len(manifests), "sources": sources},
    )


def check_bodacc(data_lake: Path) -> CheckResult:
    raw_root = data_lake / "raw" / "bodacc"
    manifests = _manifest_index(raw_root)
    paths = [Path(item["path"]) for item in manifests]
    current_pcl = [path for path in paths if "current" in path.parts and _contains_family(path, "PCL")]
    current_rcsb = [path for path in paths if "current" in path.parts and _contains_family(path, "RCS-B")]
    historical_pcl = [path for path in paths if "current" not in path.parts and _contains_family(path, "PCL")]
    historical_rcsb = [path for path in paths if "current" not in path.parts and _contains_family(path, "RCS-B")]

    if historical_pcl and historical_rcsb:
        status = "complete"
        blocker = False
        summary = "historical BODACC PCL and RCS-B manifests are present"
    elif current_pcl or current_rcsb:
        status = "partial"
        blocker = True
        summary = "BODACC current-year label evidence exists, but historical PCL/RCS-B are missing"
    elif manifests:
        status = "partial"
        blocker = True
        summary = "BODACC manifests exist, but label-source families are missing"
    else:
        status = "missing"
        blocker = True
        summary = "BODACC raw evidence is missing"

    return CheckResult(
        name="bodacc",
        status=status,
        train_blocker=blocker,
        summary=summary,
        evidence={
            "raw_root": str(raw_root),
            "manifest_count": len(manifests),
            "current_pcl_manifests": len(current_pcl),
            "current_rcs_b_manifests": len(current_rcsb),
            "historical_pcl_manifests": len(historical_pcl),
            "historical_rcs_b_manifests": len(historical_rcsb),
        },
    )


def check_features(data_lake: Path, source_results: list[CheckResult]) -> CheckResult:
    feature_root = data_lake / "features"
    datasets = {
        "company_year_features": feature_root / "company_year_features" / "_manifest.json",
        "risk_labels": feature_root / "risk_labels" / "_manifest.json",
        "company_features": feature_root / "company_features" / "_manifest.json",
    }
    manifests = {name: _read_json(path) for name, path in datasets.items()}
    rows = {name: _int_or_none((manifest or {}).get("rows")) for name, manifest in manifests.items()}
    upstream_blockers = [result.name for result in source_results if result.train_blocker]

    if not any(rows.values()):
        status = "missing"
        blocker = True
        summary = "feature datasets are missing"
    elif upstream_blockers:
        status = "interim"
        blocker = True
        summary = "feature datasets exist, but upstream source coverage is incomplete"
    else:
        status = "complete"
        blocker = False
        summary = "feature datasets exist and upstream source checks passed"

    return CheckResult(
        name="features",
        status=status,
        train_blocker=blocker,
        summary=summary,
        evidence={
            "feature_root": str(feature_root),
            "rows": rows,
            "upstream_blockers": upstream_blockers,
            "manifests": manifests,
        },
    )


def _manifest_index(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    items = []
    for path in sorted(root.rglob("_manifest.json")):
        manifest = _read_json(path)
        if manifest is not None:
            items.append({"path": str(path), "manifest": manifest})
    return items


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _find_file(root: Path, name: str) -> Path | None:
    if not root.exists():
        return None
    direct = root / name
    if direct.exists():
        return direct
    matches = list(root.rglob(name))
    return matches[0] if matches else None


def _contains_family(path: Path, family: str) -> bool:
    normalized = str(path).replace("_", "-").upper()
    return family.upper() in normalized


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _default_data_lake_dir() -> str:
    if os.environ.get("DATA_LAKE_DIR"):
        return os.environ["DATA_LAKE_DIR"]
    if Path("D:/PFE_volumes/data-lake").exists():
        return "D:/PFE_volumes/data-lake"
    return "/data-lake"


def _default_inpi_source_dir() -> str:
    if os.environ.get("INPI_LOCAL_DATA_DIR"):
        return os.environ["INPI_LOCAL_DATA_DIR"]
    if Path("D:/PFE_volumes/inpi-data").exists():
        return "D:/PFE_volumes/inpi-data"
    return "/app/data/inpi"


def _print_human(payload: dict[str, Any]) -> None:
    print(f"Data lake: {payload['data_lake_dir']}")
    print(f"INPI source: {payload['inpi_source_dir']}")
    print(f"Training ready: {'yes' if payload['training_ready'] else 'no'}")
    print()
    for check in payload["checks"]:
        marker = "BLOCKS TRAINING" if check["train_blocker"] else "ok"
        print(f"[{check['status']}] {check['name']}: {check['summary']} ({marker})")
        evidence = check["evidence"]
        if check["name"] == "features":
            print(f"  rows: {evidence.get('rows')}")
        elif check["name"] == "inpi":
            print(f"  missing_zips: {evidence.get('missing_zips')}")
            print(f"  downloading_zips: {evidence.get('downloading_zips')}")
            print(f"  manifest_count: {evidence.get('manifest_count')}")
        elif "manifest_count" in evidence:
            print(f"  manifest_count: {evidence.get('manifest_count')}")
        if "manifest_rows" in evidence:
            print(f"  manifest_rows: {evidence.get('manifest_rows')}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local data-lake readiness without downloading anything.")
    parser.add_argument("--data-lake-dir", help="Data lake root. Defaults to DATA_LAKE_DIR or D:/PFE_volumes/data-lake.")
    parser.add_argument("--inpi-source-dir", help="INPI source ZIP root. Defaults to INPI_LOCAL_DATA_DIR or D:/PFE_volumes/inpi-data.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", help="Write the JSON readiness payload to this file.")
    parser.add_argument("--fail-on-not-ready", action="store_true", help="Exit with code 2 when training_ready is false.")
    return parser.parse_args()


if __name__ == "__main__":
    main()
