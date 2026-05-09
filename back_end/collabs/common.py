"""Shared helpers for Google Colab data-preparation scripts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_DRIVE_ROOT = "/content/drive/MyDrive/pfe_data"
DEFAULT_WORK_ROOT = "/content/pfe_work"
DATAGOUV_API_BASE = "https://www.data.gouv.fr/api/1"
FINANCIAL_DATASET_SLUG = "donnees-financieres-detaillees-des-entreprises-format-parquet"

INSEE_RESOURCES = [
    ("stock_unite_legale", "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockUniteLegale_utf8.parquet"),
    ("stock_etablissement", "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockEtablissement_utf8.parquet"),
    ("stock_unite_legale_historique", "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockUniteLegaleHistorique_utf8.parquet"),
    ("stock_etablissement_historique", "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockEtablissementHistorique_utf8.parquet"),
    ("stock_etablissement_liens_succession", "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockEtablissementLiensSuccession_utf8.parquet"),
]


def paths(drive_root: str | Path) -> dict[str, Path]:
    root = Path(drive_root).resolve()
    result = {
        "drive_root": root,
        "source_archives": root / "source-archives",
        "data_lake": root / "data-lake",
        "artifacts": root / "ml-artifacts",
    }
    for path in result.values():
        path.mkdir(parents=True, exist_ok=True)
    return result


def sync_file_to_drive(local_path: Path, local_root: Path, drive_root: Path) -> Path:
    target = drive_root / local_path.relative_to(local_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_path, target)
    return target


def sync_tree_to_drive(local_path: Path, local_root: Path, drive_root: Path) -> Path:
    target = drive_root / local_path.relative_to(local_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(local_path, target, dirs_exist_ok=True)
    return target


def seed_file_from_drive(local_path: Path, local_root: Path, drive_root: Path) -> bool:
    source = drive_root / local_path.relative_to(local_root)
    if not source.exists() or local_path.exists():
        return False
    local_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, local_path)
    return True


def storage_paths(drive_root: str | Path, work_dir: str | Path | None) -> tuple[dict[str, Path], dict[str, Path]]:
    drive_paths = paths(drive_root)
    if not work_dir:
        return drive_paths, drive_paths
    return drive_paths, paths(work_dir)


def pipeline_env(drive_root: str | Path) -> dict[str, str]:
    p = paths(drive_root)
    env = os.environ.copy()
    env.update(
        {
            "INGESTION_DATA_DIR": str(p["source_archives"]),
            "INPI_LOCAL_DATA_DIR": str(p["source_archives"] / "inpi"),
            "INSEE_BULK_SOURCE_DIR": str(p["source_archives"] / "insee" / "bulk"),
            "FINANCIAL_SOURCE_ARCHIVE_DIR": str(p["source_archives"] / "financials" / "data_gouv"),
            "DATA_LAKE_DIR": str(p["data_lake"]),
            "ML_ARTIFACTS_DIR": str(p["artifacts"]),
            "ML_MODEL_FILE": str(p["artifacts"] / "model.joblib"),
        }
    )
    return env


def install_deps(repo_dir: str | Path) -> None:
    repo_path = Path(repo_dir)
    colab_requirements = repo_path / "collabs" / "requirements-colab.txt"
    requirements = colab_requirements if colab_requirements.exists() else repo_path / "requirements.txt"
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements)], repo_dir)


def run(command: list[str], cwd: str | Path, env: dict[str, str] | None = None) -> None:
    command = _unbuffer_python(command)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env["PYTHONUNBUFFERED"] = "1"
    print("[run]", " ".join(command))
    subprocess.run(command, cwd=str(cwd), env=merged_env, check=True)


def _unbuffer_python(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = Path(command[0]).name.lower()
    if not executable.startswith("python"):
        return command
    if len(command) > 1 and command[1] == "-u":
        return command
    return [command[0], "-u", *command[1:]]


def read_json_url(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "pfe-colab-ml-pipeline/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def append_status(
    drive_root: str | Path,
    *,
    step: str,
    status: str,
    command: list[str] | None = None,
    error: BaseException | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    report_dir = Path(drive_root).resolve() / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "pipeline_status.json"
    md_path = report_dir / "pipeline_status.md"
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {"steps": []}
    except json.JSONDecodeError:
        payload = {"steps": []}
    entry: dict[str, Any] = {
        "step": step,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if command:
        entry["command"] = command
    if details:
        entry["details"] = details
    if error:
        entry["error_type"] = type(error).__name__
        entry["error"] = str(error)
        entry["traceback"] = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if isinstance(error, subprocess.CalledProcessError):
            entry["returncode"] = error.returncode
    payload["steps"].append(entry)
    payload["updated_at"] = entry["timestamp"]
    write_json(json_path, payload)
    write_pipeline_status_markdown(md_path, payload)


def write_pipeline_status_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = payload.get("steps", [])
    lines = [
        "# Pipeline Status",
        "",
        f"Updated at: `{payload.get('updated_at', '')}`",
        "",
        "| Step | Status | Time | Notes |",
        "|---|---|---|---|",
    ]
    for row in rows:
        notes = row.get("error") or ""
        if row.get("returncode") is not None:
            notes = f"returncode={row['returncode']} {notes}".strip()
        notes = str(notes).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{row.get('step', '')}` | `{row.get('status', '')}` | `{row.get('timestamp', '')}` | {notes} |")
    failures = [row for row in rows if row.get("status") == "failed"]
    if failures:
        lines.extend(["", "## Failures", ""])
        for row in failures:
            lines.extend(
                [
                    f"### {row.get('step', '')}",
                    "",
                    f"- Error: `{row.get('error_type', '')}` {row.get('error', '')}",
                    f"- Return code: `{row.get('returncode', '')}`",
                    "",
                    "```text",
                    row.get("traceback", "").strip(),
                    "```",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def download_resumable(url: str, path: Path, *, overwrite: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        print(f"[download] skip existing {path} ({path.stat().st_size:,} bytes)")
        return path

    tmp = path.with_suffix(path.suffix + ".tmp")
    if overwrite and tmp.exists():
        tmp.unlink()

    resume_from = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": "pfe-colab-ml-pipeline/1.0", "Accept-Encoding": "identity"}
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"

    print(f"[download] {'resume' if resume_from else 'start'} {url}")
    request = Request(url, headers=headers)
    try:
        response = urlopen(request, timeout=60)
    except HTTPError as exc:
        if resume_from and exc.code == 416:
            tmp.rename(path)
            print(f"[download] completed from existing tmp {path}")
            return path
        raise

    with response:
        if resume_from and response.status != 206:
            print("[download] server ignored Range; restarting this file")
            tmp.unlink(missing_ok=True)
            resume_from = 0
        total = total_size(response.headers, resume_from)
        written = resume_from
        last_logged = written
        mode = "ab" if resume_from else "wb"
        started = time.monotonic()
        with tmp.open(mode) as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                if written - last_logged >= 100 * 1024 * 1024:
                    print_progress(path.name, written, total, started)
                    last_logged = written

    tmp.rename(path)
    print_progress(path.name, path.stat().st_size, total, started)
    return path


def total_size(headers: Any, resume_from: int) -> int | None:
    content_range = headers.get("Content-Range")
    if content_range and "/" in content_range:
        try:
            return int(content_range.rsplit("/", 1)[1])
        except ValueError:
            return None
    content_length = headers.get("Content-Length")
    if content_length:
        try:
            return int(content_length) + resume_from
        except ValueError:
            return None
    return None


def print_progress(name: str, written: int, total: int | None, started: float) -> None:
    elapsed = max(time.monotonic() - started, 1.0)
    mb = written / 1024 / 1024
    speed = mb / elapsed
    if total:
        percent = min(written / total * 100, 100.0)
        print(f"[download] {name}: {mb:,.1f} MB / {total / 1024 / 1024:,.1f} MB ({percent:.2f}%), {speed:.1f} MB/s")
    else:
        print(f"[download] {name}: {mb:,.1f} MB, {speed:.1f} MB/s")


def print_outputs(drive_root: str | Path) -> None:
    p = paths(drive_root)
    print("\nMain outputs:")
    for path in [
        p["data_lake"] / "features" / "company_year_features",
        p["data_lake"] / "features" / "risk_labels",
        p["data_lake"] / "features" / "company_features",
        p["artifacts"],
        p["drive_root"] / "reports",
    ]:
        print(f"- {path}")
