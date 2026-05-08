# Incremental Data Collection Checklist

## Rule

Work one step at a time. Do not start the next step until the current step has
clear evidence:

```text
command run
output path
row count
manifest/progress file
basic quality check
decision: complete / blocked / retry
```

Training remains on hold until the dataset contains enough positive labels.

## Current Position

| Area | Status | Evidence |
|---|---|---|
| Docker stack | Complete | API, worker, and MongoDB are running; `/api/v1/health` and `/api/v1/health/db` return `ok` |
| Data lake mount | Complete | `/data-lake` is mounted in the container and writes to `D:/PFE_volumes/data-lake` |
| BODACC smoke export | Complete | 1,000 rows exported from `BILAN_BXC20260001.taz` to `/data-lake/raw/bodacc/current/2026/BILAN_BXC20260001` |
| Label-source BODACC export | Complete | `PCL_BXA20260024.taz` and `RCS-B_BXB20260003.taz` exported to Parquet |
| INSEE identity smoke export | Complete | 5,000 rows exported to `/data-lake/raw/insee/unites_legales/step3_identity_smoke_20260503` |
| INPI annual accounts smoke export | Complete | 5,000 rows exported to `/data-lake/raw/inpi/comptes_annuels/standard/stock_RNE_comptes_annuels_20250926_1000_v2` |
| INPI formalities smoke export | Complete | 5,000 rows exported from official ZIP to `/data-lake/raw/inpi/formalites/standard/stock_RNE_formalites_20250523_0000` |
| Financial full clean build | Complete | 2.82 GB source Parquet downloaded to `/data-lake/raw/financials/data_gouv_export_detail_bilan_20260210`; 6,368,964 clean rows built in `/data-lake/clean/financials` |
| Multi-year feature build | Complete with partial non-financial sources | 17,078,580 company-year feature rows and 17,078,580 label rows created for 2017-2025 |
| INPI full source coverage | In progress | Missing `stock_RNE_formalites_NIVEAU1_20260304_1400.zip` is downloading; partial file was 2.2 GB of 15.1 GB on 2026-05-03 23:10 |
| INPI full Parquet export | In progress | Full export for `stock_RNE_comptes_annuels_20250926_1000_v2.zip` reached 3,100,000 rows and 31 parts; `done=false` |
| Training | On hold | Positive labels now exist, but source coverage is still too narrow for a real model |

## Checklist

### Step 0: Environment And Smoke Test

Status: Complete.

Evidence:

| Check | Result |
|---|---|
| Backend compile | Passed |
| API health | Passed |
| Mongo health | Passed |
| BODACC Parquet smoke export | Passed |
| Feature builder smoke run | Passed |

Decision:

```text
Complete. Do not train yet.
```

### Step 1: Build A Source Inventory

Status: Complete.

Goal:

Create a local inventory of available source files and identify what is missing
for model labels.

Required evidence:

| Source | Required Evidence |
|---|---|
| BODACC | Count archives by family/year: `BILAN`, `PCL`, `RCS_A`, `RCS_B` |
| INPI | List downloaded ZIP files by family: `comptes_annuels`, `formalites` |
| INSEE | Confirm whether bulk stock files or API credentials are available |
| Financials | Confirm whether source Parquet exists locally |

Evidence updated on 2026-05-04:

| Source | Local Evidence | Decision |
|---|---|---|
| BODACC source archives | Current-year `PCL` and `RCS-B` archives are present under `/source-archives/bodacc/current`; historical local source currently includes BILAN archives under `/source-archives/bodacc/OPENDATA/BODACC/FluxHistorique` | Current labels exist, but historical `PCL` and `RCS-B` coverage is still missing |
| INPI source archives | Three ZIPs are present under `/source-archives/inpi`; missing `stock_RNE_formalites_NIVEAU1_20260304_1400.zip` is downloading as `.zip.part` | Wait for download, then rerun full Parquet export for all four ZIPs |
| Main data lake | `/data-lake` contains full financial clean data and multi-year feature outputs; INPI/INSEE/BODACC are still partial | Keep current feature outputs as interim evidence, but rebuild after full source extraction |
| Older ingestion lake | Removed during cleanup; active data-lake path is `/data-lake` | No longer part of the active architecture |
| INSEE | `/data-lake/raw/insee/unites_legales/step3_identity_smoke_20260503`, 5,000 rows | Full INSEE identity source still missing |
| Financials | `/data-lake/clean/financials`, 6,368,964 rows | Complete enough for current ML features |

Completion rule:

```text
Complete. We know what exists locally and what must still be collected.
```

Missing before dataset build:

