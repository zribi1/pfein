import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument, UpdateOne

from app.core.config import settings

logger = logging.getLogger(__name__)

UPSERT_KEY = "siren"
ACTIVE_STATUSES = {"starting", "downloading", "ingesting", "resuming", "cancelling"}


class IngestionCancelled(Exception):
    pass


class IngestionAlreadyRunning(Exception):
    pass


class IngestionService:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.INGESTION_STATE_COLLECTION]
        self.data_coll = db[settings.INGESTION_COLLECTION]
        self.data_dir = Path(settings.INGESTION_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def ensure_indexes(self) -> None:
        await self.data_coll.create_index([(UPSERT_KEY, ASCENDING)], unique=True)
        await self.state_coll.create_index([("dataset_slug", ASCENDING)], unique=True)

    async def run(self, dataset_slug: str, force: bool = False) -> None:
        await self.ensure_indexes()
        run_id = str(uuid4())
        state = await self._acquire_run(dataset_slug, run_id, force)

        try:
            current_path = state.get("current_file_path")
            if current_path and Path(current_path).exists():
                logger.info("[ingest] resuming pending file %s", current_path)
                await self._update_state_owned(
                    dataset_slug,
                    run_id,
                    {"status": "resuming", "last_check_at": _utcnow(), "last_error": None},
                )
                inserted = await self._ingest_parquet(Path(current_path), dataset_slug)
                await self._mark_ingested(
                    dataset_slug,
                    run_id,
                    state["current_file_remote_update"],
                    inserted,
                )
                state = await self._get_state(dataset_slug)
            elif current_path:
                logger.warning("[ingest] state pointed at missing file %s, clearing", current_path)
                await self._update_state_owned(dataset_slug, run_id, {"current_file_path": None})

            await self._check_cancel(dataset_slug, run_id)
            meta = await self._fetch_dataset_meta(dataset_slug)
            remote_update = _parse_iso(meta.get("last_update"))
            last_known = state.get("last_remote_update")
            if not force and last_known and remote_update <= last_known:
                logger.info(
                    "[ingest] no new version (remote=%s, last=%s)", remote_update, last_known
                )
                await self._update_state_owned(
                    dataset_slug,
                    run_id,
                    {"last_check_at": _utcnow(), "status": "idle", "last_error": None},
                )
                return

            resource = next(
                (r for r in meta.get("resources", []) if str(r.get("format", "")).lower() == "parquet"),
                None,
            )
            if not resource:
                logger.error("[ingest] no parquet resource on dataset %s", dataset_slug)
                await self._update_state_owned(
                    dataset_slug,
                    run_id,
                    {"status": "error", "last_error": "no parquet resource"},
                )
                return

            target = self.data_dir / f"{dataset_slug}.parquet"
            try:
                await self._download(resource["url"], target, dataset_slug, run_id)
            except IngestionCancelled:
                return

            await self._update_state_owned(
                dataset_slug,
                run_id,
                {
                    "current_file_path": str(target),
                    "current_file_remote_update": remote_update,
                    "status": "ingesting",
                },
            )

            inserted = await self._ingest_parquet(target, dataset_slug)
            await self._mark_ingested(dataset_slug, run_id, remote_update, inserted)
        except IngestionCancelled:
            raise
        except Exception as exc:
            await self._update_state_owned(
                dataset_slug,
                run_id,
                {"status": "error", "last_error": str(exc)},
            )
            raise
        finally:
            await self._release_run(dataset_slug, run_id)

    async def request_cancel(self, dataset_slug: str) -> dict[str, Any]:
        state = await self._get_state(dataset_slug)
        if state.get("status") not in ACTIVE_STATUSES:
            return {"accepted": False, "status": state.get("status", "idle")}

        await self._update_state(
            dataset_slug,
            {
                "cancel_requested": True,
                "status": "cancelling",
                "last_error": None,
            },
        )
        return {"accepted": True, "status": "cancelling"}

    async def get_status(self, dataset_slug: str) -> dict[str, Any]:
        state = await self._get_state(dataset_slug)
        state.pop("_id", None)
        return state

    async def _get_state(self, dataset_slug: str) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"dataset_slug": dataset_slug})
        if doc is None:
            doc = {"dataset_slug": dataset_slug, "status": "idle", "run_id": None}
            await self.state_coll.insert_one(doc)
        return doc

    async def _update_state(self, dataset_slug: str, fields: dict[str, Any]) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": dataset_slug},
            {"$set": fields},
            upsert=True,
        )

    async def _update_state_owned(
        self, dataset_slug: str, run_id: str, fields: dict[str, Any]
    ) -> None:
        result = await self.state_coll.update_one(
            {"dataset_slug": dataset_slug, "run_id": run_id},
            {"$set": fields},
            upsert=False,
        )
        if result.matched_count == 0:
            raise IngestionAlreadyRunning("ingestion ownership lost")

    async def _acquire_run(self, dataset_slug: str, run_id: str, force: bool) -> dict[str, Any]:
        await self._get_state(dataset_slug)
        state = await self.state_coll.find_one_and_update(
            {
                "dataset_slug": dataset_slug,
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
            current = await self._get_state(dataset_slug)
            raise IngestionAlreadyRunning(
                f"ingestion already running with status={current.get('status', 'unknown')}"
            )
        return state

    async def _release_run(self, dataset_slug: str, run_id: str) -> None:
        await self.state_coll.update_one(
            {"dataset_slug": dataset_slug, "run_id": run_id},
            {"$set": {"run_id": None}, "$unset": {"force_requested": ""}},
        )

    async def _check_cancel(self, dataset_slug: str, run_id: str | None = None) -> None:
        state = await self._get_state(dataset_slug)
        if state.get("cancel_requested"):
            fields = {"cancel_requested": False, "status": "cancelled"}
            if run_id is None:
                await self._update_state(dataset_slug, fields)
            else:
                await self._update_state_owned(dataset_slug, run_id, fields)
            raise IngestionCancelled("ingestion cancelled by user")

    async def _mark_ingested(
        self, dataset_slug: str, run_id: str, remote_update: datetime, rows: int
    ) -> None:
        state = await self._get_state(dataset_slug)
        path = state.get("current_file_path")
        if path:
            try:
                os.remove(path)
                logger.info("[ingest] removed %s", path)
            except OSError as exc:
                logger.warning("[ingest] failed to remove %s: %s", path, exc)
        await self._update_state_owned(
            dataset_slug,
            run_id,
            {
                "last_remote_update": remote_update,
                "last_successful_run": _utcnow(),
                "rows_ingested_last_run": rows,
                "current_file_path": None,
                "current_file_remote_update": None,
                "download_target": None,
                "downloaded_bytes": 0,
                "status": "idle",
                "last_error": None,
            },
        )

    async def _fetch_dataset_meta(self, dataset_slug: str) -> dict[str, Any]:
        url = f"{settings.DATAGOUV_API_BASE}/datasets/{dataset_slug}/"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def _download(self, url: str, target: Path, dataset_slug: str, run_id: str) -> None:
        tmp = target.with_suffix(target.suffix + ".tmp")
        if tmp.exists():
            tmp.unlink()
        logger.info("[ingest] downloading %s -> %s", url, target)
        await self._update_state_owned(
            dataset_slug,
            run_id,
            {
                "status": "downloading",
                "download_target": str(target),
                "downloaded_bytes": 0,
                "last_check_at": _utcnow(),
            },
        )

        bytes_written = 0
        last_log_bytes = 0
        log_interval = 50 * 1024 * 1024
        chunk_count = 0

        try:
            async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    total_bytes = int(resp.headers.get("content-length", 0))
                    if total_bytes:
                        logger.info("[ingest] total size: %s MiB", total_bytes // (1024 * 1024))
                    with tmp.open("wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            chunk_count += 1
                            if chunk_count % 10 == 0:
                                await self._check_cancel(dataset_slug, run_id)
                            f.write(chunk)
                            bytes_written += len(chunk)
                            if bytes_written - last_log_bytes >= log_interval:
                                await self._update_state_owned(
                                    dataset_slug,
                                    run_id,
                                    {"downloaded_bytes": bytes_written, "last_check_at": _utcnow()},
                                )
                                if total_bytes:
                                    pct = (bytes_written / total_bytes) * 100
                                    logger.info(
                                        "[ingest] progress: %s / %s MiB (%.1f%%)",
                                        bytes_written // (1024 * 1024),
                                        total_bytes // (1024 * 1024),
                                        pct,
                                    )
                                else:
                                    logger.info(
                                        "[ingest] progress: %s MiB",
                                        bytes_written // (1024 * 1024),
                                    )
                                last_log_bytes = bytes_written
                    await self._update_state_owned(
                        dataset_slug,
                        run_id,
                        {"downloaded_bytes": bytes_written, "last_check_at": _utcnow()},
                    )

            if target.exists():
                target.unlink()
            os.replace(tmp, target)
            logger.info("[ingest] download complete (%s MiB)", bytes_written // (1024 * 1024))
        except IngestionCancelled:
            if tmp.exists():
                tmp.unlink()
            logger.info("[ingest] download cancelled")
            raise

    async def _ingest_parquet(self, path: Path, dataset_slug: str) -> int:
        return await asyncio.to_thread(self._ingest_parquet_sync, path, dataset_slug)

    def _ingest_parquet_sync(self, path: Path, dataset_slug: str) -> int:
        import pyarrow.parquet as pq

        from pymongo import MongoClient

        sync_client = MongoClient(settings.MONGO_URI)
        try:
            sync_coll = sync_client[settings.MONGO_DB][settings.INGESTION_COLLECTION]
            state_coll = sync_client[settings.MONGO_DB][settings.INGESTION_STATE_COLLECTION]
            pf = pq.ParquetFile(path)
            schema_names = {name.lower(): name for name in pf.schema_arrow.names}
            siren_col = schema_names.get(UPSERT_KEY)
            if siren_col is None:
                raise RuntimeError(
                    f"parquet at {path} has no '{UPSERT_KEY}' column (got {list(schema_names.values())})"
                )

            total = 0
            batch_size = settings.INGESTION_BATCH_SIZE
            for rg_idx in range(pf.num_row_groups):
                state = state_coll.find_one({"dataset_slug": dataset_slug}, {"cancel_requested": 1})
                if state and state.get("cancel_requested"):
                    state_coll.update_one(
                        {"dataset_slug": dataset_slug},
                        {"$set": {"cancel_requested": False, "status": "cancelled"}},
                    )
                    raise IngestionCancelled("ingestion cancelled by user")

                table = pf.read_row_group(rg_idx)
                rows = table.to_pylist()
                buf: list[UpdateOne] = []
                for row in rows:
                    key = row.get(siren_col)
                    if key is None:
                        continue
                    doc = {k: _coerce(v) for k, v in row.items()}
                    doc[UPSERT_KEY] = str(key)
                    buf.append(
                        UpdateOne({UPSERT_KEY: doc[UPSERT_KEY]}, {"$set": doc}, upsert=True)
                    )
                    if len(buf) >= batch_size:
                        sync_coll.bulk_write(buf, ordered=False)
                        total += len(buf)
                        buf.clear()
                if buf:
                    sync_coll.bulk_write(buf, ordered=False)
                    total += len(buf)

                logger.info(
                    "[ingest] row_group %d/%d done, total=%d",
                    rg_idx + 1,
                    pf.num_row_groups,
                    total,
                )
            return total
        finally:
            sync_client.close()


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _coerce(value: Any) -> Any:
    if hasattr(value, "isoformat") and not isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value
