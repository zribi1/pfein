from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urljoin, urlparse
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, MongoClient, ReturnDocument, UpdateOne
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure

from app.core.config import settings
from app.services.bodacc_xml_parser import parse_bodacc_xml_content
from app.services.rejected_record_writer import SyncRejectedRecordWriter

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"starting", "listing", "downloading", "processing", "cancelling"}
ARCHIVE_EXTENSIONS = (".tar", ".tar.gz", ".taz")
BODACC_FILENAME_YEAR_RE = re.compile(r"(?:B[IX][ABC]|BODACC)[_-]?((?:19|20)[0-9]{2})[0-9]{3}", re.IGNORECASE)
YEAR_RE = re.compile(r"(?:19|20)[0-9]{2}")


class BodaccInitAlreadyRunning(Exception):
    pass


class BodaccInitCancelled(Exception):
    pass


@dataclass(frozen=True)
class BodaccArchive:
    url: str
    year: int
    mode: str


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


class BodaccInitIngestionService:
    def __init__(self, db: AsyncIOMotorDatabase, mode: Literal["init", "current"] = "init") -> None:
        if mode not in ("init", "current"):
            raise ValueError(f"unsupported BODACC ingestion mode: {mode}")
        self.mode = mode
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.files_coll = db[self._files_collection_name()]
        self.imports_coll = db[settings.BODACC_IMPORTS_COLLECTION]
        self.records_coll = db[settings.BODACC_ANNONCES_COLLECTION]
        self.data_dir = Path(self._data_dir())
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_slug = self._dataset_slug()

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)
        await self.files_coll.create_index([("url", ASCENDING)], unique=True)
        await self.files_coll.create_index([("status", ASCENDING)])
        await self.files_coll.create_index([("year", ASCENDING)])
        await self.files_coll.create_index([("fully_processed", ASCENDING)])
        await self.files_coll.create_index([("processed_at", ASCENDING)])
        try:
            await self.imports_coll.create_index([("filename", ASCENDING), ("filePath", ASCENDING)])
            await self.imports_coll.create_index([("recordKey", ASCENDING)], unique=True, sparse=True)
            await self.imports_coll.create_index([("status", ASCENDING)])
            await self.records_coll.create_index([("siren", ASCENDING)])
            await self.records_coll.create_index([("eventDate", ASCENDING)])
            await self.records_coll.create_index(
                [("nojo", ASCENDING)],
                unique=True,
                partialFilterExpression={"nojo": {"$type": "string"}},
            )
            await self.records_coll.create_index([("flags.liquidation", ASCENDING)])
            await self.records_coll.create_index([("flags.redressement", ASCENDING)])
            await self.records_coll.create_index([("flags.procedureCollective", ASCENDING)])
            await self.records_coll.create_index([("personneType", ASCENDING)])
            await self.records_coll.create_index([("bodaccFamily", ASCENDING)])
            await self.records_coll.create_index([("eventCategory", ASCENDING)])
            await self.records_coll.create_index([("isRiskEvent", ASCENDING)])
            await self.records_coll.create_index([("archiveMemberName", ASCENDING)])
            # Rejected records indexes
            rejected_coll = self.db[settings.REJECTED_RECORDS_COLLECTION]
            await rejected_coll.create_index([("source", ASCENDING), ("rejected_at", ASCENDING)])
            await rejected_coll.create_index([("reason", ASCENDING)])
            await rejected_coll.create_index([("pipeline", ASCENDING)])
            await rejected_coll.create_index([("siren_attempt", ASCENDING)], sparse=True)
        except OperationFailure as exc:
            if exc.code != 86:
                raise

    async def run_init(
        self,
        force: bool = False,
        max_files: int | None = None,
        filename_contains: str | None = None,
    ) -> None:
        await self._run(force=force, max_files=max_files, filename_contains=filename_contains)

    async def run_current(
        self,
        force: bool = False,
        max_files: int | None = None,
        filename_contains: str | None = None,
    ) -> None:
        await self._run(force=force, max_files=max_files, filename_contains=filename_contains)

    async def _run(
        self,
        force: bool = False,
        max_files: int | None = None,
        filename_contains: str | None = None,
    ) -> None:
        await self.ensure_indexes()
        run_id = str(uuid4())
        filename_contains = filename_contains.strip() if filename_contains else None
        await self._acquire_run(run_id, force, max_files, filename_contains)
        processed = 0
        rows_total = 0
        try:
            await self._update_state_owned(run_id, {"status": "listing", "last_check_at": _utcnow()})
            archives = await self._discover_archives()
            await self._update_state_owned(
                run_id,
                {
                    "remote_files_total": len(archives),
                    "last_check_at": _utcnow(),
                },
            )
            to_process = await self._reconcile_archives(archives, force)
            if filename_contains:
                needle = filename_contains.lower()
                to_process = [
                    archive
                    for archive in to_process
                    if needle in Path(urlparse(archive.url).path).name.lower()
                ]
            limit = int(max_files or self._max_files_per_run() or 0)
            logger.info(
                "[bodacc-%s] processing queue: discovered=%d to_process=%d force=%s limit=%s",
                self.mode,
                len(archives),
                len(to_process),
                force,
                limit or "unlimited",
            )
            if to_process:
                logger.info(
                    "[bodacc-%s] first pending archive: %s",
                    self.mode,
                    to_process[0].url,
                )

            queue = asyncio.Queue(maxsize=3)
            producer_task = asyncio.create_task(self._producer(run_id, to_process, queue, limit, force))
            consumer_task = asyncio.create_task(self._consumer(run_id, queue, force))
            
            try:
                results = await asyncio.gather(producer_task, consumer_task)
                processed, rows_total = results[1]
            except BaseException:
                producer_task.cancel()
                consumer_task.cancel()
                raise
            remaining = max(0, len(to_process) - processed)
            next_urls = [item.url for item in to_process[processed:processed + 5]]
            logger.info(
                "[bodacc-%s] run summary: processed=%d/%d archives, records=%d, remaining_pending=%d%s",
                self.mode,
                processed,
                len(to_process),
                rows_total,
                remaining,
                f", next={next_urls}" if next_urls else "",
            )

            await self._update_state_owned(
                run_id,
                {
                    "status": "idle",
                    "files_processed_last_run": processed,
                    "rows_ingested_last_run": rows_total,
                    "last_successful_run": _utcnow(),
                    "last_check_at": _utcnow(),
                    "last_error": None,
                },
            )
        except BodaccInitCancelled:
            raise
        except Exception as exc:
            await self._update_state_owned(
                run_id,
                {"status": "error", "last_error": str(exc), "last_check_at": _utcnow()},
            )
            logger.exception("[bodacc-%s] run failed", self.mode)
            raise
        finally:
            await self._release_run(run_id)

    async def get_status(self) -> dict[str, Any]:
        state = await self._get_state()
        state.pop("_id", None)
        state["files_by_status"] = await self._counts_by_status()
        return state

    async def list_files(
        self,
        *,
        status: str | None = None,
        contains: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if contains:
            query["url"] = {"$regex": contains, "$options": "i"}
        cursor = self.files_coll.find(query, {"_id": 0}).sort("url", ASCENDING).limit(limit)
        return [doc async for doc in cursor]

    async def request_cancel(self) -> dict[str, Any]:
        state = await self._get_state()
        if state.get("status") not in ACTIVE_STATUSES:
            return {"accepted": False, "status": state.get("status", "idle")}
        await self._update_state({"cancel_requested": True, "status": "cancelling"})
        return {"accepted": True, "status": "cancelling"}

    async def _discover_archives(self) -> list[BodaccArchive]:
        base_url = _ensure_trailing_slash(self._base_url())
        seen_dirs: set[str] = set()
        found: dict[str, BodaccArchive] = {}

        timeout = httpx.Timeout(
            float(settings.BODACC_HTTP_TIMEOUT_SECONDS),
            connect=30.0,
        )
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async def walk(url: str) -> None:
                normalized_url = _ensure_trailing_slash(url)
                if normalized_url in seen_dirs:
                    return
                seen_dirs.add(normalized_url)
                html = await self._get_directory_html(client, normalized_url)

                parser = _HrefParser()
                parser.feed(html)
                for href in parser.hrefs:
                    if href.startswith(("#", "?", "mailto:")):
                        continue
                    child = urljoin(normalized_url, href)
                    if not _is_under_base(base_url, child):
                        continue
                    child_path = unquote(urlparse(child).path)
                    name = Path(child_path.rstrip("/")).name
                    if name in ("", ".", ".."):
                        continue
                    if child.endswith("/"):
                        await walk(child)
                        continue
                    if not _is_archive_name(name):
                        continue
                    year = _year_from_url(child)
                    if year is None:
                        logger.warning("[bodacc-%s] skipping archive without year: %s", self.mode, child)
                        continue
                    found[child] = BodaccArchive(url=child, year=year, mode=self.mode)

            await walk(base_url)

        archives = sorted(found.values(), key=lambda item: item.url)
        logger.info("[bodacc-%s] discovered %d archives", self.mode, len(archives))
        return archives

    async def _get_directory_html(self, client: httpx.AsyncClient, url: str) -> str:
        max_attempts = max(1, int(settings.API_RETRY_MAX_ATTEMPTS))
        base_delay = float(settings.API_RETRY_BASE_DELAY_SECONDS)
        max_delay = float(settings.API_RETRY_MAX_DELAY_SECONDS)
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info("[bodacc-%s] listing %s", self.mode, url)
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt >= max_attempts:
                    logger.error(
                        "[bodacc-%s] failed listing %s after %d attempts: %s",
                        self.mode,
                        url,
                        attempt,
                        exc,
                    )
                    raise
                delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                logger.warning(
                    "[bodacc-%s] listing %s failed attempt %d/%d; retrying in %.1fs: %s",
                    self.mode,
                    url,
                    attempt,
                    max_attempts,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        raise RuntimeError(f"failed listing {url}")

    async def _reconcile_archives(
        self, archives: list[BodaccArchive], force: bool
    ) -> list[BodaccArchive]:
        to_process: list[BodaccArchive] = []
        for archive in archives:
            existing = await self.files_coll.find_one({"url": archive.url})
            if existing is None:
                await self.files_coll.insert_one(
                    {
                        "url": archive.url,
                        "year": archive.year,
                        "mode": self.mode,
                        "status": "pending",
                        "fully_processed": False,
                        "attempts": 0,
                        "discovered_at": _utcnow(),
                        "local_path": str(self._local_path_for(archive.url)),
                    }
                )
                to_process.append(archive)
                continue
            if (
                not force
                and (existing.get("status") == "done" or existing.get("fully_processed") is True)
            ):
                continue
            recovered_from = existing.get("status")
            await self.files_coll.update_one(
                {"url": archive.url},
                {
                    "$set": {
                        "year": archive.year,
                        "mode": self.mode,
                        "status": "pending",
                        "fully_processed": False,
                        "recovered_from_status": recovered_from,
                        "local_path": str(self._local_path_for(archive.url)),
                        "last_error": None,
                    }
                },
            )
            to_process.append(archive)
        return to_process

    async def _producer(self, run_id: str, to_process: list[BodaccArchive], queue: asyncio.Queue, limit: int, force: bool) -> None:
        produced = 0
        for archive in to_process:
            await self._check_cancel(run_id)
            if limit and produced >= limit:
                logger.info(
                    "[bodacc-%s] reached max files per run=%d in downloader, stopping with %d archive(s) still pending",
                    self.mode,
                    limit,
                    len(to_process) - produced,
                )
                break
            
            local_path = self._local_path_for(archive.url)
            local_archive_ready = _is_ready_archive_file(local_path)
            initial_status = "processing" if local_archive_ready else "downloading"
            
            await self._update_state_owned(
                run_id,
                {
                    "status": initial_status,
                    "current_remote_path": archive.url,
                    "current_local_path": str(local_path),
                    "current_year": archive.year,
                    "current_archive_size_bytes": local_path.stat().st_size if local_archive_ready else None,
                    "downloaded_bytes": 0,
                    "download_total_bytes": None,
                    "download_progress_percent": None,
                    "download_status": "reused_local_file" if local_archive_ready else "downloading",
                    "last_check_at": _utcnow(),
                },
            )
            await self.files_coll.update_one(
                {"url": archive.url},
                {
                    "$set": {
                        "status": initial_status,
                        "mode": self.mode,
                        "local_path": str(local_path),
                        "local_size": local_path.stat().st_size if local_archive_ready else None,
                        "download_status": "reused_local_file" if local_archive_ready else "downloading",
                        "last_error": None,
                        "processing_started_at": _utcnow() if local_archive_ready else None,
                    },
                    "$inc": {"attempts": 1},
                },
            )

            try:
                if local_archive_ready:
                    logger.info(
                        "[bodacc-%s] reusing downloaded archive path=%s size=%d force=%s",
                        self.mode,
                        local_path,
                        local_path.stat().st_size,
                        force,
                    )
                else:
                    await self._download_archive(run_id, archive.url, local_path)
                    await self.files_coll.update_one(
                        {"url": archive.url},
                        {
                            "$set": {
                                "status": "downloaded",
                                "download_status": "downloaded",
                                "downloaded_at": _utcnow(),
                                "downloaded_bytes": local_path.stat().st_size if local_path.exists() else None,
                                "local_size": local_path.stat().st_size if local_path.exists() else None,
                            }
                        },
                    )
            except Exception as exc:
                await self.files_coll.update_one(
                    {"url": archive.url},
                    {
                        "$set": {
                            "status": "failed",
                            "last_error": str(exc),
                            "failed_at": _utcnow(),
                        }
                    },
                )
                raise
                
            await queue.put(archive)
            produced += 1
        
        await queue.put(None)

    async def _consumer(self, run_id: str, queue: asyncio.Queue, force: bool) -> tuple[int, int]:
        rows_total = 0
        processed = 0
        while True:
            archive = await queue.get()
            if archive is None:
                queue.task_done()
                break
            
            try:
                await self._check_cancel(run_id)
                local_path = self._local_path_for(archive.url)
                
                await self._update_state_owned(
                    run_id,
                    {
                        "status": "processing",
                        "last_check_at": _utcnow(),
                    },
                )
                await self.files_coll.update_one(
                    {"url": archive.url},
                    {"$set": {"status": "processing", "processing_started_at": _utcnow()}},
                )
                
                rows = await asyncio.to_thread(self._process_archive_sync, local_path, archive, force)
                
                await self.files_coll.update_one(
                    {"url": archive.url},
                    {
                        "$set": {
                            "status": "done",
                            "rows_ingested": rows,
                            "processed_at": _utcnow(),
                            "fully_processed": True,
                            "last_error": None,
                        }
                    },
                )
                logger.info(
                    "[bodacc-%s] archive done url=%s year=%d records=%d",
                    self.mode,
                    archive.url,
                    archive.year,
                    rows,
                )
                if self._delete_after_ingest():
                    local_path.unlink(missing_ok=True)
                
                rows_total += rows
                processed += 1
            except Exception as exc:
                await self.files_coll.update_one(
                    {"url": archive.url},
                    {
                        "$set": {
                            "status": "failed",
                            "last_error": str(exc),
                            "failed_at": _utcnow(),
                        }
                    },
                )
                raise
            finally:
                queue.task_done()
        return processed, rows_total

    async def _download_archive(self, run_id: str, url: str, local_path: Path) -> None:
        tmp = local_path.with_suffix(local_path.suffix + ".part")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0
        last_logged = 0
        log_step = 50 * 1024 * 1024
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total_bytes = _download_total_bytes(response)
                await self._update_download_progress(run_id, bytes_written, total_bytes)
                with tmp.open("wb") as fh:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        await self._check_cancel(run_id)
                        if not chunk:
                            continue
                        fh.write(chunk)
                        bytes_written += len(chunk)
                        await self._update_download_progress(run_id, bytes_written, total_bytes)
                        if bytes_written - last_logged >= log_step:
                            logger.info(
                                "[bodacc-%s] download progress %s: %s",
                                self.mode,
                                url,
                                _format_download_progress(bytes_written, total_bytes),
                            )
                            last_logged = bytes_written
        if local_path.exists():
            local_path.unlink()
        os.replace(tmp, local_path)
        await self._update_download_progress(run_id, bytes_written, total_bytes)
        logger.info(
            "[bodacc-%s] download complete %s: %s",
            self.mode,
            url,
            _format_download_progress(bytes_written, total_bytes),
        )

    async def _update_download_progress(
        self,
        run_id: str,
        bytes_written: int,
        total_bytes: int | None,
    ) -> None:
        fields: dict[str, Any] = {
            "downloaded_bytes": bytes_written,
            "download_total_bytes": total_bytes,
            "download_progress_percent": _progress_percent(bytes_written, total_bytes),
            "last_check_at": _utcnow(),
        }
        await self._update_state_owned(run_id, fields)

    def _process_archive_sync(self, local_path: Path, archive: BodaccArchive, force: bool = False) -> int:
        sync_client = MongoClient(settings.MONGO_URI)
        try:
            db = sync_client[settings.MONGO_DB]
            imports_coll = db[settings.BODACC_IMPORTS_COLLECTION]
            annonces_coll = db[settings.BODACC_ANNONCES_COLLECTION]
            rejected = SyncRejectedRecordWriter(db[settings.REJECTED_RECORDS_COLLECTION])
            stats = _empty_archive_stats()
            with tarfile.open(local_path, mode="r:*") as tf:
                for member in tf:
                    if not member.isfile():
                        continue
                    stats["members"] += 1
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    content = extracted.read()
                    _merge_archive_stats(
                        stats,
                        _ingest_archive_member_clean(
                            imports_coll,
                            annonces_coll,
                            content,
                            archive,
                            member.name,
                            str(local_path),
                            force=force,
                            rejected=rejected,
                        ),
                    )
            rejected.flush()
            logger.info(
                "[bodacc-%s] archive parsed members=%d annonces=%d inserted=%d skipped=%d parse_errors=%d member_errors=%d url=%s",
                archive.mode,
                stats["members"],
                stats["annonces"],
                stats["inserted"],
                stats["skipped"],
                stats["parseErrors"],
                stats["memberErrors"],
                archive.url,
            )
            return stats["inserted"]
        finally:
            sync_client.close()

    def _local_path_for(self, url: str) -> Path:
        parsed = urlparse(url)
        rel = unquote(parsed.path).lstrip("/")
        return self.data_dir / rel

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": self.dataset_slug})
        if doc is None:
            doc = {"dataset_slug": self.dataset_slug, "status": "idle", "run_id": None}
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
            upsert=False,
        )
        if result.matched_count == 0:
            raise BodaccInitAlreadyRunning("bodacc init ownership lost")

    async def _acquire_run(
        self,
        run_id: str,
        force: bool,
        max_files: int | None,
        filename_contains: str | None,
    ) -> dict[str, Any]:
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
                    "force_requested": force,
                    "max_files_requested": max_files,
                    "filename_contains_requested": filename_contains,
                    "last_error": None,
                    "last_started_at": _utcnow(),
                    "last_check_at": _utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if state is None:
            current = await self._get_state()
            raise BodaccInitAlreadyRunning(
                f"bodacc {self.mode} already running with status={current.get('status', 'unknown')}"
            )
        return state

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {
                "$set": {"run_id": None},
                "$unset": {
                    "force_requested": "",
                    "max_files_requested": "",
                    "filename_contains_requested": "",
                },
            },
        )

    async def _check_cancel(self, run_id: str) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return
        await self._update_state_owned(run_id, {"cancel_requested": False, "status": "cancelled"})
        raise BodaccInitCancelled(f"bodacc {self.mode} cancelled by user")

    async def _counts_by_status(self) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        out: dict[str, int] = {}
        async for doc in self.files_coll.aggregate(pipeline):
            out[str(doc["_id"])] = int(doc["n"])
        return out

    def _base_url(self) -> str:
        if self.mode == "current":
            return settings.BODACC_CURRENT_BASE_URL
        return settings.BODACC_INIT_BASE_URL

    def _data_dir(self) -> str:
        if self.mode == "current":
            return settings.BODACC_CURRENT_DATA_DIR
        return settings.BODACC_INIT_DATA_DIR

    def _files_collection_name(self) -> str:
        if self.mode == "current":
            return settings.BODACC_CURRENT_FILES_COLLECTION
        return settings.BODACC_INIT_FILES_COLLECTION

    def _dataset_slug(self) -> str:
        if self.mode == "current":
            return settings.BODACC_CURRENT_DATASET_SLUG
        return settings.BODACC_INIT_DATASET_SLUG

    def _max_files_per_run(self) -> int:
        if self.mode == "current":
            return settings.BODACC_CURRENT_MAX_FILES_PER_RUN
        return settings.BODACC_INIT_MAX_FILES_PER_RUN

    def _delete_after_ingest(self) -> bool:
        if self.mode == "current":
            return settings.BODACC_CURRENT_DELETE_AFTER_INGEST
        return settings.BODACC_INIT_DELETE_AFTER_INGEST


