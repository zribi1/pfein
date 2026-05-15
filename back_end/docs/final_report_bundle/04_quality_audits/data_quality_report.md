# Data Quality And Reproducibility Report

## Purpose

This report defines the quality checks that should be applied to the data-lake
exports and serving collections. Some sources now have full or large interim
evidence, but final model-quality evidence still depends on completing INPI,
INSEE, and historical BODACC coverage.

## Datasets To Check

| Source | Raw Dataset | Clean Dataset | Feature Dataset |
|---|---|---|---|
| INSEE | `/data-lake/raw/insee` | `/data-lake/clean/company_identity`, `/data-lake/clean/establishments` | Company identity features |
| INPI | `/data-lake/raw/inpi` | `/data-lake/clean/annual_accounts`, `/data-lake/clean/formalities_events` | Filing and registry features |
| BODACC | `/data-lake/raw/bodacc` | `/data-lake/clean/legal_events` | Legal event features |
| Financials | `/data-lake/raw/financials` | `/data-lake/clean/financials` | Financial features |
| ML | Not applicable | Not applicable | `/data-lake/features/company_year_features`, `/data-lake/features/risk_labels` |

## Required Checks

| Check | Purpose |
|---|---|
| Manifest exists | Confirms the export records rows, parts, source path, and timestamp |
| Progress file done | Confirms long exports finished cleanly |
| Row count is non-zero | Detects empty or failed exports |
| Required columns exist | Confirms downstream tools can read the dataset |
| SIREN format is valid | Protects joins between sources |
| Duplicate key rate is measured | Detects raw or clean grain problems |
| Date fields parse correctly | Protects chronology and leakage control |
| Source lineage exists | Preserves reproducibility |

## Source-Specific Checks

### INSEE

| Check | Expected Rule |
|---|---|
| `siren` length | Nine digits |
| `etat_administratif` values | Known active/closed status codes |
| `date_creation` parse rate | High enough for company-age features |
| Bulk dataset type | Correctly detected as unit, establishment, historical, or succession file |

### INPI

| Check | Expected Rule |
|---|---|
| `record_key` uniqueness | Unique within exported raw files |
| `category` values | `comptes_annuels` or `formalites` |
| `niveau` values | `standard` or `niveau1` |
| Account dates | `date_depot` and `date_cloture` parseable when present |

### BODACC

| Check | Expected Rule |
|---|---|
| `record_key` or `nojo` uniqueness | Unique announcement key |
| `event_date` coverage | Available or recoverable from `date_parution` |
| `bodacc_family` values | `RCS_A`, `RCS_B`, `PCL`, or `BILAN` |
| Risk flags | Consistent with `event_category` and `event_type` |

### Financials

| Check | Expected Rule |
|---|---|
| Grain | Prefer `(siren, financial_year)` |
| Numeric fields | Revenue, result, equity, and debt parse as numbers when present |
| Year fields | `financial_year` or `closing_date` exists |
| Future data handling | Values after prediction cutoff are excluded from features |

## Reproducibility Evidence

Each major export should keep:

```text
_manifest.json
_progress.json
source archive or source URL
row count
part count
export timestamp
```

Original source archives or source Parquet files should remain available so raw
and clean datasets can be regenerated after parser improvements.

## Local Readiness Check

A read-only readiness checker exists for local validation:

```bash
docker compose exec api python scripts/check_dataset_readiness.py
```

It reports whether each source is `complete`, `partial`, `smoke`,
`in_progress`, `interim`, or `missing`. This check is separate from row-level
quality: it answers whether the expected source coverage exists before feature
rebuilds and model training.

The feature table can be audited with:

```bash
docker compose exec api python scripts/audit_feature_dataset.py
```

This should be run inside Docker for the final project because DuckDB and
PyArrow are container dependencies, not host requirements.

## Current Status

| Area | Status |
|---|---|
| Raw exporters | INPI, BODACC, INSEE API, INSEE bulk, and financial data-lake exporters exist |
| Pipeline API | Endpoints exist for financial clean build, feature build, model training, prediction publishing, and job status |
| Feature builder | Company-year feature and label builder exists and has produced interim 2017-2025 outputs |
| Financial data lake | Full source Parquet downloaded and clean financial table built |
| Clean layers | Partly conceptual and should be finalized per source |
| Evidence tables | Financial full clean evidence recorded; INPI full export in progress; INSEE and historical BODACC still partial |

## Smoke-Test Evidence

The first smoke run was executed on 2026-05-02 with the Docker stack running
locally.

### Runtime Health

