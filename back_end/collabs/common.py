"""Shared helpers for Google Colab data-preparation scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_DRIVE_ROOT = "/content/drive/MyDrive/pfe_data"
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
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(Path(repo_dir) / "requirements.txt")], repo_dir)


def run(command: list[str], cwd: str | Path, env: dict[str, str] | None = None) -> None:
    print("[run]", " ".join(command))
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def read_json_url(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "pfe-colab-ml-pipeline/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


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
    ]:
        print(f"- {path}")
