from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument

from app.core.config import settings
from app.services.inpi_ingestion_service import InpiFileTarget, InpiIngestionService
from app.tools.inpi_to_parquet import export_inpi_file_to_parquet

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"starting", "discovering", "exporting", "cancelling"}
VALID_CATEGORIES = {"comptes_annuels", "formalites"}
VALID_NIVEAUX = {"standard", "niveau1"}


class InpiParquetExportAlreadyRunning(Exception):
    pass


class InpiParquetExportCancelled(Exception):
    pass


@dataclass(frozen=True)
class InpiLocalArchive:
    input_path: Path
    target: InpiFileTarget
    output_dir: Path


class InpiParquetExportService:
    """Export local INPI RNE ZIP archives to raw Parquet in the data lake."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.dataset_slug = settings.INPI_PARQUET_EXPORT_DATASET_SLUG
        self.input_dir = Path(settings.INPI_LOCAL_DATA_DIR)
        self.output_base = Path(settings.DATA_LAKE_DIR) / "raw" / "inpi"
        self.progress_path = Path(settings.INPI_PARQUET_EXPORT_PROGRESS_FILE)
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)

    async def start(
        self,
        *,
        force_export: bool = False,
        max_files: int | None = None,
        max_records_per_file: int | None = None,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
        include_raw_json: bool = False,
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
                    "force_export_requested": force_export,
                    "max_files_requested": max_files,
                    "max_records_per_file_requested": max_records_per_file,
                    "categories_requested": categories,
                    "niveaux_requested": niveaux,
                    "include_raw_json_requested": include_raw_json,
                    "discovered": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                    "rows": 0,
                    "current_file": "",
                    "current_category": None,
                    "current_niveau": None,
                    "current_output_dir": None,
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
            raise InpiParquetExportAlreadyRunning(
                f"inpi parquet export already running with status={current.get('status', 'unknown')}"
            )
        await self._write_progress_from_state(state)
        return run_id

    async def run_started(
        self,
        run_id: str,
        *,
        force_export: bool = False,
        max_files: int | None = None,
        max_records_per_file: int | None = None,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
        include_raw_json: bool = False,
    ) -> None:
        categories = _normalize_filter(categories, VALID_CATEGORIES, "category")
        niveaux = _normalize_filter(niveaux, VALID_NIVEAUX, "niveau")
        stats: dict[str, Any] = {
            "discovered": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "rows": 0,
            "failed_files": [],
        }
        try:
            await self._update_state_owned(run_id, {"status": "discovering", "updated_at": _utcnow()})
            archives = await asyncio.to_thread(self._discover_archives, categories, niveaux)
            stats["discovered"] = len(archives)
            await self._update_state_owned(
                run_id,
                {
                    "discovered": len(archives),
                    "categories_requested": categories,
                    "niveaux_requested": niveaux,
                    "updated_at": _utcnow(),
                },
            )

            handled = 0
            for archive in archives:
                await self._check_cancel(run_id)
                if max_files is not None and handled >= max_files:
                    break
                handled += 1
                await self._handle_archive(
                    run_id,
                    archive,
                    stats,
                    force_export=force_export,
                    max_records_per_file=max_records_per_file,
                    include_raw_json=include_raw_json,
                )

            status = "done" if stats["failed"] == 0 else "done_with_failures"
            completion_fields: dict[str, Any] = {
                "status": status,
                "current_file": "",
                "current_category": None,
                "current_niveau": None,
                "current_output_dir": None,
                "last_error": None if stats["failed"] == 0 else f"{stats['failed']} archive(s) failed",
                "updated_at": _utcnow(),
                **stats,
            }
            if stats["failed"] == 0:
                completion_fields["last_successful_run"] = _utcnow()
            await self._update_state_owned(run_id, completion_fields)
        except InpiParquetExportCancelled:
            await self._update_state_owned(
                run_id,
                {
                    "status": "cancelled",
                    "cancel_requested": False,
                    "current_file": "",
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
                    "current_file": "",
                    "updated_at": _utcnow(),
                    **stats,
                },
            )
            logger.exception("[inpi-parquet-export] run failed")
            raise
        finally:
            await self._release_run(run_id)

    async def run(
        self,
        *,
        force_export: bool = False,
        max_files: int | None = None,
        max_records_per_file: int | None = None,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
        include_raw_json: bool = False,
    ) -> None:
        run_id = await self.start(
            force_export=force_export,
            max_files=max_files,
            max_records_per_file=max_records_per_file,
            categories=categories,
            niveaux=niveaux,
            include_raw_json=include_raw_json,
        )
        await self.run_started(
            run_id,
            force_export=force_export,
            max_files=max_files,
            max_records_per_file=max_records_per_file,
            categories=categories,
            niveaux=niveaux,
            include_raw_json=include_raw_json,
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

    async def list_local_files(
        self,
        *,
        categories: list[str] | None = None,
        niveaux: list[str] | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        categories = _normalize_filter(categories, VALID_CATEGORIES, "category")
        niveaux = _normalize_filter(niveaux, VALID_NIVEAUX, "niveau")
        archives = await asyncio.to_thread(self._discover_archives, categories, niveaux)
        items = []
        for archive in archives[:limit]:
            manifest = _read_manifest(archive.output_dir)
            items.append(
                {
                    "input_path": str(archive.input_path),
                    "name": archive.input_path.name,
                    "size_bytes": archive.input_path.stat().st_size,
                    "category": archive.target.category,
                    "niveau": archive.target.niveau,
                    "output_dir": str(archive.output_dir),
                    "exported": manifest is not None,
                    "manifest_rows": manifest.get("rows") if manifest else None,
                }
            )
        return {
            "input_dir": str(self.input_dir),
            "count": len(archives),
            "returned": len(items),
            "files": items,
        }

    async def _handle_archive(
        self,
        run_id: str,
        archive: InpiLocalArchive,
        stats: dict[str, Any],
        *,
        force_export: bool,
        max_records_per_file: int | None,
        include_raw_json: bool,
    ) -> None:
        manifest = _read_manifest(archive.output_dir)
        if manifest is not None and not force_export:
            stats["skipped"] += 1
            stats["rows"] += int(manifest.get("rows") or 0)
            await self._update_state_owned(run_id, {**stats, "updated_at": _utcnow()})
            return

        await self._update_state_owned(
            run_id,
            {
                "status": "exporting",
                "current_file": str(archive.input_path),
                "current_category": archive.target.category,
                "current_niveau": archive.target.niveau,
                "current_output_dir": str(archive.output_dir),
                "updated_at": _utcnow(),
            },
        )

        try:
            _prepare_output_dir(archive.output_dir, self.output_base, force_export)
            rows = await asyncio.to_thread(
                export_inpi_file_to_parquet,
                input_path=archive.input_path,
                output_dir=archive.output_dir,
                target=archive.target,
                batch_size=settings.INPI_PARQUET_EXPORT_BATCH_SIZE,
                max_records=max_records_per_file,
                include_raw_json=include_raw_json,
            )
            stats["processed"] += 1
            stats["rows"] += rows
        except Exception as exc:
            stats["failed"] += 1
            stats["failed_files"].append(str(archive.input_path))
            logger.exception("[inpi-parquet-export] failed input=%s", archive.input_path)
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

    def _discover_archives(
        self,
        categories: list[str] | None,
        niveaux: list[str] | None,
    ) -> list[InpiLocalArchive]:
        if not self.input_dir.exists():
            return []
        archives: list[InpiLocalArchive] = []
        for input_path in sorted(self.input_dir.rglob("*.zip")):
            target = InpiIngestionService._target_for_path(str(input_path))
            if target is None:
                continue
            if categories and target.category not in categories:
                continue
            if niveaux and target.niveau not in niveaux:
                continue
            output_dir = self.output_base / target.category / target.niveau / input_path.stem
            archives.append(InpiLocalArchive(input_path=input_path, target=target, output_dir=output_dir))
        return archives

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": self.dataset_slug})
        if doc is None:
            doc = {
                "dataset_slug": self.dataset_slug,
                "status": "idle",
                "run_id": None,
                "rows": 0,
                "discovered": 0,
                "processed": 0,
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
        state = await self._get_state()
        await self._write_progress_from_state(state)

    async def _update_state_owned(self, run_id: str, fields: dict[str, Any]) -> None:
        result = await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {"$set": fields},
        )
        if result.matched_count == 0:
            raise InpiParquetExportAlreadyRunning("inpi parquet export ownership lost")
        state = await self._get_state()
        await self._write_progress_from_state(state)

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {
                "$set": {"run_id": None, "updated_at": _utcnow()},
                "$unset": {
                    "max_files_requested": "",
                    "max_records_per_file_requested": "",
                    "include_raw_json_requested": "",
                },
            },
        )
        state = await self._get_state()
        await self._write_progress_from_state(state)

    async def _check_cancel(self, run_id: str) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return
        await self._update_state_owned(run_id, {"status": "cancelled", "cancel_requested": False})
        raise InpiParquetExportCancelled("inpi parquet export cancelled by user")

    async def _write_progress_from_state(self, state: dict[str, Any]) -> None:
        payload = dict(state)
        payload.pop("_id", None)
        tmp = self.progress_path.with_suffix(self.progress_path.suffix + ".tmp")
        await asyncio.to_thread(
            tmp.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "utf-8",
        )
        await asyncio.to_thread(tmp.replace, self.progress_path)


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


def _read_manifest(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _prepare_output_dir(path: Path, root: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise FileExistsError(f"INPI export output already exists without a manifest: {path}")
        resolved = path.resolve()
        root_resolved = root.resolve()
        if root_resolved not in resolved.parents and resolved != root_resolved:
            raise RuntimeError(f"refusing to delete output outside INPI data-lake root: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