def _ingest_archive_member_clean(
    imports_coll: Any,
    annonces_coll: Any,
    content: bytes,
    archive: BodaccArchive,
    member_name: str,
    local_archive_path: str,
    *,
    force: bool = False,
    rejected: SyncRejectedRecordWriter | None = None,
) -> dict[str, int]:
    sample_path = _save_expected_xml_sample(content, archive, member_name)
    record_key = hashlib.sha256(
        archive.url.encode("utf-8") + b"\0" + member_name.encode("utf-8") + b"\0" + content
    ).hexdigest()
    now = _utcnow()
    file_path = f"{local_archive_path}:{member_name}"
    existing_import = imports_coll.find_one(
        {"recordKey": record_key},
        {"_id": 1, "status": 1, "annoncesCount": 1, "insertedCount": 1, "skippedCount": 1},
    )
    if existing_import and existing_import.get("status") == "success" and not force:
        annonces_count = int(existing_import.get("annoncesCount") or 0)
        inserted_count = int(existing_import.get("insertedCount") or 0)
        skipped_count = int(existing_import.get("skippedCount") or 0)
        logger.info(
            "[bodacc-%s] skipping already imported member=%s annonces=%d inserted=%d skipped=%d",
            archive.mode,
            member_name,
            annonces_count,
            inserted_count,
            skipped_count,
        )
        return {
            "members": 0,
            "annonces": annonces_count,
            "inserted": 0,
            "skipped": annonces_count or inserted_count + skipped_count,
            "parseErrors": 0,
            "memberErrors": 0,
        }

    imports_coll.update_one(
        {"recordKey": record_key},
        {
            "$setOnInsert": {
                "recordKey": record_key,
                "filename": Path(member_name).name,
                "filePath": file_path,
                "sourceUrl": archive.url,
                "archiveName": Path(urlparse(archive.url).path).name,
                "archiveMemberName": member_name,
                "bodaccMode": archive.mode,
                "year": archive.year,
                "importedAt": now,
                "debugSampleXmlPath": sample_path,
            },
            "$set": {
                "status": "pending",
                "errorMessage": None,
            },
        },
        upsert=True,
    )
    import_doc = imports_coll.find_one({"recordKey": record_key}, {"_id": 1})
    if import_doc is None:
        raise RuntimeError(f"failed to create BODACC import record for {member_name}")
    import_id = import_doc["_id"]

    try:
        parsed = parse_bodacc_xml_content(content)
    except Exception as exc:
        debug_path = _save_bad_xml_debug_copy(
            content,
            archive,
            member_name,
            reason="parse_error",
        )
        imports_coll.update_one(
            {"_id": import_id},
            {
                "$set": {
                    "status": "failed",
                    "errorMessage": str(exc),
                    "debugXmlPath": debug_path,
                    "annoncesCount": 0,
                    "insertedCount": 0,
                    "skippedCount": 0,
                }
            },
        )
        logger.warning("[bodacc-%s] failed parsing %s: %s", archive.mode, member_name, exc)
        if rejected is not None:
            rejected.write(
                source="bodacc",
                pipeline=f"bodacc_{archive.mode}",
                reason="parse_error",
                error_detail=str(exc),
                raw_snippet=content,
                file_path=f"{local_archive_path}:{member_name}",
            )
        return {
            "members": 0,
            "annonces": 0,
            "inserted": 0,
            "skipped": 0,
            "parseErrors": 1,
            "memberErrors": 0,
        }

    inserted, skipped, insert_errors = _insert_annonces_idempotent(
        annonces_coll,
        parsed.annonces,
        import_id=import_id,
        archive=archive,
        member_name=member_name,
        rejected=rejected,
    )
    errors = list(parsed.errors)
    errors.extend(insert_errors)
    debug_path = None

    if len(parsed.annonces) == 0:
        debug_path = _save_bad_xml_debug_copy(
            content,
            archive,
            member_name,
            reason="no_usable_annonces",
        )

    imports_coll.update_one(
        {"_id": import_id},
        {
            "$set": {
                "parution": parsed.parution,
                "dateParution": parsed.date_parution,
                "status": "success",
                "annoncesCount": len(parsed.annonces),
                "insertedCount": inserted,
                "skippedCount": skipped,
                "errorMessage": "; ".join(errors[:20]) if errors else None,
                "debugXmlPath": debug_path,
            }
        },
    )
    return {
        "members": 0,
        "annonces": len(parsed.annonces),
        "inserted": inserted,
        "skipped": skipped,
        "parseErrors": 0,
        "memberErrors": len(errors),
    }


