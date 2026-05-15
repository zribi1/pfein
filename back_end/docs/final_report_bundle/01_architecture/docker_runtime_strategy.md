# Docker Runtime Strategy

## Purpose

The final project should treat Docker as the runtime and the Windows host as
storage. This keeps dependency management simple and avoids requiring DuckDB,
PyArrow, scikit-learn, or other Python packages to be installed manually on the
host machine.

## Runtime Rule

Use Docker for project commands:

```bash
docker compose exec api python -m app.tools.build_company_year_features --help
docker compose exec api python scripts/check_dataset_readiness.py
docker compose exec api python scripts/audit_feature_dataset.py
```

The host machine should mainly provide mounted folders:

```text
D:/PFE_volumes/data-lake
D:/PFE_volumes/source-archives
D:/PFE_volumes/ml-artifacts
D:/PFE_volumes/mongo-data
```

## What Belongs In The Final Project

| Item | Keep In Final Project | Why |
|---|---:|---|
| `Dockerfile` | Yes | Defines the Python runtime and dependencies |
| `docker-compose.yml` | Yes | Defines services and mounted volumes |
| `requirements.txt` | Yes | Source of Python dependency versions |
| `app/` | Yes | API, services, worker, and production tools |
| `scripts/` | Yes | Operational checks and audits run inside Docker |
| `docs/` | Yes | Report and operational handover |
| Host `.venv` | No | Local convenience only |
| Host `.deps` and `.tmp` | No | Local build/cache leftovers |

## Dependency Boundary

DuckDB is required by feature and audit tooling, but it should be consumed from
the Docker image. Installing DuckDB on the host is optional and only useful for
manual debugging.

| Dependency | Final Location |
|---|---|
| DuckDB | Docker image |
| PyArrow | Docker image |
| scikit-learn | Docker image |
| MongoDB | Docker service |
| Data files | Host volume mounted into Docker |

## Operational Pattern

Use endpoints for long-running jobs when available. Use Docker commands for
read-only checks and one-off audits.

| Task | Preferred Interface |
|---|---|
| Trigger downloads or exports | FastAPI endpoint with `background=true` |
| Check dataset readiness | `docker compose exec api python scripts/check_dataset_readiness.py` |
| Audit feature tables | `docker compose exec api python scripts/audit_feature_dataset.py` |
| Train or publish through pipeline | FastAPI pipeline endpoints |
| Inspect storage manually | Host volume or Docker shell |

## Report Summary

The project should not depend on host Python packages. Docker owns execution;
host volumes own persistence. This keeps the final project reproducible and
prevents local development state from becoming part of the deployment story.
