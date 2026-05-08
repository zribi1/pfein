import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.tools.build_clean_core_sources import build_clean_core_sources
from app.tools.build_clean_financials import build_clean_financials
from app.tools.build_company_year_features import build_company_year_datasets
from app.tools.publish_prediction_results import publish_predictions
from app.tools.train_continuity_model import DEFAULT_TARGET, train_model

logger = logging.getLogger(__name__)

router = APIRouter()

_TASKS: dict[str, asyncio.Task[None]] = {}


class PipelineRunResponse(BaseModel):
    accepted: bool
    job: str
    status: str
    log_file: str


class PipelineStatusResponse(BaseModel):
    job: str
    status: str
    running: bool
    log_file: str
    log_tail: list[str] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None


@router.post(
    "/sources/clean/run",
    response_model=PipelineRunResponse,
    summary="Build clean INSEE, INPI, and BODACC datasets",
    description=(
        "Compacts raw source-oriented INSEE, INPI, and BODACC Parquet exports into grouped clean datasets under "
        "`/data-lake/clean/company_identity`, `/data-lake/clean/legal_events`, "
        "`/data-lake/clean/formalities_events`, and `/data-lake/clean/annual_accounts`."
    ),
)
async def run_clean_core_sources(
    background_tasks: BackgroundTasks,
    overwrite: bool = Query(default=True),
    max_rows: int | None = Query(default=None, ge=1),
) -> PipelineRunResponse:
    return _start_job(
        background_tasks,
        "clean_core_sources",
        lambda: build_clean_core_sources(
            data_lake_dir=Path(settings.DATA_LAKE_DIR),
            overwrite=overwrite,
            max_rows=max_rows,
        ),
    )


@router.post(
    "/financials/clean/run",
    response_model=PipelineRunResponse,
    summary="Build clean financials",
    description=(
        "Normalizes raw financial Parquet files from `/data-lake/raw/financials` into "
        "`/data-lake/clean/financials`. Existing clean output is replaced when `overwrite=true`."
    ),
)
async def run_clean_financials(
    background_tasks: BackgroundTasks,
    overwrite: bool = Query(default=True),
    max_rows: int | None = Query(default=None, ge=1),
) -> PipelineRunResponse:
    return _start_job(
        background_tasks,
        "clean_financials",
        lambda: build_clean_financials(
            data_lake_dir=Path(settings.DATA_LAKE_DIR),
            overwrite=overwrite,
            max_rows=max_rows,
        ),
    )


@router.post(
    "/features/build/run",
    response_model=PipelineRunResponse,
    summary="Build company-year features and labels",
    description=(
        "Builds `/data-lake/features/company_year_features`, `/data-lake/features/risk_labels`, "
        "and `/data-lake/features/company_features` from the raw/clean data lake sources."
    ),
)
async def run_feature_build(
    background_tasks: BackgroundTasks,
    start_year: int = Query(default=2017, ge=1900, le=2100),
    end_year: int = Query(default=datetime.now(tz=timezone.utc).year - 1, ge=1900, le=2100),
    max_companies: int | None = Query(default=None, ge=1),
    overwrite: bool = Query(default=True),
) -> PipelineRunResponse:
    return _start_job(
        background_tasks,
        "build_company_year_features",
        lambda: build_company_year_datasets(
            data_lake_dir=Path(settings.DATA_LAKE_DIR),
            start_year=start_year,
            end_year=end_year,
            max_companies=max_companies,
            overwrite=overwrite,
        ),
    )


@router.post(
    "/model/train/run",
    response_model=PipelineRunResponse,
    summary="Train continuity-risk model",
    description="Trains the continuity-risk model from feature and label Parquet datasets.",
)
async def run_model_training(
    background_tasks: BackgroundTasks,
    target: str = Query(default=DEFAULT_TARGET),
    min_rows: int = Query(default=1000, ge=1),
    max_rows: int | None = Query(default=None, ge=1),
) -> PipelineRunResponse:
    return _start_job(
        background_tasks,
        "train_continuity_model",
        lambda: train_model(
            data_lake_dir=Path(settings.DATA_LAKE_DIR),
            artifacts_dir=Path(settings.ML_ARTIFACTS_DIR),
            model_file=settings.ML_MODEL_FILE,
            target=target,
            min_rows=min_rows,
            max_rows=max_rows,
        ),
    )


@router.post(
    "/predictions/publish/run",
    response_model=PipelineRunResponse,
    summary="Publish prediction results",
    description="Scores latest company features and upserts prediction documents into MongoDB.",
)
async def run_prediction_publish(
    background_tasks: BackgroundTasks,
    limit: int | None = Query(default=None, ge=1),
    batch_size: int = Query(default=1000, ge=1),
) -> PipelineRunResponse:
    return _start_job(
        background_tasks,
        "publish_prediction_results",
        lambda: publish_predictions(
            data_lake_dir=Path(settings.DATA_LAKE_DIR),
            artifacts_dir=Path(settings.ML_ARTIFACTS_DIR),
            model_file=settings.ML_MODEL_FILE,
            mongo_uri=settings.MONGO_URI,
            mongo_db=settings.MONGO_DB,
            collection=settings.PREDICTION_RESULTS_COLLECTION,
            limit=limit,
            batch_size=batch_size,
        ),
    )