def _insert_annonces_idempotent(
    annonces_coll: Any,
    annonces: list[dict[str, Any]],
    *,
    import_id: Any,
    archive: BodaccArchive,
    member_name: str,
    batch_size: int = 1000,
    rejected: SyncRejectedRecordWriter | None = None,
) -> tuple[int, int, list[str]]:
    inserted = 0
    skipped = 0
    errors: list[str] = []
    operations: list[UpdateOne] = []
    seen_nojos: set[str] = set()

    def flush() -> None:
        nonlocal inserted, skipped, operations
        if not operations:
            return
        try:
            result = annonces_coll.bulk_write(operations, ordered=False)
            inserted += int(result.upserted_count or 0)
            skipped += max(0, len(operations) - int(result.upserted_count or 0))
        except BulkWriteError as exc:
            details = exc.details or {}
            write_errors = details.get("writeErrors") or []
            duplicate_errors = [item for item in write_errors if item.get("code") == 11000]
            non_duplicate_errors = [item for item in write_errors if item.get("code") != 11000]
            inserted += int(details.get("nUpserted") or 0)
            skipped += len(duplicate_errors)
            skipped += max(0, len(operations) - int(details.get("nUpserted") or 0) - len(write_errors))
            for item in non_duplicate_errors[:20]:
                errors.append(f"bulk insert error index={item.get('index')}: {item.get('errmsg')}")
            if non_duplicate_errors:
                skipped += len(non_duplicate_errors)
        finally:
            operations = []

    for index, original in enumerate(annonces, start=1):
        annonce = dict(original)
        nojo = annonce.get("nojo")
        annonce["importId"] = import_id
        annonce["sourceUrl"] = archive.url
        annonce["archiveMemberName"] = member_name
        annonce["updatedAt"] = _utcnow()

        if nojo:
            nojo = str(nojo)
            if nojo in seen_nojos:
                skipped += 1
                continue
            seen_nojos.add(nojo)
            operations.append(
                UpdateOne(
                    {"nojo": nojo},
                    {"$setOnInsert": annonce},
                    upsert=True,
                )
            )
            if len(operations) >= batch_size:
                flush()
            continue

        # Rare edge case: no official nojo, so keep the previous conservative
        # insert path. The partial nojo unique index intentionally does not
        # enforce uniqueness for these documents.
        try:
            annonces_coll.insert_one(annonce)
            inserted += 1
        except DuplicateKeyError:
            skipped += 1
        except Exception as exc:
            skipped += 1
            errors.append(f"insert annonce #{index}: {exc}")
            if rejected is not None:
                rejected.write(
                    source="bodacc",
                    pipeline=f"bodacc_{archive.mode}",
                    reason="insert_error",
                    error_detail=str(exc),
                    raw_snippet=annonce,
                    file_path=f"{archive.url}:{member_name}",
                    extra={"siren": annonce.get("siren")},
                )

    flush()
    return inserted, skipped, errors