| Check | Result |
|---|---|
| API container | `pfein-api` running and healthy |
| Worker container | `pfein-worker` running |
| MongoDB container | `pfein-mongo` running and healthy |
| API health | `GET /api/v1/health` returned `ok` |
| DB health | `GET /api/v1/health/db` returned database `pfein` |
| Data lake mount | `/data-lake` mounted inside the container |

### BODACC Raw Parquet Smoke Export

Command:

```bash
python -m app.tools.bodacc_to_parquet \
  --input /source-archives/bodacc/current/OPENDATA/BODACC/FluxAnneeCourante/BILAN_BXC20260001.taz \
  --mode current \
  --year 2026 \
  --batch-size 500 \
  --max-records 1000
```

Output:

```text
/data-lake/raw/bodacc/current/2026/BILAN_BXC20260001
```

Evidence:

| Metric | Value |
|---|---|
| Exported rows | 1,000 |
| Parquet parts | 2 |
| Archive members | 1 |
| Parse errors | 0 |
| Progress status | `done=true` |
| Distinct SIRENs | 937 |
| Missing SIRENs | 0 |
| Event classification | `BILAN / comptes_annuels / depot_comptes` |

### Feature Builder Smoke Run

Command:

```bash
python -m app.tools.build_company_year_features \
  --start-year 2025 \
  --end-year 2025 \
  --max-companies 5000 \
  --overwrite
```

Output evidence:

| Dataset | Rows | Source Roots |
|---|---:|---|
| `/data-lake/features/company_year_features` | 3,132 | BODACC raw smoke exports |
| `/data-lake/features/risk_labels` | 3,132 | BODACC raw smoke exports |
| `/data-lake/features/company_features` | 3,132 | Latest prediction-year features |

Label balance:

| Label | Positive Count |
|---|---:|
| `continuity_risk_12m_label` | 683 |
| `legal_distress_risk_12m_label` | 190 |
| `radiation_risk_12m_label` | 493 |

The latest smoke input includes one BILAN archive, one PCL archive, and one
RCS-B archive. It validates BODACC label generation, but it does not provide
enough historical or source diversity for model training.

### BODACC Label-Source Smoke Export

Evidence:

| Archive | Rows | Important Signals |
|---|---:|---|
| `PCL_BXA20260024.taz` | 315 | 259 risk events, 175 liquidation flags, 34 redressement flags, 16 sauvegarde flags |
| `RCS-B_BXB20260003.taz` | 1,920 | 924 radiation events |

## Current Larger Evidence

The smoke evidence above proves the mechanics. Later runs have produced larger
interim outputs, but they should still be treated as pre-training evidence until
all source coverage is complete.

| Dataset | Evidence | Status |
|---|---|---|
| Financial raw source | `/data-lake/raw/financials/data_gouv_export_detail_bilan_20260210/export-detail-bilan.parquet`, 2,820,473,022 bytes | Complete |
| Financial clean table | `/data-lake/clean/financials/financials.parquet`, 6,368,964 rows | Complete |
| Company-year features | `/data-lake/features/company_year_features`, 17,078,580 rows for 2017-2025 | Interim, rebuild required |
| Risk labels | `/data-lake/features/risk_labels`, 17,078,580 rows for 2017-2025 | Interim, rebuild required |
| Latest company features | `/data-lake/features/company_features`, 1,897,620 rows | Interim, rebuild required |
| INPI source coverage | Three ZIPs present; `stock_RNE_formalites_NIVEAU1_20260304_1400.zip` downloading as `.zip.part` | In progress |
| INPI Parquet export | Full export is running for currently available ZIP files; progress files update during chunk writing | In progress |

## Limitations And Future Improvements

| Current Limitation | Future Improvement |
|---|---|
| INSEE evidence is still a 5,000-row API smoke export | Add full Sirene stock extraction and clean identity snapshots |
| BODACC evidence is still current-year oriented | Add historical `PCL` and `RCS-B` archives |
| INPI full coverage is still running | Finish missing NIVEAU1 formalities download and rerun full export for all four ZIP files |
| Clean layers are not fully implemented | Add checks after each clean builder is created |
| Mongo serving collections are not final | Add serving-document validation once builders exist |
| Data-quality checks are manual | Add a CLI command that writes a quality report automatically |

## Report Summary

The data-quality report defines the checks needed to prove that the project data
is reproducible, joinable, and safe for ML. Financials now have full clean
evidence, and large interim feature tables exist. Final quality approval still
requires full INPI, full INSEE identity, historical BODACC labels, and measured
checks on the rebuilt feature and label datasets.