@router.get(
    "/status/{job}",
    response_model=PipelineStatusResponse,
    summary="Get pipeline job status",
    description="Returns in-process status, latest log lines, and known output manifests for a pipeline job.",
)
async def get_pipeline_status(job: str) -> PipelineStatusResponse:
    if job not in _known_jobs():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown pipeline job: {job}")
    return _status(job)


def _start_job(
    background_tasks: BackgroundTasks,
    job: str,
    func: Callable[[], Any],
) -> PipelineRunResponse:
    existing = _TASKS.get(job)
    if existing and not existing.done():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{job} is already running")

    log_file = _log_file(job)
    _write_log(job, "starting")
    background_tasks.add_task(_run_background, job, func)
    return PipelineRunResponse(accepted=True, job=job, status="starting", log_file=str(log_file))


async def _run_background(job: str, func: Callable[[], Any]) -> None:
    task = asyncio.current_task()
    if task is not None:
        _TASKS[job] = task
    _write_state(job, {"status": "running", "started_at": _now(), "finished_at": None, "last_error": None})
    try:
        await asyncio.to_thread(func)
    except Exception as exc:
        logger.exception("[pipeline] job failed job=%s", job)
        _write_log(job, f"failed: {exc!r}")
        _write_state(job, {"status": "failed", "finished_at": _now(), "last_error": str(exc)})
        return
    _write_log(job, "done")
    _write_state(job, {"status": "done", "finished_at": _now(), "last_error": None})


def _status(job: str) -> PipelineStatusResponse:
    task = _TASKS.get(job)
    running = bool(task and not task.done())
    state = _read_state(job)
    outputs = _outputs_for(job)
    if running:
        current_status = "running"
    else:
        current_status = str(state.get("status") or _status_from_outputs(outputs))
    return PipelineStatusResponse(
        job=job,
        status=current_status,
        running=running,
        log_file=str(_log_file(job)),
        log_tail=_tail(_log_file(job)),
        outputs=outputs,
        started_at=_parse_dt(state.get("started_at")),
        finished_at=_parse_dt(state.get("finished_at")),
        last_error=state.get("last_error"),
    )


def _known_jobs() -> set[str]:
    return {
        "clean_core_sources",
        "clean_financials",
        "build_company_year_features",
        "train_continuity_model",
        "publish_prediction_results",
    }


def _log_file(job: str) -> Path:
    return Path(settings.DATA_LAKE_DIR) / "logs" / f"{job}.log"


def _state_file(job: str) -> Path:
    return Path(settings.DATA_LAKE_DIR) / "logs" / f"{job}.state.json"


def _write_log(job: str, message: str) -> None:
    path = _log_file(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{_now()} | {job} | {message}\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _write_state(job: str, update: dict[str, Any]) -> None:
    state = {**_read_state(job), **update}
    path = _state_file(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json_dumps(state), encoding="utf-8")
    tmp.replace(path)


def _read_state(job: str) -> dict[str, Any]:
    path = _state_file(job)
    if not path.exists():
        return {}
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tail(path: Path, lines: int = 80) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except Exception as exc:
        return [f"failed reading log: {exc}"]


def _outputs_for(job: str) -> dict[str, Any]:
    data_lake = Path(settings.DATA_LAKE_DIR)
    if job == "clean_core_sources":
        return {
            "company_identity": _read_json(data_lake / "clean" / "company_identity" / "_manifest.json"),
            "legal_events": _read_json(data_lake / "clean" / "legal_events" / "_manifest.json"),
            "formalities_events": _read_json(data_lake / "clean" / "formalities_events" / "_manifest.json"),
            "annual_accounts": _read_json(data_lake / "clean" / "annual_accounts" / "_manifest.json"),
        }
    if job == "clean_financials":
        return {"manifest": _read_json(data_lake / "clean" / "financials" / "_manifest.json")}
    if job == "build_company_year_features":
        return {
            "company_year_features": _read_json(data_lake / "features" / "company_year_features" / "_manifest.json"),
            "risk_labels": _read_json(data_lake / "features" / "risk_labels" / "_manifest.json"),
            "company_features": _read_json(data_lake / "features" / "company_features" / "_manifest.json"),
        }
    if job == "train_continuity_model":
        return {"metadata": _read_json(Path(settings.ML_ARTIFACTS_DIR) / "model_metadata.json")}
    if job == "publish_prediction_results":
        return {}
    return {}


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc), "path": str(path)}


def _status_from_outputs(outputs: dict[str, Any]) -> str:
    if not outputs:
        return "unknown"
    if all(value is not None for value in outputs.values()):
        return "done"
    if any(value is not None for value in outputs.values()):
        return "partial"
    return "unknown"


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None
