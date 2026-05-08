from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument

from app.core.config import settings

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"starting", "downloading", "cancelling"}


class FinancialExportAlreadyRunning(Exception):
    pass


class FinancialExportCancelled(Exception):
    pass


@dataclass(frozen=True)
class FinancialResource:
    resource_id: str | None
    title: str
    url: str
    filename: str
    format: str | None
    filesize: int | None
    last_modified: str | None


class FinancialDataLakeService:
    """Download data.gouv.fr financial Parquet resources to the data lake."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.dataset_slug = settings.FINANCIAL_EXPORT_DATASET_SLUG
        self.output_base = Path(settings.DATA_LAKE_DIR) / "raw" / "financials"
        self.source_base = Path(settings.FINANCIAL_SOURCE_ARCHIVE_DIR)
        self.output_base.mkdir(parents=True, exist_ok=True)
        self.source_base.mkdir(parents=True, exist_ok=True)

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)

    async def list_resources(self) -> dict[str, Any]:
        meta = await self._fetch_dataset_meta()
        resources = [_resource_from_meta(item) for item in meta.get("resources", [])]
        parquet_resources = [
            resource for resource in resources if (resource.format or "").lower() == "parquet"
        ]
        return {
            "dataset_slug": settings.DATAGOUV_DATASET_SLUG,
            "title": meta.get("title"),
            "last_update": meta.get("last_update"),
            "resources": [
                {
                    "resource_id": resource.resource_id,
                    "title": resource.title,
                    "url": resource.url,
                    "filename": resource.filename,
                    "format": resource.format,
                    "filesize": resource.filesize,
                    "last_modified": resource.last_modified,
                }
                for resource in parquet_resources
            ],
        }

    async def start(
        self,
        *,
        resource_id: str | None = None,
        resource_url: str | None = None,
        run_name: str | None = None,
        overwrite: bool = False,
    ) -> str:
        await self.ensure_indexes()
        run_id = str(uuid4())
        await self._get_state()
        state = await self.state_coll.find_one_and_update(
            {
                "dataset_slug": self.dataset_slug,
                "$or": [{"run_id": {"$exists": False}}, {"run_id": None}],
            },
            {
                "$set": {
                    "run_id": run_id,
                    "status": "starting",
                    "cancel_requested": False,
                    "resource_id_requested": resource_id,
                    "resource_url_requested": resource_url,
                    "run_name_requested": run_name,
                    "overwrite_requested": overwrite,
                    "output_dir": None,
                    "output_file": None,
                    "downloaded_bytes": 0,
                    "download_total_bytes": None,
                    "download_progress_percent": None,
                    "last_error": None,
                    "last_started_at": _utcnow(),
                    "updated_at": _utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if state is None:
            current = await self._get_state()
            raise FinancialExportAlreadyRunning(
                f"financial export already running with status={current.get('status', 'unknown')}"
            )
        return run_id

    async def run_started(
        self,
        run_id: str,
        *,
        resource_id: str | None = None,
        resource_url: str | None = None,
        run_name: str | None = None,
        overwrite: bool = False,
    ) -> None:
        try:
            resource = await self._select_resource(resource_id=resource_id, resource_url=resource_url)
            output_dir = self._output_dir(run_name, resource)
            output_file = output_dir / resource.filename
            source_dir = self._source_dir(run_name, resource)
            source_file = source_dir / resource.filename
            _prepare_output_dir(output_dir, self.output_base, overwrite)
            _prepare_output_dir(source_dir, self.source_base, overwrite)
            await self._update_state_owned(
                run_id,
                {
                    "status": "downloading",
                    "resource_id": resource.resource_id,
                    "resource_title": resource.title,
                    "resource_url": resource.url,
                    "source_archive_dir": str(source_dir),
                    "source_archive_file": str(source_file),
                    "output_dir": str(output_dir),
                    "output_file": str(output_file),
                    "downloaded_bytes": 0,
                    "download_total_bytes": resource.filesize,
                    "download_progress_percent": 0.0 if resource.filesize else None,
                    "updated_at": _utcnow(),
                },
            )

            await self._download_resource(resource, source_file, run_id)
            _validate_parquet_magic(source_file)
            _copy_source_to_raw(source_file, output_file)
            _validate_parquet_magic(output_file)
            manifest = {
                "source": "data.gouv.fr",
                "dataset_slug": settings.DATAGOUV_DATASET_SLUG,
                "resource_id": resource.resource_id,
                "resource_title": resource.title,
                "resource_url": resource.url,
                "resource_last_modified": resource.last_modified,
                "resource_filesize": resource.filesize,
                "source_archive_file": str(source_file),
                "output_file": str(output_file),
                "size_bytes": output_file.stat().st_size,
                "downloaded_at": _utcnow().isoformat(),
            }
            (output_dir / "_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            await self._update_state_owned(
                run_id,
                {
                    "status": "done",
                    "downloaded_bytes": output_file.stat().st_size,
                    "download_progress_percent": 100.0,
                    "last_successful_run": _utcnow(),
                    "last_error": None,
                    "updated_at": _utcnow(),
                },
            )
        except FinancialExportCancelled:
            await self._update_state_owned(
                run_id,
                {"status": "cancelled", "cancel_requested": False, "updated_at": _utcnow()},
            )
            raise
        except Exception as exc:
            await self._update_state_owned(
                run_id,
                {"status": "error", "last_error": str(exc), "updated_at": _utcnow()},
            )
            logger.exception("[financial-export] run failed")
            raise
        finally:
            await self._release_run(run_id)

    async def run(
        self,
        *,
        resource_id: str | None = None,
        resource_url: str | None = None,
        run_name: str | None = None,
        overwrite: bool = False,
    ) -> None:
        run_id = await self.start(
            resource_id=resource_id,
            resource_url=resource_url,
            run_name=run_name,
            overwrite=overwrite,
        )
        await self.run_started(
            run_id,
            resource_id=resource_id,
            resource_url=resource_url,
            run_name=run_name,
            overwrite=overwrite,
        )

    async def get_status(self) -> dict[str, Any]:
        state = await self._get_state()
        state.pop("_id", None)
        return state

    async def request_cancel(self) -> dict[str, Any]:
        state = await self._get_state()
        if state.get("status") not in ACTIVE_STATUSES:
            return {"accepted": False, "status": state.get("status", "idle")}
        await self._update_state({"cancel_requested": True, "status": "cancelling", "updated_at": _utcnow()})
        return {"accepted": True, "status": "cancelling"}

    async def list_local_files(self) -> dict[str, Any]:
        files = []
        for parquet_path in sorted(self.output_base.rglob("*.parquet")):
            manifest = _read_manifest(parquet_path.parent)
            files.append(
                {
                    "path": str(parquet_path),
                    "size_bytes": parquet_path.stat().st_size,
                    "output_dir": str(parquet_path.parent),
                    "manifest": manifest,
                }
            )
        return {"root": str(self.output_base), "count": len(files), "files": files}

    async def _fetch_dataset_meta(self) -> dict[str, Any]:
        url = f"{settings.DATAGOUV_API_BASE}/datasets/{settings.DATAGOUV_DATASET_SLUG}/"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _select_resource(
        self,
        *,
        resource_id: str | None,
        resource_url: str | None,
    ) -> FinancialResource:
        resources = [
            _resource_from_meta(item)
            for item in (await self._fetch_dataset_meta()).get("resources", [])
            if str(item.get("format", "")).lower() == "parquet"
        ]
        if resource_url:
            for resource in resources:
                if resource.url == resource_url:
                    return resource
            return FinancialResource(
                resource_id=resource_id,
                title=Path(resource_url).name or "financial_resource",
                url=resource_url,
                filename=_filename_from_url(resource_url),
                format="parquet",
                filesize=None,
                last_modified=None,
            )
        if resource_id:
            for resource in resources:
                if resource.resource_id == resource_id:
                    return resource
            raise ValueError(f"financial resource not found: {resource_id}")
        if not resources:
            raise ValueError("no Parquet resource found on data.gouv.fr dataset")
        return resources[0]

    def _output_dir(self, run_name: str | None, resource: FinancialResource) -> Path:
        name = run_name or _safe_name(resource.title or resource.filename)
        return self.output_base / name

    def _source_dir(self, run_name: str | None, resource: FinancialResource) -> Path:
        name = run_name or _safe_name(resource.title or resource.filename)
        return self.source_base / name

    async def _download_resource(self, resource: FinancialResource, output_file: Path, run_id: str) -> None:
        tmp = output_file.with_suffix(output_file.suffix + ".tmp")
        if tmp.exists():
            tmp.unlink()
        bytes_written = 0
        total = resource.filesize
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", resource.url, headers={"Accept-Encoding": "identity"}) as response:
                response.raise_for_status()
                header_total = int(response.headers.get("content-length", "0") or 0) or None
                total = total or header_total
                with tmp.open("wb") as handle:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        await self._check_cancel(run_id)
                        handle.write(chunk)
                        bytes_written += len(chunk)
                        if bytes_written % (50 * 1024 * 1024) < len(chunk):
                            await self._update_state_owned(
                                run_id,
                                {
                                    "downloaded_bytes": bytes_written,
                                    "download_total_bytes": total,
                                    "download_progress_percent": _progress_percent(bytes_written, total),
                                    "updated_at": _utcnow(),
                                },
                            )
        if total and bytes_written < total:
            raise RuntimeError(f"incomplete download: {bytes_written} < {total}")
        if output_file.exists():
            output_file.unlink()
        os.replace(tmp, output_file)

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": self.dataset_slug})
        if doc is None:
            doc = {
                "dataset_slug": self.dataset_slug,
                "status": "idle",
                "run_id": None,
                "downloaded_bytes": 0,
            }
            await self.state_coll.insert_one(doc)
        return doc

    async def _update_state(self, fields: dict[str, Any]) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug},
            {"$set": fields},
            upsert=True,
        )

    async def _update_state_owned(self, run_id: str, fields: dict[str, Any]) -> None:
        result = await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {"$set": fields},
        )
        if result.matched_count == 0:
            raise FinancialExportAlreadyRunning("financial export ownership lost")

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {
                "$set": {"run_id": None, "updated_at": _utcnow()},
                "$unset": {
                    "resource_id_requested": "",
                    "resource_url_requested": "",
                    "run_name_requested": "",
                    "overwrite_requested": "",
                },
            },
        )

    async def _check_cancel(self, run_id: str) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return
        await self._update_state_owned(run_id, {"status": "cancelled", "cancel_requested": False})
        raise FinancialExportCancelled("financial export cancelled by user")


def _resource_from_meta(item: dict[str, Any]) -> FinancialResource:
    url = str(item.get("url") or item.get("latest") or "")
    title = str(item.get("title") or item.get("description") or _filename_from_url(url))
    return FinancialResource(
        resource_id=item.get("id"),
        title=title,
        url=url,
        filename=_filename_from_url(url, title),
        format=item.get("format"),
        filesize=_int_or_none(item.get("filesize") or item.get("filetype_size")),
        last_modified=item.get("last_modified") or item.get("published") or item.get("created_at"),
    )


def _filename_from_url(url: str, fallback: str | None = None) -> str:
    candidate = Path(url.split("?", 1)[0]).name or fallback or "financial_source.parquet"
    if not candidate.lower().endswith(".parquet"):
        candidate = f"{_safe_name(candidate)}.parquet"
    return candidate


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return cleaned[:120] or "financial_source"


def _prepare_output_dir(path: Path, root: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise FileExistsError(f"financial output already exists: {path}")
        resolved = path.resolve()
        root_resolved = root.resolve()
        if root_resolved not in resolved.parents and resolved != root_resolved:
            raise RuntimeError(f"refusing to delete output outside financial data-lake root: {path}")
        import shutil

        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_source_to_raw(source_file: Path, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_file.with_suffix(output_file.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(source_file, tmp)
    if output_file.exists():
        output_file.unlink()
    os.replace(tmp, output_file)


def _validate_parquet_magic(path: Path) -> None:
    if path.stat().st_size < 8:
        raise RuntimeError(f"downloaded file is too small to be Parquet: {path}")
    with path.open("rb") as handle:
        head = handle.read(4)
        handle.seek(-4, os.SEEK_END)
        tail = handle.read(4)
    if head != b"PAR1" or tail != b"PAR1":
        raise RuntimeError(f"downloaded file is not a valid Parquet file: {path}")


def _read_manifest(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _progress_percent(done: int, total: int | None) -> float | None:
    if not total:
        return None
    return round(min(100.0, (done / total) * 100), 2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