def _empty_archive_stats() -> dict[str, int]:
    return {
        "members": 0,
        "annonces": 0,
        "inserted": 0,
        "skipped": 0,
        "parseErrors": 0,
        "memberErrors": 0,
    }


def _merge_archive_stats(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def _save_bad_xml_debug_copy(
    content: bytes,
    archive: BodaccArchive,
    member_name: str,
    reason: str,
) -> str | None:
    if not settings.BODACC_DEBUG_BAD_XML_ENABLED:
        return None
    try:
        safe_member_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(member_name).name)
        archive_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(urlparse(archive.url).path).name)
        target_dir = Path(settings.BODACC_DEBUG_BAD_XML_DIR) / archive.mode / reason
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{archive_stem}__{safe_member_name}"
        with target_path.open("wb") as fh:
            fh.write(content)
        logger.info(
            "[bodacc-%s] saved debug XML reason=%s path=%s",
            archive.mode,
            reason,
            target_path,
        )
        return str(target_path)
    except Exception as exc:
        logger.warning(
            "[bodacc-%s] failed saving debug XML member=%s reason=%s: %s",
            archive.mode,
            member_name,
            reason,
            exc,
        )
        return None


def _save_expected_xml_sample(
    content: bytes,
    archive: BodaccArchive,
    member_name: str,
) -> str | None:
    if not settings.BODACC_DEBUG_SAMPLE_XML_ENABLED:
        return None

    family = _bodacc_family_from_names(archive.url, member_name)
    if family == "UNKNOWN":
        return None

    try:
        max_per_family = max(0, int(settings.BODACC_DEBUG_SAMPLE_XML_MAX_PER_FAMILY))
        target_dir = Path(settings.BODACC_DEBUG_SAMPLE_XML_DIR) / archive.mode / family
        target_dir.mkdir(parents=True, exist_ok=True)
        existing = [path for path in target_dir.iterdir() if path.is_file()]
        if max_per_family and len(existing) >= max_per_family:
            return None

        safe_member_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(member_name).name)
        archive_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(urlparse(archive.url).path).name)
        target_path = target_dir / f"{archive_stem}__{safe_member_name}"
        if target_path.exists():
            return str(target_path)

        with target_path.open("wb") as fh:
            fh.write(content)
        logger.info(
            "[bodacc-%s] saved sample XML family=%s path=%s",
            archive.mode,
            family,
            target_path,
        )
        return str(target_path)
    except Exception as exc:
        logger.warning(
            "[bodacc-%s] failed saving sample XML member=%s: %s",
            archive.mode,
            member_name,
            exc,
        )
        return None


