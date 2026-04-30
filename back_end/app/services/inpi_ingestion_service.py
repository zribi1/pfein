"""INPI RNE bulk ingestion via FTP/SFTP.

Mirrors the resumable pattern of `IngestionService` but works on a directory tree
of JSON / JSON.gz / ZIP files exposed over FTP or SFTP. State lives in two
Mongo collections:

  - `ingestion_state` : run-level state (single doc keyed by `dataset_slug`),
    same shape as the parquet ingestion — so the same admin views keep working.
  - `inpi_rne_files`  : per-file state (one doc per remote path) tracking
    pending → downloading → downloaded → processing → done / failed.

Heavy IO (FTP/SFTP, gzip/zip parsing, bulk_write) runs in `asyncio.to_thread`
so the worker event loop stays free for state updates.
"""

from __future__ import annotations

import asyncio
import ftplib
import gzip
import io
import json
import logging
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, MongoClient, ReturnDocument, UpdateOne
from pymongo.errors import OperationFailure

from app.core.config import settings
from app.services.company_sync_service import (
    extract_denomination,
    extract_siren,
)

logger = logging.getLogger(__name__)

UPSERT_KEY = "siren"
ACTIVE_STATUSES = {"starting", "listing", "downloading", "processing", "resuming", "cancelling"}
FILE_STATUS_PENDING = "pending"
FILE_STATUS_DOWNLOADING = "downloading"
FILE_STATUS_DOWNLOADED = "downloaded"
FILE_STATUS_PROCESSING = "processing"
FILE_STATUS_DONE = "done"
FILE_STATUS_FAILED = "failed"


class InpiIngestionCancelled(Exception):
    pass


class InpiIngestionAlreadyRunning(Exception):
    pass


class InpiFtpError(Exception):
    pass


@dataclass(frozen=True)
class RemoteFile:
    path: str          # absolute remote path, posix
    size: int
    mtime: datetime | None


# ---------------------------------------------------------------------------
# FTP / SFTP connector
# ---------------------------------------------------------------------------

