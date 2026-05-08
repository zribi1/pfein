from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument

from app.core.config import settings
from app.tools.bodacc_to_parquet import export_bodacc_archive_to_parquet

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"starting", "listing", "downloading", "exporting", "cancelling"}
DEFAULT_FAMILIES = ("PCL", "RCS-B")
BODACC_FILENAME_YEAR_RE = re.compile(r"(?:B[IX][ABC]|BODACC)[_-]?((?:19|20)[0-9]{2})[0-9]{3}", re.IGNORECASE)
YEAR_RE = re.compile(r"(?:19|20)[0-9]{2}")


class BodaccLabelExportAlreadyRunning(Exception):
    pass


class BodaccLabelExportCancelled(Exception):
    pass


@dataclass(frozen=True)
class BodaccLabelArchive:
    url: str
    year: int | None
    family: str
    local_path: Path


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


class BodaccLabelExportService:
    """Download current-year BODACC label archives and export them to Parquet."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.dataset_slug = settings.BODACC_LABEL_EXPORT_DATASET_SLUG
        self.input_dir = Path(settings.BODACC_CURRENT_DATA_DIR)
        self.output_base = Path(settings.DATA_LAKE_DIR) / "raw" / "bodacc"
        self.progress_path = Path(settings.BODACC_LABEL_EXPORT_PROGRESS_FILE)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)

    async def start(
        self,
        *,
        force_download: bool = False,
        force_export: bool = False,
        max_files: int | None = None,
        families: list[str] | None = None,
    ) -> str:
        await self.ensure_indexes()
        run_id = str(uuid4())
        families = _normalize_families(families)
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
                    "force_export_requested": force_export,
                    "max_files_requested": max_files,
                    "families_requested": families,
                    "discovered": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                    "rows": 0,
                    "downloaded": 0,
                    "download_skipped": 0,
                    "redownloaded": 0,
                    "current_file": "",
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
            raise BodaccLabelExportAlreadyRunning(
                f"bodacc label export already running with status={current.get('status', 'unknown')}"
            )
        await self._write_progress_from_state(state)
        return run_id

    async def run_started(
        self,
        run_id: str,
        *,
        force_download: bool = False,
        force_export: bool = False,
        max_files: int | None = None,
        families: list[str] | None = None,
    ) -> None:
        families = _normalize_families(families)
        stats: dict[str, Any] = {
            "discovered": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "rows": 0,
            "downloaded": 0,
            "download_skipped": 0,
            "redownloaded": 0,
            "failed_files": [],
        }
        try:
            await self._update_state_owned(run_id, {"status": "listing", "updated_at": _utcnow()})
            archives = await self._discover_archives(families)
            stats["discovered"] = len(archives)
            await self._update_state_owned(
                run_id,
                {
                    "discovered": len(archives),
                    "families_requested": families,
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
                    force_download=force_download,
                    force_export=force_export,
                )

            status = "done" if stats["failed"] == 0 else "done_with_failures"
            completion_fields: dict[str, Any] = {
                "status": status,
                "current_file": "",
                "download_status": None,
                "downloaded_bytes": None,
                "download_total_bytes": None,
                "download_progress_percent": None,
                "last_error": None if stats["failed"] == 0 else f"{stats['failed']} archive(s) failed",
                "updated_at": _utcnow(),
                **stats,
            }
            if stats["failed"] == 0:
                completion_fields["last_successful_run"] = _utcnow()
            await self._update_state_owned(run_id, completion_fields)
        except BodaccLabelExportCancelled:
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
            logger.exception("[bodacc-label-export] run failed")
            raise
        finally:
            await self._release_run(run_id)

    async def run(
        self,
        *,
        force_download: bool = False,
        force_export: bool = False,
        max_files: int | None = None,
        families: list[str] | None = None,
    ) -> None:
        run_id = await self.start(
            force_download=force_download,
            force_export=force_export,
            max_files=max_files,
            families=families,
        )
        await self.run_started(
            run_id,
            force_download=force_download,
            force_export=force_export,
            max_files=max_files,
            families=families,
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

    async def _discover_archives(self, families: list[str]) -> list[BodaccLabelArchive]:
        base_url = _ensure_trailing_slash(settings.BODACC_CURRENT_BASE_URL)
        timeout = httpx.Timeout(float(settings.BODACC_HTTP_TIMEOUT_SECONDS), connect=30.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(base_url)
            response.raise_for_status()

        parser = _HrefParser()
        parser.feed(response.text)
        found: dict[str, BodaccLabelArchive] = {}
        family_set = set(families)
        for href in parser.hrefs:
            if href.startswith(("#", "?", "mailto:")):
                continue
            url = urljoin(base_url, href)
            if not _is_under_base(base_url, url):
                continue
            name = Path(unquote(urlparse(url).path)).name
            if not name.lower().endswith(".taz"):
                continue
            family = _family_from_name(name)
            if family not in family_set:
                continue
            found[url] = BodaccLabelArchive(
                url=url,
                year=_year_from_name(name),
                family=family,
                local_path=self._local_path_for(url),
            )
        archives = sorted(found.values(), key=lambda archive: archive.url)
        logger.info(
            "[bodacc-label-export] discovered=%d families=%s",
            len(archives),
            ",".join(families),
        )
        return archives

    async def _handle_archive(
        self,
        run_id: str,
        archive: BodaccLabelArchive,
        stats: dict[str, Any],
        *,
        force_download: bool,
        force_export: bool,
    ) -> None:
        local_path = archive.local_path
        current_file = str(local_path)
        await self._update_state_owned(
            run_id,
            {
                "current_file": current_file,
                "current_remote_path": archive.url,
                "current_family": archive.family,
                "current_year": archive.year,
                "updated_at": _utcnow(),
                **stats,
            },
        )

        try:
            was_existing = local_path.exists()
            if force_download or not _archive_is_readable(local_path):
                await self._download_archive(run_id, archive, force_download=force_download, was_existing=was_existing)
                stats["downloaded"] += 1
                if was_existing:
                    stats["redownloaded"] += 1
            else:
                stats["download_skipped"] += 1

            output_dir = self.output_base / "current" / str(archive.year or "unknown") / local_path.stem
            if not force_export and _manifest_done(output_dir / "_manifest.json"):
                stats["skipped"] += 1
                logger.info("[bodacc-label-export] skip existing export archive=%s", local_path)
                await self._update_state_owned(run_id, {"updated_at": _utcnow(), **stats})
                return

            await self._update_state_owned(
                run_id,
                {
                    "status": "exporting",
                    "download_status": "complete",
                    "current_file": current_file,
                    "updated_at": _utcnow(),
                    **stats,
                },
            )
            rows = await asyncio.to_thread(
                export_bodacc_archive_to_parquet,
                input_path=local_path,
                output_dir=output_dir,
                mode="current",
                year=archive.year,
                batch_size=settings.BODACC_LABEL_EXPORT_BATCH_SIZE,
                include_raw_json=False,
            )
            stats["processed"] += 1
            stats["rows"] += rows
            logger.info("[bodacc-label-export] exported archive=%s rows=%d", local_path, rows)
            await self._update_state_owned(run_id, {"updated_at": _utcnow(), **stats})
        except BodaccLabelExportCancelled:
            raise
        except Exception as exc:
            stats["failed"] += 1
            stats["failed_files"].append(current_file)
            logger.exception("[bodacc-label-export] failed archive=%s error=%s", local_path, exc)
            await self._update_state_owned(
                run_id,
                {
                    "last_error": str(exc),
                    "updated_at": _utcnow(),
                    **stats,
                },
            )

    async def _download_archive(
        self,
        run_id: str,
        archive: BodaccLabelArchive,
        *,
        force_download: bool,
        was_existing: bool,
    ) -> None:
        local_path = archive.local_path
        tmp = local_path.with_suffix(local_path.suffix + ".part")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if tmp.exists():
            tmp.unlink()

        bytes_written = 0
        last_persisted = 0
        await self._update_state_owned(
            run_id,
            {
                "status": "downloading",
                "download_status": "redownloading" if was_existing else "downloading",
                "downloaded_bytes": 0,
                "download_total_bytes": None,
                "download_progress_percent": None,
                "force_download_requested": force_download,
                "updated_at": _utcnow(),
            },
        )
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", archive.url) as response:
                response.raise_for_status()
                total_bytes = _download_total_bytes(response)
                with tmp.open("wb") as fh:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        await self._check_cancel(run_id)
                        if not chunk:
                            continue
                        fh.write(chunk)
                        bytes_written += len(chunk)
                        if bytes_written - last_persisted >= 10 * 1024 * 1024:
                            last_persisted = bytes_written
                            await self._update_state_owned(
                                run_id,
                                {
                                    "downloaded_bytes": bytes_written,
                                    "download_total_bytes": total_bytes,
                                    "download_progress_percent": _progress_percent(bytes_written, total_bytes),
                                    "updated_at": _utcnow(),
                                },
                            )

        if not _archive_is_readable(tmp):
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"downloaded archive failed tar validation: {archive.url}")

        os.replace(tmp, local_path)
        await self._update_state_owned(
            run_id,
            {
                "download_status": "complete",
                "downloaded_bytes": bytes_written,
                "download_total_bytes": total_bytes,
                "download_progress_percent": _progress_percent(bytes_written, total_bytes),
                "current_archive_size_bytes": local_path.stat().st_size,
                "updated_at": _utcnow(),
            },
        )

    def _local_path_for(self, url: str) -> Path:
        rel = unquote(urlparse(url).path).lstrip("/")
        return self.input_dir / rel

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": self.dataset_slug})
        seed = _state_from_progress_file(self.progress_path, self.dataset_slug)
        if doc is None:
            doc = seed or {
                "dataset_slug": self.dataset_slug,
                "status": "idle",
                "run_id": None,
                "discovered": 0,
                "processed": 0,
                "skipped": 0,
                "failed": 0,
                "rows": 0,
                "current_file": "",
                "failed_files": [],
            }
            await self.state_coll.insert_one(doc)
            return doc
        if (
            seed
            and doc.get("status") not in ACTIVE_STATUSES
            and int(seed.get("rows") or 0) > int(doc.get("rows") or 0)
        ):
            await self.state_coll.update_one(
                {"dataset_slug": self.dataset_slug},
                {"$set": seed},
            )
            doc.update(seed)
        return doc

    async def _update_state(self, fields: dict[str, Any]) -> None:
        fields = {"updated_at": _utcnow(), **fields}
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug},
            {"$set": fields},
            upsert=True,
        )
        state = await self._get_state()
        await self._write_progress_from_state(state)

    async def _update_state_owned(self, run_id: str, fields: dict[str, Any]) -> None:
        fields = {"updated_at": _utcnow(), **fields}
        result = await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {"$set": fields},
        )
        if result.matched_count == 0:
            raise BodaccLabelExportAlreadyRunning("bodacc label export ownership lost")
        state = await self._get_state()
        await self._write_progress_from_state(state)

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {
                "$set": {"run_id": None, "updated_at": _utcnow()},
                "$unset": {
                    "force_download_requested": "",
                    "force_export_requested": "",
                    "max_files_requested": "",
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
        raise BodaccLabelExportCancelled("bodacc label export cancelled by user")

    async def _write_progress_from_state(self, state: dict[str, Any]) -> None:
        data = _public_progress(state)
        await asyncio.to_thread(_write_json_atomic, self.progress_path, data)


def _normalize_families(families: list[str] | None) -> list[str]:
    values = families or list(DEFAULT_FAMILIES)
    normalized: list[str] = []
    for family in values:
        value = family.strip().upper().replace("_", "-")
        if value == "RCSB":
            value = "RCS-B"
        if value in {"PCL", "RCS-B", "RCS-A", "BILAN"} and value not in normalized:
            normalized.append(value)
    return normalized or list(DEFAULT_FAMILIES)


def _family_from_name(name: str) -> str:
    value = name.upper().replace("_", "-")
    if value.startswith("PCL-BXA") or value.startswith("PCL-"):
        return "PCL"
    if value.startswith("RCS-B-BXB") or value.startswith("RCSB-BXB"):
        return "RCS-B"
    if value.startswith("RCS-A-BXA") or value.startswith("RCSA-BXA"):
        return "RCS-A"
    if value.startswith("BILAN-BXC"):
        return "BILAN"
    return "other"


def _year_from_name(name: str) -> int | None:
    match = BODACC_FILENAME_YEAR_RE.search(name)
    if match:
        return int(match.group(1))
    match = YEAR_RE.search(name)
    return int(match.group(0)) if match else None


def _archive_is_readable(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        found_file = False
        with tarfile.open(path, mode="r:*") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                found_file = True
                extracted = tf.extractfile(member)
                if extracted is None:
                    return False
                while extracted.read(1024 * 1024):
                    pass
        return found_file
    except (OSError, tarfile.TarError, EOFError):
        logger.warning("[bodacc-label-export] archive is not readable: %s", path)
        return False


def _manifest_done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return int(data.get("rows") or 0) > 0


def _download_total_bytes(response: httpx.Response) -> int | None:
    encoding = (response.headers.get("content-encoding") or "").strip().lower()
    if encoding and encoding != "identity":
        return None
    value = response.headers.get("content-length")
    if value is None or not value.isdigit():
        return None
    return int(value)


def _progress_percent(bytes_written: int, total_bytes: int | None) -> float | None:
    if not total_bytes:
        return None
    return round(min(100.0, (bytes_written / total_bytes) * 100), 2)


def _public_progress(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": state.get("status", "idle"),
        "discovered": int(state.get("discovered") or 0),
        "processed": int(state.get("processed") or 0),
        "skipped": int(state.get("skipped") or 0),
        "failed": int(state.get("failed") or 0),
        "rows": int(state.get("rows") or 0),
        "downloaded": int(state.get("downloaded") or 0),
        "download_skipped": int(state.get("download_skipped") or 0),
        "redownloaded": int(state.get("redownloaded") or 0),
        "current_file": state.get("current_file") or "",
        "failed_files": list(state.get("failed_files") or []),
        "updated_at": _json_value(state.get("updated_at") or _utcnow()),
    }


def _state_from_progress_file(path: Path, dataset_slug: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return {
        "dataset_slug": dataset_slug,
        "run_id": None,
        "status": str(data.get("status") or "idle"),
        "cancel_requested": False,
        "discovered": int(data.get("discovered") or 0),
        "processed": int(data.get("processed") or 0),
        "skipped": int(data.get("skipped") or 0),
        "failed": int(data.get("failed") or 0),
        "rows": int(data.get("rows") or 0),
        "downloaded": int(data.get("downloaded") or 0),
        "download_skipped": int(data.get("download_skipped") or 0),
        "redownloaded": int(data.get("redownloaded") or 0),
        "current_file": data.get("current_file") or "",
        "failed_files": list(data.get("failed_files") or []),
        "updated_at": _parse_datetime(data.get("updated_at")),
    }


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_value), encoding="utf-8")
    tmp.replace(path)


def _is_under_base(base_url: str, child_url: str) -> bool:
    base = urlparse(base_url)
    child = urlparse(child_url)
    return child.scheme == base.scheme and child.netloc == base.netloc and child.path.startswith(base.path)


def _ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
