from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument

from app.core.config import settings
from app.services.inpi_ingestion_service import _FtpConnector, InpiFileTarget, InpiIngestionService

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"starting", "listing", "downloading", "cancelling"}
VALID_CATEGORIES = {"comptes_annuels", "formalites"}
VALID_NIVEAUX = {"standard", "niveau1"}


class InpiSourceDownloadAlreadyRunning(Exception):
    pass


class InpiSourceDownloadCancelled(Exception):
    pass


@dataclass(frozen=True)
class InpiRemoteArchive:
    remote_path: str
    remote_size: int
    remote_mtime: datetime | None
    target: InpiFileTarget
    local_path: Path


class InpiSourceDownloadService:
    """Download INPI source ZIP archives to the local source mirror only."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.dataset_slug = settings.INPI_SOURCE_DOWNLOAD_DATASET_SLUG
        self.input_dir = Path(settings.INPI_LOCAL_DATA_DIR)
        self.input_dir.mkdir(parents=True, exist_ok=True)

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)

    async def list_remote(
        self,
        *,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        categories = _normalize_filter(categories, VALID_CATEGORIES, "category")
        niveaux = _normalize_filter(niveaux, VALID_NIVEAUX, "niveau")
        archives = await asyncio.to_thread(self._discover_remote_archives, categories, niveaux)
        files = []
        for archive in archives[:limit]:
            files.append(
                {
                    "remote_path": archive.remote_path,
                    "remote_size": archive.remote_size,
                    "remote_mtime": archive.remote_mtime,
                    "category": archive.target.category,
                    "niveau": archive.target.niveau,
                    "local_path": str(archive.local_path),
                    "downloaded": archive.local_path.exists(),
                }
            )
        return {
            "remote_base_dir": settings.INPI_REMOTE_BASE_DIR,
            "local_dir": str(self.input_dir),
            "count": len(archives),
            "returned": len(files),
            "files": files,
        }

    async def start(
        self,
        *,
        force_download: bool = False,
        max_files: int | None = None,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
    ) -> str:
        await self.ensure_indexes()
        run_id = str(uuid4())
        categories = _normalize_filter(categories, VALID_CATEGORIES, "category")
        niveaux = _normalize_filter(niveaux, VALID_NIVEAUX, "niveau")
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
                    "force_download_requested": force_download,
                    "max_files_requested": max_files,
                    "categories_requested": categories,
                    "niveaux_requested": niveaux,
                    "discovered": 0,
                    "downloaded": 0,
                    "skipped": 0,
                    "failed": 0,
                    "current_remote_path": None,
                    "current_local_path": None,
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
            raise InpiSourceDownloadAlreadyRunning(
                f"inpi source download already running with status={current.get('status', 'unknown')}"
            )
        return run_id

    async def run_started(
        self,
        run_id: str,
        *,
        force_download: bool = False,
        max_files: int | None = None,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
    ) -> None:
        categories = _normalize_filter(categories, VALID_CATEGORIES, "category")
        niveaux = _normalize_filter(niveaux, VALID_NIVEAUX, "niveau")
        stats: dict[str, Any] = {"discovered": 0, "downloaded": 0, "skipped": 0, "failed": 0, "failed_files": []}
        try:
            await self._update_state_owned(run_id, {"status": "listing", "updated_at": _utcnow()})
            archives = await asyncio.to_thread(self._discover_remote_archives, categories, niveaux)
            stats["discovered"] = len(archives)
            await self._update_state_owned(run_id, {**stats, "updated_at": _utcnow()})

            handled = 0
            for archive in archives:
                await self._check_cancel(run_id)
                if max_files is not None and handled >= max_files:
                    break
                handled += 1
                await self._download_archive(run_id, archive, stats, force_download=force_download)

            status = "done" if stats["failed"] == 0 else "done_with_failures"
            fields: dict[str, Any] = {
                "status": status,
                "current_remote_path": None,
                "current_local_path": None,
                "last_error": None if stats["failed"] == 0 else f"{stats['failed']} archive(s) failed",
                "updated_at": _utcnow(),
                **stats,
            }
            if stats["failed"] == 0:
                fields["last_successful_run"] = _utcnow()
            await self._update_state_owned(run_id, fields)
        except InpiSourceDownloadCancelled:
            await self._update_state_owned(
                run_id,
                {
                    "status": "cancelled",
                    "cancel_requested": False,
                    "current_remote_path": None,
                    "current_local_path": None,
                    "updated_at": _utcnow(),
                    **stats,
                },
            )
            raise
        except Exception as exc:
            await self._update_state_owned(
                run_id,
                {
                    "status": "error",
                    "last_error": str(exc),
                    "current_remote_path": None,
                    "current_local_path": None,
                    "updated_at": _utcnow(),
                    **stats,
                },
            )
            logger.exception("[inpi-source-download] run failed")
            raise
        finally:
            await self._release_run(run_id)

    async def run(
        self,
        *,
        force_download: bool = False,
        max_files: int | None = None,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
    ) -> None:
        run_id = await self.start(
            force_download=force_download,
            max_files=max_files,
            categories=categories,
            niveaux=niveaux,
        )
        await self.run_started(
            run_id,
            force_download=force_download,
            max_files=max_files,
            categories=categories,
            niveaux=niveaux,
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

    async def _download_archive(
        self,
        run_id: str,
        archive: InpiRemoteArchive,
        stats: dict[str, Any],
        *,
        force_download: bool,
    ) -> None:
        if archive.local_path.exists() and not force_download:
            stats["skipped"] += 1
            await self._update_state_owned(run_id, {**stats, "updated_at": _utcnow()})
            return

        await self._update_state_owned(
            run_id,
            {
                "status": "downloading",
                "current_remote_path": archive.remote_path,
                "current_local_path": str(archive.local_path),
                "download_total_bytes": archive.remote_size or None,
                "updated_at": _utcnow(),
            },
        )
        try:
            written = await asyncio.to_thread(self._download_one_sync, archive.remote_path, archive.local_path)
            if archive.remote_size and written != archive.remote_size:
                raise RuntimeError(f"size mismatch: remote={archive.remote_size} written={written}")
            stats["downloaded"] += 1
            await self._write_source_manifest(archive, written)
        except Exception as exc:
            logger.exception("[inpi-source-download] Failed to download %s", archive.remote_path)
            stats["failed"] += 1
            stats["failed_files"].append(archive.remote_path)
            await self._update_state_owned(
                run_id,
                {
                    **stats,
                    "last_error": str(exc),
                    "updated_at": _utcnow(),
                },
            )
            return
        await self._update_state_owned(run_id, {**stats, "last_error": None, "updated_at": _utcnow()})

    def _discover_remote_archives(
        self,
        categories: list[str] | None,
        niveaux: list[str] | None,
    ) -> list[InpiRemoteArchive]:
        with _FtpConnector() as conn:
            remote_files = list(conn.walk(settings.INPI_REMOTE_BASE_DIR or "/"))
        archives: list[InpiRemoteArchive] = []
        for remote_file in remote_files:
            target = InpiIngestionService._target_for_path(remote_file.path)
            if target is None:
                continue
            if categories and target.category not in categories:
                continue
            if niveaux and target.niveau not in niveaux:
                continue
            archives.append(
                InpiRemoteArchive(
                    remote_path=remote_file.path,
                    remote_size=int(remote_file.size or 0),
                    remote_mtime=remote_file.mtime,
                    target=target,
                    local_path=self._local_path_for(remote_file.path),
                )
            )
        return sorted(archives, key=lambda archive: archive.remote_path)

    def _download_one_sync(self, remote_path: str, local_path: Path) -> int:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = local_path.with_suffix(local_path.suffix + ".part")
        if tmp.exists():
            tmp.unlink()
        with _FtpConnector() as conn:
            written = conn.download(remote_path, tmp)
        if local_path.exists():
            local_path.unlink()
        os.replace(tmp, local_path)
        return written

    def _local_path_for(self, remote_path: str) -> Path:
        rel = PurePosixPath(remote_path.lstrip("/"))
        return self.input_dir / Path(*rel.parts)

    async def _write_source_manifest(self, archive: InpiRemoteArchive, written: int) -> None:
        manifest = {
            "source": "inpi_ftp_source_download",
            "remote_path": archive.remote_path,
            "remote_size": archive.remote_size,
            "remote_mtime": archive.remote_mtime.isoformat() if archive.remote_mtime else None,
            "local_path": str(archive.local_path),
            "local_size": written,
            "category": archive.target.category,
            "niveau": archive.target.niveau,
            "downloaded_at": _utcnow().isoformat(),
        }
        manifest_path = archive.local_path.with_suffix(archive.local_path.suffix + ".manifest.json")
        await asyncio.to_thread(
            manifest_path.write_text,
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
            "utf-8",
        )

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": self.dataset_slug})
        if doc is None:
            doc = {
                "dataset_slug": self.dataset_slug,
                "status": "idle",
                "run_id": None,
                "discovered": 0,
                "downloaded": 0,
                "skipped": 0,
                "failed": 0,
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
            raise InpiSourceDownloadAlreadyRunning("inpi source download ownership lost")

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {
                "$set": {"run_id": None, "updated_at": _utcnow()},
                "$unset": {
                    "max_files_requested": "",
                },
            },
        )

    async def _check_cancel(self, run_id: str) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return
        await self._update_state_owned(run_id, {"status": "cancelled", "cancel_requested": False})
        raise InpiSourceDownloadCancelled("inpi source download cancelled by user")


def _normalize_filter(values: list[str] | None, allowed: set[str], label: str) -> list[str] | None:
    if not values:
        return None
    normalized: list[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip().lower()
            if not item:
                continue
            if item not in allowed:
                raise ValueError(f"unsupported INPI {label}: {item}")
            normalized.append(item)
    return sorted(set(normalized)) or None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