def _bodacc_family_from_names(archive_url: str, member_name: str) -> str:
    value = f"{Path(urlparse(archive_url).path).name} {Path(member_name).name}".upper()
    if "PCL_BXA" in value:
        return "PCL"
    if "BILAN_BXC" in value:
        return "BILAN"
    if "RCS-A_BXA" in value or "RCSA_BXA" in value:
        return "RCS_A"
    if "RCS-B_BXB" in value or "RCSB_BXB" in value:
        return "RCS_B"
    return "UNKNOWN"


def _is_archive_name(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(ARCHIVE_EXTENSIONS)


def _is_ready_archive_file(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        try:
            with tarfile.open(path, mode="r:*"):
                return True
        except tarfile.TarError:
            logger.warning("[bodacc] local archive exists but is not readable, will redownload: %s", path)
            return False
    except OSError:
        return False


def _content_length(response: httpx.Response) -> int | None:
    value = response.headers.get("content-length")
    if value is None or not value.isdigit():
        return None
    return int(value)


def _download_total_bytes(response: httpx.Response) -> int | None:
    # httpx may transparently decompress responses, so compressed content-length
    # can be smaller than the bytes written to disk. In that case a percentage is
    # misleading; keep the raw byte counter but omit the total.
    encoding = (response.headers.get("content-encoding") or "").strip().lower()
    if encoding and encoding != "identity":
        return None
    return _content_length(response)


def _progress_percent(bytes_written: int, total_bytes: int | None) -> float | None:
    if not total_bytes:
        return None
    return round(min(100.0, (bytes_written / total_bytes) * 100), 2)


def _format_download_progress(bytes_written: int, total_bytes: int | None) -> str:
    written_mib = bytes_written // (1024 * 1024)
    percent = _progress_percent(bytes_written, total_bytes)
    if total_bytes and percent is not None:
        total_mib = total_bytes // (1024 * 1024)
        return f"{written_mib} MiB / {total_mib} MiB ({percent:.2f}%)"
    return f"{written_mib} MiB"


def _year_from_url(url: str) -> int | None:
    path = unquote(urlparse(url).path)
    parts = [part for part in path.split("/") if part]
    for part in reversed(parts[:-1]):
        if re.fullmatch(r"(?:19|20)[0-9]{2}", part):
            return int(part)

    filename = parts[-1] if parts else path
    match = BODACC_FILENAME_YEAR_RE.search(filename)
    if match:
        return int(match.group(1))

    match = YEAR_RE.search(filename)
    return int(match.group(0)) if match else None


def _is_under_base(base_url: str, child_url: str) -> bool:
    base = urlparse(base_url)
    child = urlparse(child_url)
    return child.scheme == base.scheme and child.netloc == base.netloc and child.path.startswith(base.path)


def _ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
