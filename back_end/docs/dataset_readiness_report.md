# Dataset Readiness Report

## Purpose

This report defines the local checks used to decide whether the project data is
ready for model training. It does not download anything. It only scans local
source folders, data-lake manifests, and feature outputs.

The goal is to avoid training on a dataset that is technically present but still
partial, smoke-capped, or missing an important source family.

## Readiness Command

Final project usage should run inside Docker, where DuckDB, PyArrow, and the
other project dependencies are installed:

```bash
docker compose exec api python scripts/check_dataset_readiness.py
```

The host can also run the script from the backend project root when local
dependencies are installed:

```bash
python scripts/check_dataset_readiness.py
```

Optional JSON output:

```bash
docker compose exec api python scripts/check_dataset_readiness.py --json
```

To make a training command fail fast when the dataset is not ready:

```bash
docker compose exec api python scripts/check_dataset_readiness.py --fail-on-not-ready
```

Feature audit:

```bash
docker compose exec api python scripts/audit_feature_dataset.py
```

The checker defaults to:

| Input | Default |
|---|---|
| Data lake | `DATA_LAKE_DIR`, then `D:/PFE_volumes/data-lake`, then `/data-lake` |
| INPI source ZIPs | `INPI_LOCAL_DATA_DIR`, then `D:/PFE_volumes/source-archives/inpi`, then `/source-archives/inpi` |

## Status Meanings

| Status | Meaning | Training Decision |
|---|---|---|
| `complete` | Expected local evidence is present | Does not block training |
| `partial` | Some evidence exists, but required coverage is missing | Blocks training |
| `smoke` | Evidence is intentionally capped or API-smoke-sized | Blocks training |
| `in_progress` | A source file or export is currently unfinished | Blocks training |
| `interim` | Feature tables exist but upstream sources are incomplete | Blocks training |
| `missing` | No usable evidence was found | Blocks training |

## Current Required Sources

| Source | Required Evidence Before Training |
|---|---|
| Financials | `/data-lake/clean/financials/_manifest.json` with full clean row count |
| INPI | Four expected ZIP files and matching raw Parquet manifests |
| INSEE | Full Sirene stock extraction, not only API smoke output |
| BODACC | Historical `PCL` and `RCS-B` Parquet manifests |
| Features | Rebuilt after all upstream sources are complete |

Expected INPI source ZIP files:

```text
stock_RNE_comptes_annuels_20250926_1000_v2.zip
stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip
stock_RNE_formalites_20250523_0000.zip
stock_RNE_formalites_NIVEAU1_20260304_1400.zip
```

## Why This Matters

The project can have large feature tables even when the source coverage is not
final. For example, financial data can create many company-year rows, while
INSEE identity, INPI lifecycle events, or historical BODACC labels are still
partial. Those feature tables are useful integration evidence, but they should
be marked as `interim` and rebuilt before training.

The readiness check makes this explicit.

## Current Local Result

The latest local check returned:

| Area | Status | Meaning |
|---|---|---|
| Financials | `complete` | Clean financials exist with 6,368,964 rows |
| INPI | `in_progress` | One expected NIVEAU1 formalities ZIP is still a `.part` file |
| INSEE | `smoke` | Only 5,000 API-exported identity rows are present |
| BODACC | `partial` | Current-year labels exist, but historical `PCL` and `RCS-B` are missing |
| Features | `interim` | Feature tables exist but were built before all upstream sources were complete |

Training readiness:

```text
no
```

## Report Summary

The readiness checker is a local safety gate. It separates file integrity from
source completeness and prevents accidental model training on smoke or partial
datasets. It should be run before feature rebuilds, before model training, and
before updating final validation metrics.
