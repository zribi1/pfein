import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import OperationFailure

from app.core.config import settings

logger = logging.getLogger(__name__)

JOB_NAME = "company_sync"
ACTIVE_STATUSES = {"starting", "running", "cancelling"}
SyncSource = Literal["all", "insee", "inpi", "bodacc"]


class CompanySyncCancelled(Exception):
    pass


class CompanySyncAlreadyRunning(Exception):
    pass


class CompanySyncService:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.state_coll = db[settings.COMPANY_SYNC_STATE_COLLECTION]
        self.company_coll = db[settings.COMPANY_COLLECTION]

    async def ensure_indexes(self) -> None:
        await self.state_coll.create_index([("job_name", ASCENDING)], unique=True)
        try:
            await self.company_coll.create_index([("siren", ASCENDING)], unique=True)
        except OperationFailure as exc:
            if exc.code != 86:
                raise

    async def run(self, source: SyncSource = "all") -> None:
        await self.ensure_indexes()
        run_id = str(uuid4())
        await self._acquire_run(run_id, source)

        try:
            active_source = source if source != "all" else "all"
            await self._update_state_owned(
                run_id,
                {
                    "status": "running",
                    "active_source": active_source,
                    "last_check_at": _utcnow(),
                },
            )
            sources = ("insee", "inpi", "bodacc") if source == "all" else (source,)
            if source == "all":
                async with asyncio.TaskGroup() as task_group:
                    for source_name in sources:
                        task_group.create_task(self._run_source_task(run_id, source_name, active_source="all"))
            else:
                await self._run_source_task(run_id, sources[0], active_source=active_source)

            await self._update_state_owned(
                run_id,
                {
                    "status": "idle",
                    "active_source": None,
                    "last_error": None,
                    "last_finished_at": _utcnow(),
                    "last_successful_run": _utcnow(),
                    "last_check_at": _utcnow(),
                },
            )
        except CompanySyncCancelled:
            logger.info("[company-sync] cancelled")
            raise
        except Exception as exc:
            await self._update_state_owned(
                run_id,
                {
                    "status": "error",
                    "last_error": str(exc),
                    "last_finished_at": _utcnow(),
                    "last_check_at": _utcnow(),
                },
            )
            logger.exception("[company-sync] run failed")
            raise
        finally:
            await self._release_run(run_id)

    async def _run_source_task(
        self,
        run_id: str,
        source: Literal["insee", "inpi", "bodacc"],
        *,
        active_source: str,
    ) -> None:
        await self._check_cancel(run_id)
        await self._update_state_owned(
            run_id,
            {
                "active_source": active_source,
                "last_check_at": _utcnow(),
            },
        )
        await self._sync_source(run_id, source)
        await self._log_source_completion(run_id, source)

    async def get_status(self) -> dict[str, Any]:
        state = await self._get_state()
        state.pop("_id", None)
        return state

    async def request_cancel(self) -> dict[str, Any]:
        state = await self._get_state()
        if state.get("status") not in ACTIVE_STATUSES:
            return {"accepted": False, "status": state.get("status", "idle")}

        await self._update_state(
            {
                "cancel_requested": True,
                "status": "cancelling",
                "last_error": None,
                "last_check_at": _utcnow(),
            }
        )
        return {"accepted": True, "status": "cancelling"}

    async def _sync_source(self, run_id: str, source: Literal["insee", "inpi", "bodacc"]) -> None:
        if source == "insee":
            await self._sync_insee(run_id)
            return
        if source == "inpi":
            await self._sync_inpi(run_id)
            return
        await self._sync_bodacc(run_id)

    async def _sync_insee(self, run_id: str) -> None:
        api_key = settings.INSEE_API_KEY.strip()
        if not api_key:
            raise ValueError("INSEE sync requires INSEE_API_KEY")

        page = 0
        cursor = "*"
        max_pages = settings.INSEE_MAX_PAGES if settings.INSEE_MAX_PAGES > 0 else 1000

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                await self._check_cancel(run_id)
                page += 1
                params: dict[str, Any] = {
                    "nombre": settings.INSEE_PAGE_SIZE,
                    "curseur": cursor,
                }
                if settings.INSEE_QUERY.strip():
                    params["q"] = settings.INSEE_QUERY.strip()

                payload = await self._request_json(
                    client,
                    "GET",
                    settings.INSEE_BASE_URL,
                    headers={
                        "X-INSEE-Api-Key-Integration": api_key,
                        "Accept": "application/json",
                    },
                    params=params,
                )

                items = extract_list(payload, ("unitesLegales",))
                await self._record_batch_progress(run_id, page, len(items))
                if not items:
                    break

                await self._upsert_companies(run_id, "insee", items)

                next_cursor = extract_insee_next_cursor(payload)
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor

                if page >= max_pages:
                    break
                await asyncio.sleep(settings.INSEE_SLEEP_SECONDS)

    async def _sync_inpi(self, run_id: str) -> None:
        username = settings.INPI_USERNAME.strip()
        password = settings.INPI_PASSWORD.strip()
        if not username or not password:
            raise ValueError("INPI sync requires INPI_USERNAME and INPI_PASSWORD")

        async with httpx.AsyncClient(timeout=30.0) as client:
            login_payload = await self._request_json(
                client,
                "POST",
                f"{settings.INPI_BASE_URL}/api/sso/login",
                headers=_inpi_headers(),
                json_body={"username": username, "password": password},
            )
            token = login_payload.get("token")
            if not token:
                raise RuntimeError("INPI login succeeded without returning a token")

            page = settings.INPI_START_PAGE
            pages_seen = 0
            total_available: int | None = None
            while True:
                await self._check_cancel(run_id)
                payload = await self._request_json(
                    client,
                    "GET",
                    f"{settings.INPI_BASE_URL}{settings.INPI_ENDPOINT}",
                    headers=_inpi_headers(str(token)),
                    params={"page": page, "per_page": settings.INPI_PER_PAGE},
                )
                if isinstance(payload, list):
                    items = payload
                else:
                    items = extract_list(payload, ("items", "results", "content", "companies", "data"))
                    total_available = extract_total_count(payload) or total_available
                await self._record_batch_progress(run_id, page, len(items))
                if not items:
                    break

                await self._upsert_companies(run_id, "inpi", items)

                if len(items) < settings.INPI_PER_PAGE:
                    break
                if total_available is not None and page * settings.INPI_PER_PAGE >= total_available:
                    break

                page += 1
                pages_seen += 1
                if settings.INPI_MAX_PAGES > 0 and pages_seen >= settings.INPI_MAX_PAGES:
                    break
                await asyncio.sleep(settings.INPI_SLEEP_SECONDS)

    async def _sync_bodacc(self, run_id: str) -> None:
        offset = 0
        page = 0
        limit = settings.BODACC_LIMIT
        total_available: int | None = None
        url = (
            f"{settings.BODACC_BASE_URL}/api/explore/{settings.BODACC_API_VERSION}"
            f"/catalog/datasets/{settings.BODACC_DATASET}/records"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                await self._check_cancel(run_id)
                page += 1
                params: dict[str, Any] = {"limit": limit, "offset": offset}
                if settings.BODACC_WHERE.strip():
                    params["where"] = settings.BODACC_WHERE.strip()

                payload = await self._request_json(
                    client,
                    "GET",
                    url,
                    params=params,
                )
                items = extract_list(payload, ("results",))
                total_available = extract_total_count(payload) or total_available
                await self._record_batch_progress(run_id, page, len(items))
                if not items:
                    break

                await self._upsert_companies(run_id, "bodacc", items)

                offset += limit
                if total_available is not None and offset >= total_available:
                    break
                if settings.BODACC_MAX_PAGES > 0 and page >= settings.BODACC_MAX_PAGES:
                    break
                await asyncio.sleep(settings.BODACC_SLEEP_SECONDS)

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = await client.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, (dict, list)):
            raise RuntimeError(f"unexpected response shape from {url}")
        return payload

    async def _upsert_companies(
        self,
        run_id: str,
        source: Literal["insee", "inpi", "bodacc"],
        items: list[Any],
    ) -> None:
        for index, item in enumerate(items, start=1):
            await self._check_cancel(run_id)
            if not isinstance(item, dict):
                continue

            doc = normalize_company_document(source, item)
            if not doc:
                continue

            result = await self.company_coll.update_one(
                {"siren": doc["siren"]},
                {
                    "$set": doc,
                    "$setOnInsert": {"created_at": _utcnow()},
                },
                upsert=True,
            )
            if result.upserted_id is not None:
                counter_name = "created"
            elif result.modified_count > 0:
                counter_name = "updated"
            else:
                counter_name = "unchanged"

            await self._increment_counters(run_id, source, counter_name)
            await self._increment_counters(run_id, source, "processed")
            await self._update_state_owned(
                run_id,
                {
                    "current_batch_progress": index,
                    "last_check_at": _utcnow(),
                },
            )

    async def _record_batch_progress(self, run_id: str, batch_number: int, batch_size: int) -> None:
        await self._update_state_owned(
            run_id,
            {
                "current_batch_number": batch_number,
                "current_batch_size": batch_size,
                "current_batch_progress": 0,
                "last_check_at": _utcnow(),
            },
        )

    async def _increment_counters(
        self,
        run_id: str,
        source: str,
        counter_name: Literal["processed", "created", "updated", "unchanged"],
    ) -> None:
        await self.state_coll.update_one(
            {"job_name": JOB_NAME, "run_id": run_id},
            {
                "$inc": {
                    counter_name: 1,
                    f"counters.{counter_name}": 1,
                    f"counters.sources.{source}.{counter_name}": 1,
                },
                "$set": {"last_check_at": _utcnow()},
            },
        )

    async def _log_source_completion(
        self,
        run_id: str,
        source: Literal["insee", "inpi", "bodacc"],
    ) -> None:
        state = await self._get_state()
        if state.get("run_id") != run_id:
            return

        source_counters = state.get("counters", {}).get("sources", {}).get(source, {})
        found = int(source_counters.get("processed", 0))
        created = int(source_counters.get("created", 0))
        updated = int(source_counters.get("updated", 0))
        unchanged = int(source_counters.get("unchanged", 0))
        stored = created + updated
        logger.info(
            "[company-sync] completed source=%s found=%s stored=%s created=%s updated=%s unchanged=%s",
            source,
            found,
            stored,
            created,
            updated,
            unchanged,
        )

    async def _get_state(self) -> dict[str, Any]:
        doc = await self.state_coll.find_one({"job_name": JOB_NAME})
        if doc is None:
            doc = {
                "job_name": JOB_NAME,
                "status": "idle",
                "run_id": None,
                "active_source": None,
                "cancel_requested": False,
                "current_batch_number": None,
                "current_batch_size": None,
                "current_batch_progress": None,
                "current_insee_offset": None,
                "last_started_at": None,
                "last_finished_at": None,
                "last_successful_run": None,
                "last_check_at": None,
                "last_error": None,
                "counters": _empty_counters(),
            }
            await self.state_coll.insert_one(doc)
        return doc

    async def _update_state(self, fields: dict[str, Any]) -> None:
        await self.state_coll.update_one(
            {"job_name": JOB_NAME},
            {"$set": fields},
            upsert=True,
        )

    async def _update_state_owned(self, run_id: str, fields: dict[str, Any]) -> None:
        result = await self.state_coll.update_one(
            {"job_name": JOB_NAME, "run_id": run_id},
            {"$set": fields},
            upsert=False,
        )
        if result.matched_count == 0:
            raise CompanySyncAlreadyRunning("company sync ownership lost")

    async def _acquire_run(self, run_id: str, source: SyncSource) -> dict[str, Any]:
        await self._get_state()
        state = await self.state_coll.find_one_and_update(
            {
                "job_name": JOB_NAME,
                "$or": [{"run_id": {"$exists": False}}, {"run_id": None}],
            },
            {
                "$set": {
                    "run_id": run_id,
                    "status": "starting",
                    "active_source": source if source != "all" else None,
                    "cancel_requested": False,
                    "last_error": None,
                    "last_started_at": _utcnow(),
                    "last_finished_at": None,
                    "last_check_at": _utcnow(),
                    "current_batch_number": None,
                    "current_batch_size": None,
                    "current_batch_progress": None,
                    "current_insee_offset": None,
                    "counters": _empty_counters(),
                },
                "$unset": {
                    "processed": "",
                    "created": "",
                    "updated": "",
                    "unchanged": "",
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if state is None:
            current = await self._get_state()
            raise CompanySyncAlreadyRunning(
                f"company sync already running with status={current.get('status', 'unknown')}"
            )
        return state

    async def _release_run(self, run_id: str) -> None:
        await self.state_coll.update_one(
            {"job_name": JOB_NAME, "run_id": run_id},
            {
                "$set": {
                    "run_id": None,
                    "active_source": None,
                    "cancel_requested": False,
                    "last_check_at": _utcnow(),
                }
            },
        )

    async def _check_cancel(self, run_id: str | None = None) -> None:
        state = await self._get_state()
        if not state.get("cancel_requested"):
            return

        fields = {
            "cancel_requested": False,
            "status": "cancelled",
            "last_finished_at": _utcnow(),
            "last_check_at": _utcnow(),
        }
        if run_id is None:
            await self._update_state(fields)
        else:
            await self._update_state_owned(run_id, fields)
        raise CompanySyncCancelled("company sync cancelled by user")


def normalize_company_document(source: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    siren = extract_siren(source, payload)
    if not siren:
        return None

    now = _utcnow()
    denomination = extract_denomination(source, payload)
    return {
        "siren": siren,
        "denomination": denomination,
        "updated_at": now,
        f"{source}_updated_at": now,
        f"{source}_raw": payload,
        "last_source": source,
    }


def extract_siren(source: str, payload: dict[str, Any]) -> str | None:
    candidates: list[Any] = []
    if source == "insee":
        candidates.extend(
            [
                get_nested_value(payload, ("siren",)),
                get_nested_value(payload, ("periodesUniteLegale", "0", "siren")),
                get_nested_value(payload, ("uniteLegale", "siren")),
            ]
        )
    elif source == "inpi":
        candidates.extend(
            [
                get_nested_value(payload, ("siren",)),
                get_nested_value(payload, ("company", "siren")),
                get_nested_value(payload, ("entreprise", "siren")),
                get_nested_value(payload, ("formality", "content", "personneMorale", "identite", "entreprise", "siren")),
                get_nested_value(payload, ("formality", "content", "personnePhysique", "identite", "entreprise", "siren")),
            ]
        )
    else:
        candidates.extend(
            [
                get_nested_value(payload, ("siren",)),
                get_nested_value(payload, ("record", "siren")),
                get_nested_value(payload, ("fields", "siren")),
                get_nested_value(payload, ("personne", "numeroImmatriculation", "numeroIdentification", "numeroSiren")),
            ]
        )

    for value in candidates:
        normalized = normalize_siren(value)
        if normalized:
            return normalized
    return None


def extract_denomination(source: str, payload: dict[str, Any]) -> str | None:
    if source == "insee":
        for path in (
            ("denominationUniteLegale",),
            ("periodesUniteLegale", "0", "denominationUniteLegale"),
            ("periodesUniteLegale", "0", "nomUniteLegale"),
        ):
            value = get_nested_value(payload, path)
            if isinstance(value, str) and value.strip():
                return value.strip()
    elif source == "inpi":
        for path in (
            ("denomination",),
            ("company", "name"),
            ("entreprise", "denomination"),
            ("formality", "content", "personneMorale", "identite", "entreprise", "denomination"),
            ("formality", "content", "personnePhysique", "identite", "entreprise", "nomCommercial"),
        ):
            value = get_nested_value(payload, path)
            if isinstance(value, str) and value.strip():
                return value.strip()
    else:
        for path in (
            ("denomination",),
            ("fields", "denomination"),
            ("fields", "nom_commercial"),
            ("record", "fields", "denomination"),
        ):
            value = get_nested_value(payload, path)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def extract_list(payload: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    list_keys = [key for key, value in payload.items() if isinstance(value, list)]
    if len(list_keys) == 1:
        return payload[list_keys[0]]
    return []


def extract_total_count(payload: dict[str, Any]) -> int | None:
    for path in (
        ("total_count",),
        ("totalCount",),
        ("total",),
        ("nbResults",),
        ("header", "total"),
        ("pagination", "total"),
        ("pagination", "total_count"),
        ("pagination", "totalCount"),
    ):
        value = get_nested_value(payload, path)
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def extract_insee_next_cursor(payload: dict[str, Any]) -> str | None:
    for path in (
        ("header", "curseurSuivant"),
        ("header", "nextCursor"),
        ("curseurSuivant",),
        ("nextCursor",),
    ):
        value = get_nested_value(payload, path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_nested_value(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for key in path:
        if isinstance(current, list):
            if not key.isdigit():
                return None
            index = int(key)
            if index >= len(current):
                return None
            current = current[index]
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_siren(value: Any) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 9:
        return None
    return digits


def _inpi_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://data.inpi.fr",
        "Referer": "https://data.inpi.fr/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _empty_counters() -> dict[str, Any]:
    return {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "sources": {},
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
