"""Centralized writer for rejected / dead-letter records.

Every ingestion pipeline (INPI, BODACC, INSEE) can use this module to
persist records that were dropped during processing — along with the
*reason* they failed and a snippet of the original payload.  This lets
operators audit exactly which companies or entries were lost and why.

Two interfaces are provided:

* **SyncRejectedRecordWriter** — for code running inside
  ``asyncio.to_thread`` (INPI file processing, BODACC archive parsing).
* **AsyncRejectedRecordWriter** — for async callers (company sync).

Both buffer writes and flush in configurable batches to minimise
per-record overhead.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection as SyncCollection

logger = logging.getLogger(__name__)

_MAX_SNIPPET_BYTES = 2048
_DEFAULT_FLUSH_SIZE = 200


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _truncate(value: Any, max_bytes: int = _MAX_SNIPPET_BYTES) -> str:
    """Return a string representation of *value*, truncated to *max_bytes*."""
    if isinstance(value, (bytes, bytearray)):
        text = value[:max_bytes].decode("utf-8", errors="replace")
    elif isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    else:
        text = str(value)
    if len(text) > max_bytes:
        return text[:max_bytes] + "…<truncated>"
    return text


class SyncRejectedRecordWriter:
    """Buffered, synchronous writer backed by a PyMongo collection.

    Typical usage inside ``asyncio.to_thread``::

        writer = SyncRejectedRecordWriter(sync_db[settings.REJECTED_RECORDS_COLLECTION])
        # ... in a loop ...
        writer.write(source="inpi", pipeline="inpi_rne_bulk", ...)
        # after the loop:
        writer.flush()
    """

    def __init__(
        self,
        collection: SyncCollection,
        *,
        flush_size: int = _DEFAULT_FLUSH_SIZE,
    ) -> None:
        self._coll = collection
        self._flush_size = flush_size
        self._buffer: list[dict[str, Any]] = []

    # -- public API -----------------------------------------------------------

    def write(
        self,
        *,
        source: str,
        pipeline: str,
        reason: str,
        error_detail: str,
        raw_snippet: Any = "",
        file_path: str | None = None,
        line_number: int | None = None,
        siren_attempt: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        doc: dict[str, Any] = {
            "source": source,
            "pipeline": pipeline,
            "reason": reason,
            "error_detail": error_detail,
            "raw_snippet": _truncate(raw_snippet),
            "file_path": file_path,
            "line_number": line_number,
            "siren_attempt": siren_attempt,
            "extra": extra or {},
            "rejected_at": _utcnow(),
        }
        self._buffer.append(doc)
        if len(self._buffer) >= self._flush_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        try:
            self._coll.insert_many(self._buffer, ordered=False)
        except Exception:
            logger.exception(
                "[rejected-records] failed to flush %d rejected records",
                len(self._buffer),
            )
        finally:
            self._buffer.clear()

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)


class AsyncRejectedRecordWriter:
    """Async writer backed by a Motor collection.

    Typical usage::

        writer = AsyncRejectedRecordWriter(db[settings.REJECTED_RECORDS_COLLECTION])
        await writer.write(source="insee", pipeline="insee_bulk", ...)
        await writer.flush()
    """

    def __init__(
        self,
        collection: Any,
        *,
        flush_size: int = _DEFAULT_FLUSH_SIZE,
    ) -> None:
        self._coll = collection
        self._flush_size = flush_size
        self._buffer: list[dict[str, Any]] = []

    async def write(
        self,
        *,
        source: str,
        pipeline: str,
        reason: str,
        error_detail: str,
        raw_snippet: Any = "",
        file_path: str | None = None,
        line_number: int | None = None,
        siren_attempt: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        doc: dict[str, Any] = {
            "source": source,
            "pipeline": pipeline,
            "reason": reason,
            "error_detail": error_detail,
            "raw_snippet": _truncate(raw_snippet),
            "file_path": file_path,
            "line_number": line_number,
            "siren_attempt": siren_attempt,
            "extra": extra or {},
            "rejected_at": _utcnow(),
        }
        self._buffer.append(doc)
        if len(self._buffer) >= self._flush_size:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return
        try:
            await self._coll.insert_many(self._buffer, ordered=False)
        except Exception:
            logger.exception(
                "[rejected-records] failed to flush %d rejected records",
                len(self._buffer),
            )
        finally:
            self._buffer.clear()

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)
