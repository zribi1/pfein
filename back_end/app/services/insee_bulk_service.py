from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument

from app.core.config import settings
from app.tools.insee_bulk_to_parquet import export_insee_bulk_file

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"starting", "downloading", "exporting", "cancelling"}
PROGRESS_LOG_INTERVAL_BYTES = 50 * 1024 * 1024


class InseeBulkAlreadyRunning(Exception):
    pass


class InseeBulkCancelled(Exception):
    pass


@dataclass(frozen=True)
class InseeBulkResource:
    resource_id: str | None
    title: str
    url: str
    filename: str
    format: str | None
    filesize: int | None
    last_modified: str | None
    dataset_type: str | None
    checksum: str | None = None
    checksum_type: str | None = None
    etag: str | None = None


class InseeBulkService:
    """Download and export INSEE Sirene bulk files as the primary INSEE path."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.dataset_slug = settings.INSEE_BULK_EXPORT_DATASET_SLUG
        self.source_base = Path(settings.INSEE_BULK_SOURCE_DIR)
        self.raw_base = Path(settings.DATA_LAKE_DIR) / "raw" / "insee" / "bulk"
        self.source_base.mkdir(parents=True, exist_ok=True)
        self.raw_base.mkdir(parents=True, exist_ok=True)

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)

    async def list_resources(self) -> dict[str, Any]:
        meta = await self._fetch_dataset_meta()
        resources = [_resource_from_meta(item) for item in meta.get("resources", [])]
        resources = [resource for resource in resources if _supported_resource(resource)]
        return {
            "dataset_slug": settings.INSEE_BULK_DATASET_SLUG,
            "title": meta.get("title"),
            "last_update": meta.get("last_update"),
            "source_dir": str(self.source_base),
            "resources": [
                {
                    "resource_id": resource.resource_id,
                    "title": resource.title,
                    "url": resource.url,
                    "filename": resource.filename,
                    "format": resource.format,
                    "filesize": resource.filesize,
                    "last_modified": resource.last_modified,
                    "checksum": resource.checksum,
                    "checksum_type": resource.checksum_type,
                    "etag": resource.etag,
                    "dataset_type": resource.dataset_type,
                    "downloaded": (self.source_base / (resource.dataset_type or "unknown") / resource.filename).exists(),
                }
                for resource in resources
                if resource.dataset_type is not None
            ],
        }

    async def list_local_files(self) -> dict[str, Any]:
        files = []
        for path in sorted(self.source_base.rglob("*")):
            if not path.is_file() or path.name.endswith(".tmp") or path.name.endswith(".manifest.json"):
                continue
            dataset_type = _detect_dataset_type_from_name(path.name)
            output_dir = (
                Path(settings.DATA_LAKE_DIR)
                / "raw"
                / "insee"
                / "bulk"
                / (dataset_type or "unknown")
                / _source_stem(path)
            )
            manifest = _read_manifest(output_dir)
            files.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "dataset_type": dataset_type,
                    "output_dir": str(output_dir),
                    "exported": manifest is not None,
                    "manifest_rows": manifest.get("rows") if manifest else None,
                }
            )
        return {"source_dir": str(self.source_base), "count": len(files), "files": files}

    async def start(
        self,
        *,
        resource_id: str | None = None,
        resource_url: str | None = None,
        download: bool = True,
        export: bool = True,
        overwrite: bool = False,
        max_files: int | None = None,
        count_rows: bool = False,
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
                    "download_requested": download,
                    "export_requested": export,
                    "overwrite_requested": overwrite,
                    "max_files_requested": max_files,
                    "count_rows_requested": count_rows,
                    "discovered": 0,
                    "downloaded": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                    "rows": 0,
                    "current_file": "",
                    "current_file_downloaded_bytes": 0,
                    "current_file_total_bytes": None,
                    "current_file_progress_percent": None,
                    "failed_files": [],
                    "last_error": None,
                    "last_started_at": _utcnow(),
                    "updated_at": _utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if state is None:
            current = await self._get_state()
            raise InseeBulkAlreadyRunning(
                f"insee bulk export already running with status={current.get('status', 'unknown')}"
            )
        return run_id

    async def run_started(
        self,
        run_id: str,
        *,
        resource_id: str | None = None,
        resource_url: str | None = None,
        download: bool = True,
        export: bool = True,
        overwrite: bool = False,
        max_files: int | None = None,
        count_rows: bool = False,
    ) -> None:
        stats: dict[str, Any] = {"discovered": 0, "downloaded": 0, "processed": 0, "skipped": 0, "failed": 0, "rows": 0, "failed_files": []}
        try:
            local_files: list[Path] = []
            if download:
                await self._update_state_owned(run_id, {"status": "downloading", "updated_at": _utcnow()})
                resources = await self._selected_resources(resource_id=resource_id, resource_url=resource_url)
                stats["discovered"] = len(resources)
                for resource in resources[: max_files or len(resources)]:
                    await self._check_cancel(run_id)
                    local_files.append(await self._download_resource(run_id, resource, overwrite=overwrite, stats=stats))
            else:
                local_files = await asyncio.to_thread(self._discover_local_files)
                stats["discovered"] = len(local_files)

            if export:
                await self._update_state_owned(run_id, {"status": "exporting", "updated_at": _utcnow(), **stats})
                handled = 0
                for local_file in local_files:
                    await self._check_cancel(run_id)
                    if max_files is not None and handled >= max_files:
                        break
                    handled += 1
                    await self._export_local_file(run_id, local_file, overwrite=overwrite, count_rows=count_rows, stats=stats)

            status = "done" if stats["failed"] == 0 else "done_with_failures"
            fields: dict[str, Any] = {
                "status": status,
                "current_file": "",
                "current_file_downloaded_bytes": 0,
                "current_file_total_bytes": None,
                "current_file_progress_percent": None,
                "last_error": None if stats["failed"] == 0 else f"{stats['failed']} file(s) failed",
                "last_successful_run": _utcnow() if stats["failed"] == 0 else None,
                "updated_at": _utcnow(),
                **stats,
            }
            await self._update_state_owned(run_id, fields)
        except InseeBulkCancelled:
            await self._update_state_owned(run_id, {"status": "cancelled", "cancel_requested": False, "updated_at": _utcnow(), **stats})
            raise
        except Exception as exc:
            await self._update_state_owned(run_id, {"status": "error", "last_error": str(exc), "updated_at": _utcnow(), **stats})
            logger.exception("[insee-bulk] run failed")
            raise
        finally:
            await self._release_run(run_id)

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

    async def _selected_resources(self, *, resource_id: str | None, resource_url: str | None) -> list[InseeBulkResource]:
        resources = [_resource_from_meta(item) for item in (await self._fetch_dataset_meta()).get("resources", [])]
        resources = [resource for resource in resources if resource.dataset_type is not None and _supported_resource(resource)]
        if resource_url:
            return [resource for resource in resources if resource.url == resource_url] or [
                InseeBulkResource(
                    resource_id=resource_id,
                    title=Path(resource_url).name,
                    url=resource_url,
                    filename=_filename_from_url(resource_url),
                    format=None,
                    filesize=None,
                    last_modified=None,
                    dataset_type=_detect_dataset_type_from_name(resource_url),
                    checksum=None,
                    checksum_type=None,
                    etag=None,
                )
            ]
        if resource_id:
            matches = [resource for resource in resources if resource.resource_id == resource_id]
            if not matches:
                raise ValueError(f"insee bulk resource not found: {resource_id}")
            return matches
        priority = ["stock_unite_legale", "stock_etablissement", "stock_unite_legale_historique", "stock_etablissement_historique", "stock_etablissement_liens_succession"]
        selected: list[InseeBulkResource] = []
        for dataset_type in priority:
            matches = [resource for resource in resources if resource.dataset_type == dataset_type]
            if matches:
                selected.append(_preferred_resource(matches))
        if not selected:
            raise ValueError("no INSEE bulk resources found")
        return selected

    async def _download_resource(
        self,
        run_id: str,
        resource: InseeBulkResource,
        *,
        overwrite: bool,
        stats: dict[str, Any],
    ) -> Path:
        dataset_type = resource.dataset_type or "unknown"
        output_dir = self.source_base / dataset_type
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / resource.filename
        expected_size = resource.filesize
        if output_file.exists() and not overwrite and _source_file_is_current(output_file, resource):
            stats["skipped"] += 1
            await self._update_state_owned(
                run_id,
                {
                    "current_file": str(output_file),
                    "current_file_downloaded_bytes": output_file.stat().st_size,
                    "current_file_total_bytes": expected_size,
                    "current_file_progress_percent": _progress_percent(output_file.stat().st_size, expected_size),
                    "updated_at": _utcnow(),
                    **stats,
                },
            )
            logger.info("[insee-bulk] source already complete file=%s size=%s", output_file, output_file.stat().st_size)
            return output_file

        tmp = output_file.with_suffix(output_file.suffix + ".tmp")
        if overwrite and tmp.exists():
            tmp.unlink()
        if output_file.exists() and not _file_matches_expected_size(output_file, expected_size):
            logger.warning(
                "[insee-bulk] replacing incomplete source file=%s size=%s expected=%s",
                output_file,
                output_file.stat().st_size,
                expected_size,
            )
            output_file.replace(tmp)
        if tmp.exists() and _file_matches_expected_size(tmp, expected_size):
            os.replace(tmp, output_file)
            stats["downloaded"] += 1
            await self._update_download_progress(run_id, output_file, output_file.stat().st_size, expected_size, stats)
            logger.info("[insee-bulk] recovered complete tmp file=%s size=%s", output_file, output_file.stat().st_size)
            return output_file

        resume_from = tmp.stat().st_size if tmp.exists() and not overwrite else 0
        await self._update_download_progress(run_id, output_file, resume_from, expected_size, stats)
        if resume_from:
            logger.info("[insee-bulk] resuming download file=%s from_byte=%s expected=%s", output_file, resume_from, expected_size)
        else:
            logger.info("[insee-bulk] starting download file=%s expected=%s", output_file, expected_size)

        bytes_written = resume_from
        headers = {"Accept-Encoding": "identity"}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", resource.url, headers=headers) as response:
                response.raise_for_status()
                if resume_from and response.status_code != 206:
                    logger.warning(
                        "[insee-bulk] server ignored resume range; restarting file=%s from scratch",
                        output_file,
                    )
                    tmp.unlink(missing_ok=True)
                    bytes_written = 0
                    resume_from = 0
                mode = "ab" if resume_from else "wb"
                last_logged_bytes = bytes_written
                with tmp.open(mode) as handle:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        await self._check_cancel(run_id)
                        handle.write(chunk)
                        bytes_written += len(chunk)
                        if bytes_written - last_logged_bytes >= PROGRESS_LOG_INTERVAL_BYTES:
                            await self._update_download_progress(run_id, output_file, bytes_written, expected_size, stats)
                            logger.info(
                                "[insee-bulk] download progress file=%s bytes=%s total=%s percent=%s",
                                output_file,
                                bytes_written,
                                expected_size,
                                _progress_percent(bytes_written, expected_size),
                            )
                            last_logged_bytes = bytes_written
        if expected_size is not None and bytes_written != expected_size:
            await self._update_download_progress(run_id, output_file, bytes_written, expected_size, stats)
            raise IOError(f"incomplete INSEE download for {output_file}: received {bytes_written} bytes, expected {expected_size}")
        if output_file.exists():
            output_file.unlink()
        os.replace(tmp, output_file)
        stats["downloaded"] += 1
        _write_json(output_file.with_suffix(output_file.suffix + ".manifest.json"), {
            "source": "data.gouv.fr",
            "dataset_slug": settings.INSEE_BULK_DATASET_SLUG,
            "resource_id": resource.resource_id,
            "resource_title": resource.title,
            "resource_url": resource.url,
            "resource_last_modified": resource.last_modified,
            "resource_checksum": resource.checksum,
            "resource_checksum_type": resource.checksum_type,
            "resource_etag": resource.etag,
            "dataset_type": dataset_type,
            "size_bytes": output_file.stat().st_size,
            "downloaded_at": _utcnow().isoformat(),
        })
        await self._update_download_progress(run_id, output_file, output_file.stat().st_size, expected_size, stats)
        logger.info("[insee-bulk] download complete file=%s size=%s", output_file, output_file.stat().st_size)
        return output_file

    async def _export_local_file(self, run_id: str, path: Path, *, overwrite: bool, count_rows: bool, stats: dict[str, Any]) -> None:
        try:
            await self._update_state_owned(run_id, {"current_file": str(path), "updated_at": _utcnow(), **stats})
            output_dir = await asyncio.to_thread(
                export_insee_bulk_file,
                input_path=path,
                output_base=Path(settings.DATA_LAKE_DIR),
                dataset_type="auto",
                overwrite=overwrite,
                count_rows=count_rows,
            )
            manifest = _read_manifest(output_dir) or {}
            stats["processed"] += 1
            stats["rows"] += int(manifest.get("rows") or 0)
        except Exception as exc:
            stats["failed"] += 1
            stats["failed_files"].append(str(path))
            await self._update_state_owned(run_id, {"last_error": str(exc), "updated_at": _utcnow(), **stats})

    def _discover_local_files(self) -> list[Path]:
        suffixes = (".csv", ".csv.gz", ".txt", ".txt.gz", ".parquet")
        return sorted(path for path in self.source_base.rglob("*") if path.is_file() and path.name.lower().endswith(suffixes))

    async def _fetch_dataset_meta(self) -> dict[str, Any]:
        url = f"{settings.DATAGOUV_API_BASE}/datasets/{settings.INSEE_BULK_DATASET_SLUG}/"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": self.dataset_slug})
        if doc is None:
            doc = {"dataset_slug": self.dataset_slug, "status": "idle", "run_id": None, "rows": 0}
            await self.state_coll.insert_one(doc)
        return doc

    async def _update_state(self, fields: dict[str, Any]) -> None:
        await self.state_coll.update_one({"dataset_slug": self.dataset_slug}, {"$set": fields}, upsert=True)

    async def _update_state_owned(self, run_id: str, fields: dict[str, Any]) -> None:
        result = await self.state_coll.update_one({"dataset_slug": self.dataset_slug, "run_id": run_id}, {"$set": fields})
        if result.matched_count == 0:
            raise InseeBulkAlreadyRunning("insee bulk ownership lost")

    async def _update_download_progress(
        self,
        run_id: str,
        output_file: Path,
        downloaded_bytes: int,
        total_bytes: int | None,
        stats: dict[str, Any],
    ) -> None:
        await self._update_state_owned(
            run_id,
            {
                "current_file": str(output_file),
                "current_file_downloaded_bytes": downloaded_bytes,
                "current_file_total_bytes": total_bytes,
                "current_file_progress_percent": _progress_percent(downloaded_bytes, total_bytes),
                "updated_at": _utcnow(),
                **stats,
            },
        )

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {"$set": {"run_id": None, "updated_at": _utcnow()}, "$unset": {"max_files_requested": "", "count_rows_requested": ""}},
        )

    async def _check_cancel(self, run_id: str) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return
        await self._update_state_owned(run_id, {"status": "cancelled", "cancel_requested": False})
        raise InseeBulkCancelled("insee bulk run cancelled by user")


def _resource_from_meta(item: dict[str, Any]) -> InseeBulkResource:
    url = str(item.get("url") or item.get("latest") or "")
    title = str(item.get("title") or item.get("description") or _filename_from_url(url))
    filename = _filename_from_url(url, title)
    checksum, checksum_type = _checksum_from_meta(item)
    return InseeBulkResource(
        resource_id=item.get("id"),
        title=title,
        url=url,
        filename=filename,
        format=item.get("format"),
        filesize=_int_or_none(item.get("filesize") or item.get("filetype_size")),
        last_modified=item.get("last_modified") or item.get("published") or item.get("created_at"),
        dataset_type=_detect_dataset_type_from_name(f"{title} {filename}"),
        checksum=checksum,
        checksum_type=checksum_type,
        etag=_string_or_none(item.get("etag") or item.get("etag_hash") or item.get("filetype_hash")),
    )


def _supported_resource(resource: InseeBulkResource) -> bool:
    name = resource.filename.lower()
    return name.endswith(".parquet") and _is_official_stock_file(name)


def _preferred_resource(resources: list[InseeBulkResource]) -> InseeBulkResource:
    for resource in resources:
        if resource.filename.lower().endswith(".parquet"):
            return resource
    return resources[0]


def _is_official_stock_file(name: str) -> bool:
    normalized = name.replace("-", "_").replace(" ", "")
    return normalized in {
        "stockunitelegale_utf8.parquet",
        "stocketablissement_utf8.parquet",
        "stockunitelegalehistorique_utf8.parquet",
        "stocketablissementhistorique_utf8.parquet",
        "stocketablissementlienssuccession_utf8.parquet",
    }


def _detect_dataset_type_from_name(name: str) -> str | None:
    normalized = name.lower().replace("-", "_").replace(".", "_")
    if "lienssuccession" in normalized or "liens_succession" in normalized:
        return "stock_etablissement_liens_succession"
    if "etablissementhistorique" in normalized or "etablissement_historique" in normalized:
        return "stock_etablissement_historique"
    if "unitelegalehistorique" in normalized or "unite_legale_historique" in normalized:
        return "stock_unite_legale_historique"
    if "etablissement" in normalized:
        return "stock_etablissement"
    if "unitelegale" in normalized or "unite_legale" in normalized:
        return "stock_unite_legale"
    return None


def _filename_from_url(url: str, fallback: str | None = None) -> str:
    candidate = Path(url.split("?", 1)[0]).name or fallback or "insee_bulk_source"
    return _safe_name(candidate)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return cleaned[:160] or "insee_bulk_source"


def _source_stem(path: Path) -> str:
    name = path.name
    for suffix in (".csv.gz", ".txt.gz", ".parquet", ".csv", ".txt"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _read_manifest(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _read_source_manifest(source_file: Path) -> dict[str, Any] | None:
    manifest_path = source_file.with_suffix(source_file.suffix + ".manifest.json")
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _source_file_is_current(path: Path, resource: InseeBulkResource) -> bool:
    if not _file_matches_expected_size(path, resource.filesize):
        return False
    manifest = _read_source_manifest(path)
    if manifest is None:
        return resource.checksum is None and resource.etag is None and resource.last_modified is None

    expected_fields = {
        "resource_url": resource.url,
        "resource_last_modified": resource.last_modified,
        "resource_checksum": resource.checksum,
        "resource_checksum_type": resource.checksum_type,
        "resource_etag": resource.etag,
    }
    for key, expected in expected_fields.items():
        if expected is not None and manifest.get(key) != expected:
            return False
    return int(manifest.get("size_bytes") or 0) == path.stat().st_size


def _file_matches_expected_size(path: Path, expected_size: int | None) -> bool:
    return path.exists() and (expected_size is None or path.stat().st_size == expected_size)


def _progress_percent(downloaded_bytes: int, total_bytes: int | None) -> float | None:
    if not total_bytes:
        return None
    return round(min(downloaded_bytes / total_bytes * 100, 100.0), 2)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _checksum_from_meta(item: dict[str, Any]) -> tuple[str | None, str | None]:
    checksum = item.get("checksum")
    if isinstance(checksum, dict):
        value = _string_or_none(checksum.get("value") or checksum.get("hash") or checksum.get("checksum"))
        checksum_type = _string_or_none(checksum.get("type") or checksum.get("algorithm") or checksum.get("algo"))
        return value, checksum_type
    value = _string_or_none(checksum or item.get("sha256") or item.get("sha1") or item.get("md5"))
    if item.get("sha256"):
        return value, "sha256"
    if item.get("sha1"):
        return value, "sha1"
    if item.get("md5"):
        return value, "md5"
    return value, _string_or_none(item.get("checksum_type") or item.get("checksum_algorithm"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
