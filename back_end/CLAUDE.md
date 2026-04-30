# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

FastAPI + Motor (async MongoDB) + APScheduler (`AsyncIOScheduler`) + a joblib-backed ML registry. Python 3.12. Paired with an Angular frontend at `../pfefm-angular` that consumes `/api/v1/*`.

## Commands

```bash
# Dev stack (api + mongo)
cp .env.example .env
docker compose up --build

# Include mongo-express UI on :8081
docker compose --profile dev up

# Rebuild just the api image
docker compose build api
docker compose up -d api

# Tail logs
docker compose logs -f api
docker compose logs -f worker

# Manually trigger INPI RNE bulk ingestion (FTP/SFTP)
curl -X POST "http://localhost:8000/api/v1/ingestion/inpi/run"
curl -X POST "http://localhost:8000/api/v1/ingestion/inpi/run?force=true"
curl     "http://localhost:8000/api/v1/ingestion/inpi/status"
curl -X POST "http://localhost:8000/api/v1/ingestion/inpi/cancel"
```

Local (outside Docker):

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows bash
pip install -r requirements.txt
# .env must set MONGO_URI=mongodb://localhost:27017 when running locally
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs: `http://localhost:8000/docs` · health: `/api/v1/health` · DB ping: `/api/v1/health/db`.

No test suite, linter, or formatter is configured yet. If adding one, wire it into `requirements.txt` and surface the command here.

## Architecture

**Two processes, one codebase: API and worker.** The API container runs `uvicorn app.main:app` and only handles HTTP. The `worker` container runs `python -m app.worker` ([app/worker.py](app/worker.py)) and owns all background work — APScheduler lives there, not in the API process. Both processes share the same lifespan order on startup (`setup_logging()` → `mongodb.connect()` → `ml_registry.load()`, plus `scheduler.start()` in the worker only) and the reverse on shutdown. New subsystems plug in at this lifespan boundary in whichever process needs them, not at import time. CPU-bound work (e.g. bulk ML inference) belongs in the worker so it can't degrade API latency.

**Singletons imported from modules, not passed through DI.** `mongodb`, `ml_registry`, and `scheduler` are module-level instances in [app/db/mongodb.py](app/db/mongodb.py), [app/ml/loader.py](app/ml/loader.py), and [app/scheduler/scheduler.py](app/scheduler/scheduler.py). Endpoints reach them via thin `Depends()` shims in [app/api/deps.py](app/api/deps.py). Don't construct a second client/registry/scheduler — reuse the shared instance.

**Versioned API aggregation.** All routers live under [app/api/v1/endpoints/](app/api/v1/endpoints/) and are mounted into a single `api_router` in [app/api/v1/router.py](app/api/v1/router.py), which is in turn mounted at `settings.API_V1_PREFIX` (`/api/v1`). New endpoints: create a module in `endpoints/`, then `include_router(...)` it in `router.py` with a prefix and tags. Don't attach routers directly to `app`.

**Layering: endpoint → service → (ml_registry | db).** Endpoints are HTTP glue only — they validate with pydantic schemas from `app/schemas/` and delegate to a service class in `app/services/`. Services call `ml_registry.get(...)` for inference and/or receive a Motor DB via `Depends(mongo_db)`. Keep Motor queries and model calls out of endpoint functions.

**ML artifacts are runtime state, not image content.** [app/ml/artifacts/](app/ml/artifacts/) is mounted read-only from the host in [docker-compose.yml](docker-compose.yml) (`./app/ml/artifacts:/app/app/ml/artifacts:ro`) and `.gitignore`d except for `.gitkeep`. `MLRegistry.load()` logs a warning and returns when `model.joblib` is absent — the API still boots. To swap models in prod, replace the file and restart; no rebuild needed. Retraining jobs writing new artifacts must target this path and the volume mount must not be `:ro` in that deployment.

**Scheduler jobs are declared in `scheduler.py`, defined in `jobs.py`.** [app/scheduler/scheduler.py](app/scheduler/scheduler.py) registers `scheduler.add_job(...)` calls at import time. Job bodies live in [app/scheduler/jobs.py](app/scheduler/jobs.py) as `async def` functions and delegate to a service class in `app/services/` — same layering as endpoints. The scheduler instance is started by the worker, not the API. The `_ = jobs` line keeps the jobs module imported even when every schedule is commented out.

**INPI RNE bulk ingestion (FTP/SFTP).** The daily `ingest_inpi_rne_bulk` job ([app/services/inpi_ingestion_service.py](app/services/inpi_ingestion_service.py)) walks an INPI FTP/SFTP tree, mirrors files locally under `INPI_LOCAL_DATA_DIR` (mounted at `/app/data/inpi` on the worker only), and upserts entreprise records into `rne_companies` keyed on `siren`. State is split: `ingestion_state` holds the run-level doc (slug `inpi_rne_bulk`, same shape as the parquet job), and `inpi_rne_files` holds one doc per remote path with statuses `pending → downloading → downloaded → processing → done | failed`. Files are skipped on subsequent runs when `(remote_size, remote_mtime)` match the stored values. Downloads stream into a `.part` file and are renamed only on successful completion; remote size is verified before processing. Heavy IO (FTP I/O, gzip/zip parsing, `bulk_write`) runs inside `asyncio.to_thread`. Protocol switches between FTP (`ftplib`) and SFTP (`paramiko`) via `INPI_FTP_PROTOCOL`. Credentials live only in `.env` and are never logged.

**Ingestion job → state collection → resumable.** The daily `ingest_entreprises_parquet` job ([app/services/ingestion_service.py](app/services/ingestion_service.py)) is state-driven via the `ingestion_state` Mongo collection (one doc per `dataset_slug` tracking `last_remote_update`, `current_file_path`, `status`). Flow: resume any pending file on disk first → check data.gouv.fr `last_update` → skip if not newer → stream-download to `INGESTION_DATA_DIR` → ingest the parquet by row group with `bulk_write` upserts keyed on `siren` into `donnees_financieres_entreprises` → delete the file. The parquet feed is cumulative, so upsert-by-SIREN makes re-ingestion idempotent and crash-safe. Parquet is read with pyarrow inside `asyncio.to_thread` so the event loop stays free. The data file lives in the `ingestion-data` named volume mounted only on the worker; API has no need for it.

**Config through pydantic-settings.** [app/core/config.py](app/core/config.py) defines `Settings`, cached via `@lru_cache`, with defaults suitable for the Docker network (`MONGO_URI=mongodb://mongo:27017`). `CORS_ORIGINS` is parsed as a JSON list from env (e.g. `CORS_ORIGINS=["http://localhost:4200"]`), not a comma-separated string — the `[...]` brackets in `.env` are required.

**Docker image is multi-stage and non-root.** [Dockerfile](Dockerfile) builds a venv in a `builder` stage and copies `/opt/venv` into a slim `runtime` stage that runs as user `app`. The `HEALTHCHECK` hits `/api/v1/health`, so changing `API_V1_PREFIX` or the health route breaks container health reporting — update both.

## Domain context

Backend for a French company-health prediction product. Shared vocabulary with the frontend (see `../pfefm-angular/src/app/core/models/`): `Entreprise` (SIREN-identified company with risk/score fields), `CompanyPrediction` (model output: `prediction_modele` 0/1, `probabilite_cessation`, `confiance`), chatbot with RAG modes. Response schemas in `app/schemas/` must stay field-compatible with the Angular interfaces.