class _FtpConnector:
    """Thin sync wrapper around ftplib / paramiko.

    Used inside `asyncio.to_thread`. Never logs the password.
    Implements only what the bulk ingestor needs: walk(), download(), close().
    """

    def __init__(self) -> None:
        self.protocol = (settings.INPI_FTP_PROTOCOL or "ftp").lower()
        self.host = settings.INPI_FTP_HOST
        self.port = int(settings.INPI_FTP_PORT)
        self.user = settings.INPI_FTP_USER
        self._password = settings.INPI_FTP_PASSWORD
        self.timeout = int(settings.INPI_FTP_TIMEOUT)
        self._ftp: ftplib.FTP | None = None
        self._sftp: Any = None
        self._transport: Any = None

        if not self.host or not self.user or not self._password:
            raise InpiFtpError(
                "INPI FTP credentials not configured (INPI_FTP_HOST/USER/PASSWORD required)"
            )
        if self.protocol not in ("ftp", "sftp"):
            raise InpiFtpError(f"unsupported INPI_FTP_PROTOCOL={self.protocol!r}")

    def __enter__(self) -> "_FtpConnector":
        if self.protocol == "sftp":
            self._open_sftp()
        else:
            self._open_ftp()
        # Never put credentials in any log line.
        logger.info(
            "[inpi-ftp] connected protocol=%s host=%s port=%s user=%s",
            self.protocol, self.host, self.port, self.user,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        try:
            if self._sftp is not None:
                self._sftp.close()
        except Exception:
            pass
        try:
            if self._transport is not None:
                self._transport.close()
        except Exception:
            pass
        try:
            if self._ftp is not None:
                self._ftp.quit()
        except Exception:
            try:
                if self._ftp is not None:
                    self._ftp.close()
            except Exception:
                pass
        self._ftp = None
        self._sftp = None
        self._transport = None

    # -- connection openers --------------------------------------------------

    def _open_ftp(self) -> None:
        ftp = ftplib.FTP(timeout=self.timeout)
        ftp.connect(self.host, self.port or 21, timeout=self.timeout)
        ftp.login(self.user, self._password)
        try:
            ftp.set_pasv(True)
        except Exception:
            pass
        self._ftp = ftp

    def _open_sftp(self) -> None:
        try:
            import paramiko  # local import: heavy module
        except ImportError as exc:
            raise InpiFtpError(
                "paramiko is required for INPI_FTP_PROTOCOL=sftp; add it to requirements.txt"
            ) from exc

        transport = paramiko.Transport((self.host, self.port or 22))
        transport.banner_timeout = self.timeout
        transport.connect(username=self.user, password=self._password)
        self._transport = transport
        self._sftp = paramiko.SFTPClient.from_transport(transport)
        if self._sftp is None:
            raise InpiFtpError("failed to open SFTP channel")
        self._sftp.get_channel().settimeout(self.timeout)

    # -- listing -------------------------------------------------------------

    def walk(self, base: str) -> Iterator[RemoteFile]:
        """Recursively yield every file under `base` as RemoteFile."""
        base = base or "/"
        if self.protocol == "sftp":
            yield from self._walk_sftp(base)
        else:
            yield from self._walk_ftp(base)

    def _walk_sftp(self, base: str) -> Iterator[RemoteFile]:
        import stat as stat_mod
        stack = [base]
        while stack:
            current = stack.pop()
            try:
                entries = self._sftp.listdir_attr(current)
            except IOError as exc:
                raise InpiFtpError(f"sftp listdir failed for {current}: {exc}") from exc
            for entry in entries:
                name = entry.filename
                if name in (".", ".."):
                    continue
                child = _join_posix(current, name)
                mode = entry.st_mode or 0
                if stat_mod.S_ISDIR(mode):
                    stack.append(child)
                    continue
                mtime = (
                    datetime.fromtimestamp(entry.st_mtime, tz=timezone.utc)
                    if entry.st_mtime is not None else None
                )
                yield RemoteFile(path=child, size=int(entry.st_size or 0), mtime=mtime)

    def _walk_ftp(self, base: str) -> Iterator[RemoteFile]:
        """Recursive FTP walk.

        Strategy:
          1. Prefer MLSD (RFC 3659) — it gives us machine-parsable facts.
          2. If MLSD is refused (550/500/502), fall back to NLST.
          3. For each entry, classify dir vs file with a layered approach:
             - MLSD `type` fact when explicit (`dir`/`cdir`/`pdir`/`file`).
             - Otherwise, probe with CWD (works on every FTP server).
          4. Track visited dirs to break symlink cycles (common on RNE mounts).
        """
        ftp = self._ftp
        assert ftp is not None
        stack: list[str] = [base]
        seen_dirs: set[str] = set()

        while stack:
            current = stack.pop()
            if current in seen_dirs:
                logger.debug("[inpi-ftp] cycle skipped %s", current)
                continue
            seen_dirs.add(current)

            entries, use_mlsd = self._list_dir(current)
            logger.info(
                "[inpi-ftp] listed %s entries=%d mlsd=%s",
                current, len(entries), use_mlsd,
            )

            for name, facts in entries:
                if name in (".", ".."):
                    continue
                # MLSD/NLST may return either bare names or absolute paths.
                child = name if name.startswith("/") else _join_posix(current, name)

                is_dir = self._classify_entry(child, facts, use_mlsd)
                if is_dir:
                    logger.debug("[inpi-ftp] dir  %s", child)
                    stack.append(child)
                    continue

                size = int(facts.get("size") or 0) if use_mlsd else self._ftp_size(child)
                mtime = (
                    _parse_mlsd_modify(facts.get("modify"))
                    if use_mlsd
                    else self._ftp_mdtm(child)
                )
                logger.debug("[inpi-ftp] file %s size=%s", child, size)
                yield RemoteFile(path=child, size=size, mtime=mtime)

    def _list_dir(self, path: str) -> tuple[list[tuple[str, dict]], bool]:
        """Return (entries, used_mlsd). Empty list on permission error."""
        ftp = self._ftp
        assert ftp is not None
        try:
            return list(ftp.mlsd(path)), True
        except (ftplib.error_perm, ftplib.error_proto, ftplib.error_temp) as exc:
            logger.debug("[inpi-ftp] MLSD refused on %s: %s — falling back to NLST", path, exc)
        try:
            return [(name, {}) for name in ftp.nlst(path)], False
        except ftplib.error_perm as exc:
            logger.warning("[inpi-ftp] cannot list %s: %s", path, exc)
            return [], False

    def _classify_entry(self, path: str, facts: dict, use_mlsd: bool) -> bool:
        """Decide if `path` is a directory.

        MLSD `type` is fragile across servers — if missing or non-standard
        (e.g. `OS.unix=symlink`), we fall through to a CWD probe which is
        universally reliable.
        """
        if use_mlsd:
            ftype = (facts.get("type") or "").lower()
            if ftype in ("dir", "cdir", "pdir"):
                return True
            if ftype == "file":
                return False
            # symlink, unknown, missing -> probe.
        return self._ftp_is_dir(path)

    def _ftp_is_dir(self, path: str) -> bool:
        ftp = self._ftp
        assert ftp is not None
        cwd = ftp.pwd()
        try:
            ftp.cwd(path)
            ftp.cwd(cwd)
            return True
        except ftplib.error_perm:
            return False

    def _ftp_size(self, path: str) -> int:
        ftp = self._ftp
        assert ftp is not None
        try:
            ftp.voidcmd("TYPE I")
            return int(ftp.size(path) or 0)
        except (ftplib.error_perm, ftplib.error_temp):
            return 0

    def _ftp_mdtm(self, path: str) -> datetime | None:
        ftp = self._ftp
        assert ftp is not None
        try:
            resp = ftp.sendcmd(f"MDTM {path}")
        except (ftplib.error_perm, ftplib.error_temp):
            return None
        # response: "213 YYYYMMDDHHMMSS"
        parts = resp.split()
        if len(parts) >= 2 and parts[0].startswith("213"):
            return _parse_mlsd_modify(parts[1])
        return None

    # -- download ------------------------------------------------------------

    def download(
        self,
        remote_path: str,
        local_tmp: Path,
        on_progress: Any = None,
    ) -> int:
        """Stream-download into `local_tmp`. Returns bytes written.

        `on_progress(bytes_written: int)` is invoked after each chunk so callers
        can log/persist progress. Kept synchronous (this runs in a worker thread).
        """
        local_tmp.parent.mkdir(parents=True, exist_ok=True)
        if local_tmp.exists():
            local_tmp.unlink()
        written = 0
        with local_tmp.open("wb") as f:
            def _writer(chunk: bytes) -> None:
                nonlocal written
                f.write(chunk)
                written += len(chunk)
                if on_progress is not None:
                    on_progress(written)

            if self.protocol == "sftp":
                with self._sftp.open(remote_path, "rb") as remote_f:
                    remote_f.prefetch()
                    while True:
                        chunk = remote_f.read(1024 * 1024)
                        if not chunk:
                            break
                        _writer(chunk)
            else:
                ftp = self._ftp
                assert ftp is not None
                ftp.voidcmd("TYPE I")
                ftp.retrbinary(f"RETR {remote_path}", _writer, blocksize=1024 * 1024)
        return written


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class InpiIngestionService:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.files_coll = db[settings.INPI_RNE_FILES_COLLECTION]
        self.companies_coll = db[settings.INPI_RNE_COLLECTION]
        self.data_dir = Path(settings.INPI_LOCAL_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_slug = settings.INPI_RNE_DATASET_SLUG

    # -- public --------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)
        await self.files_coll.create_index([("remote_path", ASCENDING)], unique=True)
        await self.files_coll.create_index([("status", ASCENDING)])
        try:
            await self.companies_coll.create_index([(UPSERT_KEY, ASCENDING)], unique=True)
        except OperationFailure as exc:
            if exc.code != 86:  # IndexOptionsConflict — already exists with different options
                raise

    async def run(self, force: bool = False) -> None:
        await self.ensure_indexes()
        run_id = str(uuid4())
        await self._acquire_run(run_id, force)

        try:
            # 1) Resume: replay any file left "downloading" or "processing".
            await self._update_state_owned(run_id, {"status": "resuming", "last_check_at": _utcnow()})
            await self._resume_pending_files(run_id)

            await self._check_cancel(run_id)

            # 2) List remote tree, then keep only ingestable files.
            await self._update_state_owned(run_id, {"status": "listing", "last_check_at": _utcnow()})
            remote_files_all = await asyncio.to_thread(self._list_remote_files_sync)
            remote_files = [f for f in remote_files_all if self._should_ingest(f.path)]
            logger.info(
                "[inpi] discovered=%d ingestable=%d filter=%r",
                len(remote_files_all), len(remote_files),
                settings.INPI_REMOTE_INCLUDE_GLOB or "<default extensions>",
            )
            if remote_files_all and not remote_files:
                # Help the operator see what was visible without ingesting nothing silently.
                sample = [f.path for f in remote_files_all[:10]]
                logger.warning(
                    "[inpi] listing returned %d files but none matched the filter; sample=%s",
                    len(remote_files_all), sample,
                )
            await self._update_state_owned(
                run_id,
                {
                    "remote_files_total": len(remote_files_all),
                    "remote_files_ingestable": len(remote_files),
                    "last_check_at": _utcnow(),
                },
            )

            # 3) Reconcile per-file state (insert pending docs for new ones).
            new_files, to_process = await self._reconcile_files(remote_files, force)
            logger.info(
                "[inpi] new=%d to_process=%d (force=%s)",
                new_files, len(to_process), force,
            )

            # 4) Download + ingest each pending file.
            limit = settings.INPI_RNE_MAX_FILES_PER_RUN
            processed = 0
            ingested_total = 0
            for entry in to_process:
                await self._check_cancel(run_id)
                if limit and processed >= limit:
                    logger.info("[inpi] reached INPI_RNE_MAX_FILES_PER_RUN=%d, stopping", limit)
                    break
                rows = await self._handle_file(run_id, entry)
                ingested_total += rows
                processed += 1

            # 5) Done.
            await self._update_state_owned(
                run_id,
                {
                    "status": "idle",
                    "last_successful_run": _utcnow(),
                    "last_check_at": _utcnow(),
                    "rows_ingested_last_run": ingested_total,
                    "files_processed_last_run": processed,
                    "last_error": None,
                },
            )
        except InpiIngestionCancelled:
            raise
        except Exception as exc:
            await self._update_state_owned(
                run_id,
                {"status": "error", "last_error": str(exc), "last_check_at": _utcnow()},
            )
            logger.exception("[inpi] run failed")
            raise
        finally:
            await self._release_run(run_id)

    async def request_cancel(self) -> dict[str, Any]:
        state = await self._get_state()
        if state.get("status") not in ACTIVE_STATUSES:
            return {"accepted": False, "status": state.get("status", "idle")}
        await self._update_state(
            {"cancel_requested": True, "status": "cancelling", "last_error": None}
        )
        return {"accepted": True, "status": "cancelling"}

    async def get_status(self) -> dict[str, Any]:
        state = await self._get_state()
        state.pop("_id", None)
        counts = await self._counts_by_status()
        state["files_by_status"] = counts
        return state

    async def list_remote(self, base: str | None = None, limit: int = 200) -> dict[str, Any]:
        """List the remote FTP/SFTP tree without touching Mongo.

        Diagnostic helper exposed by the admin endpoint.
        """
        target = base or settings.INPI_REMOTE_BASE_DIR or "/"

        def _list_sync() -> list[RemoteFile]:
            with _FtpConnector() as conn:
                out: list[RemoteFile] = []
                for f in conn.walk(target):
                    out.append(f)
                    if limit and len(out) >= limit:
                        break
                return out

        files = await asyncio.to_thread(_list_sync)
        return {
            "base": target,
            "count": len(files),
            "filter": settings.INPI_REMOTE_INCLUDE_GLOB or "<default extensions>",
            "files": [
                {
                    "path": f.path,
                    "size": f.size,
                    "mtime": f.mtime.isoformat() if f.mtime else None,
                    "ingestable": self._should_ingest(f.path),
                }
                for f in files
            ],
        }

    @staticmethod
    def _should_ingest(path: str) -> bool:
        """Return True if a remote path should be downloaded and parsed.

        Default: any of .zip / .json / .json.gz / .ndjson / .jsonl (with .gz).
        Override with INPI_REMOTE_INCLUDE_GLOB (single fnmatch pattern, e.g. ``*.zip``).
        """
        glob = (settings.INPI_REMOTE_INCLUDE_GLOB or "").strip()
        if glob:
            from fnmatch import fnmatch
            return fnmatch(path.lower(), glob.lower())
        lower = path.lower()
        return lower.endswith(
            (
                ".zip",
                ".json",
                ".json.gz",
                ".ndjson",
                ".ndjson.gz",
                ".jsonl",
                ".jsonl.gz",
            )
        )

    # -- file lifecycle ------------------------------------------------------

    async def _resume_pending_files(self, run_id: str) -> None:
        cursor = self.files_coll.find(
            {"status": {"$in": [FILE_STATUS_DOWNLOADING, FILE_STATUS_PROCESSING]}}
        )
        async for doc in cursor:
            local_path = doc.get("local_path")
            remote_path = doc.get("remote_path")
            logger.info("[inpi] resuming %s status=%s", remote_path, doc.get("status"))
            # If only partially downloaded, fall back to pending so it's redone cleanly.
            if local_path and Path(local_path).with_suffix(Path(local_path).suffix + ".part").exists():
                await self.files_coll.update_one(
                    {"remote_path": remote_path},
                    {"$set": {"status": FILE_STATUS_PENDING, "last_error": None}},
                )

    async def _reconcile_files(
        self, remote_files: list[RemoteFile], force: bool
    ) -> tuple[int, list[dict[str, Any]]]:
        new_count = 0
        to_process: list[dict[str, Any]] = []
        for rf in remote_files:
            existing = await self.files_coll.find_one({"remote_path": rf.path})
            if existing is None:
                doc = {
                    "remote_path": rf.path,
                    "remote_size": rf.size,
                    "remote_mtime": rf.mtime,
                    "status": FILE_STATUS_PENDING,
                    "attempts": 0,
                    "discovered_at": _utcnow(),
                }
                await self.files_coll.insert_one(doc)
                new_count += 1
                to_process.append(doc)
                continue

            same = (
                existing.get("status") == FILE_STATUS_DONE
                and existing.get("remote_size") == rf.size
                and existing.get("remote_mtime") == rf.mtime
            )
            if same and not force:
                continue

            # Either changed remotely, failed previously, or force re-ingest.
            await self.files_coll.update_one(
                {"remote_path": rf.path},
                {
                    "$set": {
                        "remote_size": rf.size,
                        "remote_mtime": rf.mtime,
                        "status": FILE_STATUS_PENDING,
                        "last_error": None,
                    }
                },
            )
            existing.update(
                {"remote_size": rf.size, "remote_mtime": rf.mtime, "status": FILE_STATUS_PENDING}
            )
            to_process.append(existing)
        return new_count, to_process

    async def _handle_file(self, run_id: str, file_doc: dict[str, Any]) -> int:
        remote_path = file_doc["remote_path"]
        remote_size = int(file_doc.get("remote_size") or 0)
        local_path = self._local_path_for(remote_path)

        await self._update_state_owned(
            run_id,
            {
                "status": "downloading",
                "current_remote_path": remote_path,
                "current_local_path": str(local_path),
                "downloaded_bytes": 0,
                "last_check_at": _utcnow(),
            },
        )
        await self.files_coll.update_one(
            {"remote_path": remote_path},
            {
                "$set": {
                    "status": FILE_STATUS_DOWNLOADING,
                    "local_path": str(local_path),
                    "last_error": None,
                },
                "$inc": {"attempts": 1},
            },
        )

        # Download with retry/backoff.
        try:
            written = await self._with_retry(
                lambda: asyncio.to_thread(self._download_one_sync, remote_path, local_path),
                what=f"download {remote_path}",
            )
        except Exception as exc:
            await self.files_coll.update_one(
                {"remote_path": remote_path},
                {"$set": {"status": FILE_STATUS_FAILED, "last_error": str(exc)}},
            )
            raise

        if remote_size and written != remote_size:
            msg = f"size mismatch: remote={remote_size} written={written}"
            await self.files_coll.update_one(
                {"remote_path": remote_path},
                {"$set": {"status": FILE_STATUS_FAILED, "last_error": msg}},
            )
            raise InpiFtpError(msg)

        await self.files_coll.update_one(
            {"remote_path": remote_path},
            {
                "$set": {
                    "status": FILE_STATUS_DOWNLOADED,
                    "local_size": written,
                    "downloaded_at": _utcnow(),
                }
            },
        )

        await self._check_cancel(run_id)

        # Process.
        await self._update_state_owned(
            run_id, {"status": "processing", "last_check_at": _utcnow()}
        )
        await self.files_coll.update_one(
            {"remote_path": remote_path}, {"$set": {"status": FILE_STATUS_PROCESSING}}
        )
        try:
            rows = await asyncio.to_thread(self._process_file_sync, local_path)
        except Exception as exc:
            await self.files_coll.update_one(
                {"remote_path": remote_path},
                {"$set": {"status": FILE_STATUS_FAILED, "last_error": str(exc)}},
            )
            raise

        await self.files_coll.update_one(
            {"remote_path": remote_path},
            {
                "$set": {
                    "status": FILE_STATUS_DONE,
                    "rows_ingested": rows,
                    "processed_at": _utcnow(),
                    "last_error": None,
                }
            },
        )

        if settings.INPI_DELETE_AFTER_INGEST:
            try:
                local_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("[inpi] failed to remove %s: %s", local_path, exc)

        logger.info("[inpi] file done remote=%s rows=%d", remote_path, rows)
        return rows

    # -- sync helpers (run in thread) ---------------------------------------

    def _list_remote_files_sync(self) -> list[RemoteFile]:
        with _FtpConnector() as conn:
            return list(conn.walk(settings.INPI_REMOTE_BASE_DIR or "/"))

    def _download_one_sync(self, remote_path: str, local_path: Path) -> int:
        tmp = local_path.with_suffix(local_path.suffix + ".part")
        # Sync Mongo client so we can report progress from this worker thread
        # (we cannot await Motor from inside `asyncio.to_thread`).
        sync_client = MongoClient(settings.MONGO_URI)
        try:
            state_coll = sync_client[settings.MONGO_DB][settings.INGESTION_STATE_COLLECTION]
            files_coll = sync_client[settings.MONGO_DB][settings.INPI_RNE_FILES_COLLECTION]

            log_step = 50 * 1024 * 1024     # log every 50 MiB
            state_step = 10 * 1024 * 1024   # candidate state flush every 10 MiB
            state_min_interval = 3.0        # but at most once every 3 s
            last_log = 0
            last_state_bytes = 0
            last_state_at = time.monotonic()

            def _on_progress(written: int) -> None:
                nonlocal last_log, last_state_bytes, last_state_at
                if written - last_log >= log_step:
                    logger.info(
                        "[inpi] download progress %s: %d MiB",
                        remote_path, written // (1024 * 1024),
                    )
                    last_log = written
                now = time.monotonic()
                if (
                    written - last_state_bytes >= state_step
                    and now - last_state_at >= state_min_interval
                ):
                    state_coll.update_one(
                        {"dataset_slug": settings.INPI_RNE_DATASET_SLUG},
                        {"$set": {"downloaded_bytes": written, "last_check_at": _utcnow()}},
                    )
                    files_coll.update_one(
                        {"remote_path": remote_path},
                        {"$set": {"downloaded_bytes": written}},
                    )
                    last_state_bytes = written
                    last_state_at = now

            logger.info("[inpi] download start remote=%s -> %s", remote_path, local_path)
            with _FtpConnector() as conn:
                written = conn.download(remote_path, tmp, on_progress=_on_progress)

            if local_path.exists():
                local_path.unlink()
            os.replace(tmp, local_path)
            # Final flush so Mongo reflects the real total bytes.
            state_coll.update_one(
                {"dataset_slug": settings.INPI_RNE_DATASET_SLUG},
                {"$set": {"downloaded_bytes": written, "last_check_at": _utcnow()}},
            )
            files_coll.update_one(
                {"remote_path": remote_path},
                {"$set": {"downloaded_bytes": written}},
            )
            logger.info(
                "[inpi] download done remote=%s bytes=%d (%d MiB)",
                remote_path, written, written // (1024 * 1024),
            )
            return written
        finally:
            sync_client.close()

    def _process_file_sync(self, path: Path) -> int:
        sync_client = MongoClient(settings.MONGO_URI)
        try:
            sync_coll = sync_client[settings.MONGO_DB][settings.INPI_RNE_COLLECTION]
            total = 0
            buf: list[UpdateOne] = []
            batch_size = settings.INPI_RNE_BATCH_SIZE
            for record in self._iter_records(path):
                doc = self._normalize_record(record)
                if doc is None:
                    continue
                buf.append(UpdateOne({UPSERT_KEY: doc[UPSERT_KEY]}, {"$set": doc}, upsert=True))
                if len(buf) >= batch_size:
                    sync_coll.bulk_write(buf, ordered=False)
                    total += len(buf)
                    buf.clear()
            if buf:
                sync_coll.bulk_write(buf, ordered=False)
                total += len(buf)
            return total
        finally:
            sync_client.close()

    def _iter_records(self, path: Path) -> Iterable[dict[str, Any]]:
        name = path.name.lower()
        if name.endswith(".zip"):
            yield from _iter_records_zip(path)
        elif name.endswith(".json.gz") or name.endswith(".jsonl.gz") or name.endswith(".ndjson.gz"):
            with gzip.open(path, "rb") as f:
                yield from _iter_records_stream(f, name)
        elif name.endswith(".gz"):
            with gzip.open(path, "rb") as f:
                yield from _iter_records_stream(f, name[:-3])
        else:
            with path.open("rb") as f:
                yield from _iter_records_stream(f, name)

    def _normalize_record(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        siren = extract_siren("inpi", raw)
        if not siren:
            return None
        return {
            UPSERT_KEY: siren,
            "denomination": extract_denomination("inpi", raw),
            "rne_raw": raw,
            "rne_updated_at": _utcnow(),
            "source": "inpi_rne_bulk",
        }

    # -- run lifecycle (single-flight) --------------------------------------

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
            raise InpiIngestionAlreadyRunning("inpi ingestion ownership lost")

    async def _acquire_run(self, run_id: str, force: bool) -> dict[str, Any]:
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
                    "last_error": None,
                    "last_started_at": _utcnow(),
                    "last_check_at": _utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if state is None:
            current = await self._get_state()
            raise InpiIngestionAlreadyRunning(
                f"inpi ingestion already running with status={current.get('status', 'unknown')}"
            )
        return state

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": self.dataset_slug, "run_id": run_id},
            {"$set": {"run_id": None}, "$unset": {"force_requested": ""}},
        )

    async def _check_cancel(self, run_id: str | None = None) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return
        fields = {"cancel_requested": False, "status": "cancelled"}
        if run_id is None:
            await self._update_state(fields)
        else:
            await self._update_state_owned(run_id, fields)
        raise InpiIngestionCancelled("inpi ingestion cancelled by user")

    async def _counts_by_status(self) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        out: dict[str, int] = {}
        async for doc in self.files_coll.aggregate(pipeline):
            out[str(doc["_id"])] = int(doc["n"])
        return out

    # -- helpers -------------------------------------------------------------

    def _local_path_for(self, remote_path: str) -> Path:
        # Mirror the remote tree under data_dir (strip leading slash).
        rel = remote_path.lstrip("/")
        return self.data_dir / rel

    async def _with_retry(self, factory, *, what: str) -> Any:
        attempts = 0
        max_attempts = max(1, int(settings.API_RETRY_MAX_ATTEMPTS))
        base = float(settings.API_RETRY_BASE_DELAY_SECONDS)
        cap = float(settings.API_RETRY_MAX_DELAY_SECONDS)
        retryable = (InpiFtpError,) + tuple(ftplib.all_errors) + (OSError, TimeoutError)
        while True:
            try:
                return await factory()
            except retryable as exc:
                attempts += 1
                if attempts >= max_attempts:
                    logger.error("[inpi] %s failed after %d attempts: %s", what, attempts, exc)
                    raise
                delay = min(cap, base * (2 ** (attempts - 1)))
                logger.warning(
                    "[inpi] %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    what, attempts, max_attempts, delay, exc,
                )
                await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Free helpers
# ---------------------------------------------------------------------------

def _join_posix(parent: str, child: str) -> str:
    return str(PurePosixPath(parent.rstrip("/") or "/") / child)


def _parse_mlsd_modify(value: str | None) -> datetime | None:
    if not value or len(value) < 14:
        return None
    try:
        # MLSD modify is YYYYMMDDHHMMSS in UTC
        return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iter_records_zip(path: Path) -> Iterable[dict[str, Any]]:
    with zipfile.ZipFile(path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        logger.info("[inpi] zip open %s entries=%d", path.name, len(infos))
        for idx, info in enumerate(infos, 1):
            if idx == 1 or idx % 1000 == 0 or idx == len(infos):
                logger.info(
                    "[inpi] zip %s entry %d/%d %s",
                    path.name, idx, len(infos), info.filename,
                )
            inner = info.filename.lower()
            with zf.open(info) as fh:
                if inner.endswith(".gz"):
                    with gzip.open(fh, "rb") as gz:
                        yield from _iter_records_stream(gz, inner[:-3])
                else:
                    yield from _iter_records_stream(fh, inner)


def _iter_records_stream(fh: Any, hint_name: str) -> Iterable[dict[str, Any]]:
    """Yield records from a binary file-like.

    Supports:
      - JSON Lines / NDJSON (one JSON object per line)
      - JSON array  (list at top level)
      - JSON object containing a list under common keys
      - JSON object representing a single record with `siren`
    """
    name = hint_name.lower()
    if name.endswith(".jsonl") or name.endswith(".ndjson"):
        yield from _iter_jsonl(fh)
        return

    # Peek first non-whitespace byte to decide between array/object/jsonl.
    if not hasattr(fh, "read"):
        return
    head = _peek_nonspace(fh)
    if head == b"[" or head == b"{":
        try:
            data = json.load(io.TextIOWrapper(fh, encoding="utf-8"))
        except json.JSONDecodeError:
            # Could be JSONL with a leading object on first line; restart as jsonl.
            fh.seek(0)
            yield from _iter_jsonl(fh)
            return
        yield from _flatten_json(data)
        return

    # Default: try JSONL.
    fh.seek(0)
    yield from _iter_jsonl(fh)


def _peek_nonspace(fh: Any) -> bytes:
    pos = fh.tell() if hasattr(fh, "tell") else 0
    while True:
        ch = fh.read(1)
        if not ch:
            try:
                fh.seek(pos)
            except Exception:
                pass
            return b""
        if ch not in (b" ", b"\n", b"\r", b"\t"):
            try:
                fh.seek(pos)
            except Exception:
                pass
            return ch


def _iter_jsonl(fh: Any) -> Iterable[dict[str, Any]]:
    text = io.TextIOWrapper(fh, encoding="utf-8")
    for line in text:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("[inpi] skipping malformed JSONL line")
            continue
        if isinstance(obj, dict):
            yield obj


def _flatten_json(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(data, dict):
        # Top-level dict: prefer common list keys, otherwise treat as single record.
        for key in ("companies", "entreprises", "items", "results", "data", "records"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
                return
        yield data