| Priority | Missing Data | Why It Matters |
|---|---|---|
| 1 | Complete INPI NIVEAU1 formalities ZIP download and full INPI Parquet export | Needed for full registry lifecycle and filing features |
| 2 | Full INSEE Sirene stock | Needed for complete company identity, status, activity, and legal category |
| 3 | Historical BODACC `PCL` archives | Needed for historical collective-procedure and legal-distress labels |
| 4 | Historical BODACC `RCS-B` archives | Needed for historical closure/radiation labels |

### Step 2: Collect Label-Producing Legal Events

Status: Complete for proof export.

Goal:

Prioritize BODACC `PCL` and `RCS_B` archives because they produce distress and
radiation labels. Do not process thousands of `BILAN` files first.

Required evidence:

| Check | Required Result |
|---|---|
| At least one PCL archive exported to Parquet | Manifest exists, row count > 0 |
| At least one RCS_B archive exported to Parquet | Manifest exists, row count > 0 |
| Risk labels present | Positive `legal_distress_risk_12m_label` or `radiation_risk_12m_label` exists after feature build |

Evidence found on 2026-05-02:

| Check | Result |
|---|---|
| PCL source archive | `D:/PFE_volumes/source-archives/bodacc/current/OPENDATA/BODACC/FluxAnneeCourante/PCL_BXA20260024.taz`, 0.53 MB |
| RCS-B source archive | `D:/PFE_volumes/source-archives/bodacc/current/OPENDATA/BODACC/FluxAnneeCourante/RCS-B_BXB20260003.taz`, 2.90 MB |
| PCL Parquet output | `/data-lake/raw/bodacc/current/2026/PCL_BXA20260024`, 315 rows |
| RCS-B Parquet output | `/data-lake/raw/bodacc/current/2026/RCS-B_BXB20260003`, 1,920 rows |
| Label-source init endpoint | `POST /api/v1/ingestion/bodacc/label-export/run` downloads, validates, and exports current-year `PCL` and `RCS-B` archives |
| PCL risk events | 259 risk events, including 175 liquidation flags, 34 redressement flags, and 16 sauvegarde flags |
| RCS-B radiation events | 924 radiation events |
| Rebuilt 2025 label table | 3,132 rows in `/data-lake/features/risk_labels` |
| Positive labels | 683 `continuity_risk_12m_label`, 190 `legal_distress_risk_12m_label`, 493 `radiation_risk_12m_label` |

Decision:

```text
Complete for parser/export proof. Do not train yet. Scale Step 2 later by
collecting all relevant PCL and RCS-B archives across the target history.
```

### Step 3: Add Identity Backbone

Status: Complete for API smoke export.

Goal:

Add INSEE identity data so companies have names, activity codes, legal
categories, creation dates, and administrative status.

Required evidence:

| Check | Required Result |
|---|---|
| INSEE raw Parquet exists | `/data-lake/raw/insee/...` |
| SIREN validity | Nine-digit SIRENs in sample |
| Feature builder uses INSEE source | `company_identity` source root is not null in manifest |

Evidence found on 2026-05-03:

| Check | Result |
|---|---|
| INSEE bulk endpoint | `POST /api/v1/ingestion/insee/bulk/run` added for portable bulk initialization |
| INSEE raw Parquet | `/data-lake/raw/insee/unites_legales/step3_identity_smoke_20260503`, 5,000 rows |
| SIREN validity | 5,000 / 5,000 rows have valid nine-digit SIRENs; 5,000 distinct SIRENs |
| Feature builder smoke | 5,000 company-year rows and 5,000 label rows built for prediction year 2025 |
| Feature source root | `company_identity` is `/data-lake/raw/insee/unites_legales` in feature and label manifests |

Decision:

```text
Complete for API smoke export. Full-history production still needs INSEE Sirene
bulk stock files or a larger controlled API export.
```

### Step 4: Add INPI Filing And Formality Data

Status: Full export in progress.

Goal:

Add INPI annual accounts and formalities to capture filing behavior and
cessation/radiation formalities.

Required evidence:

| Check | Required Result |
|---|---|
| INPI accounts exported | `/data-lake/raw/inpi/comptes_annuels/...` |
| INPI formalities exported if available | `/data-lake/raw/inpi/formalites/...` |
| Feature builder uses INPI sources | Annual account or formalities source roots are not null |

Evidence found on 2026-05-03:

| Check | Result |
|---|---|
| Swagger grouping | `/docs` now separates endpoints into `Health`, `Predictions`, `INPI`, `INSEE`, and `BODACC` sections |
| INPI local file discovery | `GET /api/v1/ingestion/inpi/local-files` found one local ZIP: `/source-archives/inpi/stock_RNE_comptes_annuels_20250926_1000_v2.zip` |
| INPI Parquet export endpoint | `POST /api/v1/ingestion/inpi/parquet-export/run` added for portable Step 4 initialization |
| INPI accounts Parquet | `/data-lake/raw/inpi/comptes_annuels/standard/stock_RNE_comptes_annuels_20250926_1000_v2`, 5,000 rows |
| SIREN validity | 5,000 / 5,000 rows have nine-digit SIRENs; 787 distinct SIRENs |
| Filing date quality | 5,000 rows have `date_depot`; 5,000 rows have `date_cloture` |
| Feature builder smoke | 5,000 company-year rows and 5,000 label rows rebuilt for prediction year 2025 |
| INPI feature source root | `annual_accounts` is `/data-lake/raw/inpi/comptes_annuels` in feature and label manifests |
| Account feature population | 73 / 5,000 feature rows have `annual_accounts_count_all > 0`; max count is 18 |
| Clean source-download endpoint | `GET /api/v1/ingestion/inpi/source-files` and `POST /api/v1/ingestion/inpi/source-download/run` added for official ZIP download without raw Mongo writes |
| INPI formalities Parquet | `/data-lake/raw/inpi/formalites/standard/stock_RNE_formalites_20250523_0000`, 5,000 rows |
| Formalities SIREN validity | 5,000 / 5,000 rows have nine-digit SIRENs; 5,000 distinct SIRENs |
| Mongo cleanup | Obsolete `inpi_*_raw` validation collections and `inpi_rne_source_files` were dropped from MongoDB |
| Feature source roots | `formalities_events` and `annual_accounts` are non-null in feature and label manifests |
| Feature population | 4,933 / 5,000 rows have `formalities_count_all > 0`; 73 / 5,000 rows have `annual_accounts_count_all > 0` |

Decision:

```text
Do not train yet. Wait for the missing NIVEAU1 formalities ZIP download to
finish, then rerun the full INPI Parquet export without max_records_per_file.
```

### Step 5: Add Financial Data

Status: Complete for full clean financial build.

Goal:

Add financial Parquet data for revenue, result, equity, and debt features.

Required evidence:

| Check | Required Result |
|---|---|
| Financial Parquet exists | `/data-lake/raw/financials` or `/data-lake/clean/financials` |
| Numeric fields readable | DuckDB can read financial fields |
| Feature builder uses financials | `financials` source root is not null |

Evidence found on 2026-05-03:

| Check | Result |
|---|---|
| Financial Swagger section | `/docs` includes `Financials` endpoints for resources, local files, export run/status/cancel |
| Resource discovery | `GET /api/v1/ingestion/financial/resources` found `export-detail-bilan.parquet`, 2,820,473,022 bytes, updated `2026-02-10T09:26:01.275000+00:00` |
| Raw financial export | `POST /api/v1/ingestion/financial/export/run` downloaded `/data-lake/raw/financials/data_gouv_export_detail_bilan_20260210/export-detail-bilan.parquet` |
| Raw financial rows | DuckDB read 6,368,964 rows from the downloaded Parquet |
| Clean financial builder | `python -m app.tools.build_clean_financials --overwrite` wrote `/data-lake/clean/financials` |
| Clean financial rows | 6,368,964 rows |
| Numeric fields readable | 3,546 rows with revenue, 3,648 with net result, 4,802 with equity, 4,791 with debt |
| Feature builder | 17,078,580 company-year rows and 17,078,580 label rows rebuilt for prediction years 2017-2025 |
| Financial feature source root | `financials` is `/data-lake/clean/financials` in feature and label manifests |
| Feature population | 64 rows with `latest_revenue`, 70 with `latest_net_result`, 72 with `latest_equity`, 72 with `latest_debt` |
| Mongo cleanup | No `company_financials_raw` collection exists; obsolete financial Mongo ingestion service and scheduler job were removed |

Decision:

```text
Complete for full clean financial build. Rebuild features again after INPI,
INSEE, and BODACC historical coverage are completed.
```

### Step 6: Build Training Dataset

Status: Complete as interim dataset; rebuild required after source completion.

Goal:

Build company-year features and labels across multiple years.

Required evidence:

| Check | Required Result |
|---|---|
| Feature rows | Enough rows for training |
| Label balance | Both positive and negative classes exist |
| Date cutoff | Feature dates are before prediction date |
| Manifests | Feature and label manifests exist |

### Step 7: Train And Validate

Status: On hold.

Start only after Step 6 passes.

Required evidence:

| Check | Required Result |
|---|---|
| Model trains | `model.joblib` created |
| Metrics recorded | `model_metadata.json` contains metrics |
| Validation report updated | `docs/model_validation_report.md` contains real metrics |
| Predictions published | `prediction_results` has scored companies |

## Next Action

The next action is to finish Step 4 full INPI extraction:

```text
Wait for stock_RNE_formalites_NIVEAU1_20260304_1400.zip to finish downloading,
then rerun the INPI Parquet export for all local ZIP files.
```

Do not train and do not restart the API while INPI download/export jobs are
running.
