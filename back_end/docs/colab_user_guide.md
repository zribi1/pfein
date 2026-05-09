# Google Colab User Guide For The PFE ML Data Pipeline

## Purpose

This guide explains how to run the project data pipeline from a fresh Google
Colab notebook. It is written for a user who wants copy-paste cells and clear
expectations.

The pipeline uses two storage locations:

| Location | Role |
|---|---|
| `/content/pfein` | Temporary GitHub code checkout. It disappears when the runtime resets. |
| `/content/drive/MyDrive/PFE ML Data/pfe_data` | Persistent Google Drive data folder. It stores downloads, Parquet data, reports, and ML artifacts. |

Do not delete the Drive folder unless you intentionally want to remove the
downloaded data.

## Runtime Choice

Use this setup for most pipeline work:

```text
Runtime type: Python 3
Hardware accelerator: CPU
Runtime version: Latest
```

GPU and TPU do not help much for this stage because the work is mostly
downloads, Parquet scans, DuckDB SQL, and disk I/O.

High RAM is optional:

| Task | High RAM Needed? |
|---|---|
| Download source archives only | No |
| Audit reports | Usually no |
| Capped feature build with `--max-companies 100000` | Usually no |
| Full uncapped feature build | Yes, recommended |
| Large BODACC/INPI export | Maybe, enable if memory errors appear |
| Model training on large final data | Maybe, depends on model and size |

Changing runtime type restarts Colab. Drive data remains safe, but `/content`
code and installed packages may disappear.

## Step 1: Mount Google Drive

```python
from google.colab import drive
drive.mount("/content/drive")
```

Check that the shared data folder is visible:

```python
!ls "/content/drive/MyDrive/PFE ML Data/pfe_data"
```

Expected folders after previous runs:

```text
data-lake  ml-artifacts  reports  source-archives
```

If the folder does not exist yet:

```python
!mkdir -p "/content/drive/MyDrive/PFE ML Data/pfe_data"
```

## Step 2: Clone Or Refresh The Code

If `/content/pfein` does not exist:

```python
%cd /content
!git clone --branch data-extraction --single-branch https://github.com/zribi1/pfein.git /content/pfein
```

If `/content/pfein` already exists:

```python
%cd /content/pfein
!git pull
```

Move into the backend folder:

```python
%cd /content/pfein/back_end
```

## Step 3: Install Colab Dependencies

Use the Colab requirements file, not the full backend requirements.

```python
%cd /content/pfein/back_end
!pip install -q -r collabs/requirements-colab.txt
```

If you previously uninstalled FastAPI, Starlette, or Uvicorn because of Colab
dependency conflicts, that is fine. The data pipeline does not need to run the
FastAPI server inside Colab.

## Step 4: Define The Drive Root

In this guide, every command uses:

```text
/content/drive/MyDrive/PFE ML Data/pfe_data
```

You can test the path:

```python
DRIVE_ROOT = "/content/drive/MyDrive/PFE ML Data/pfe_data"
!ls "$DRIVE_ROOT"
```

Optional fast staging root:

```python
WORK_DIR = "/content/pfe_work"
!mkdir -p "$WORK_DIR"
```

Use `--work-dir "$WORK_DIR"` on pipeline commands when you want Colab to do
downloads, extraction, and Parquet writes on local disk, then sync completed
archives and outputs back to Drive. Drive remains the durable copy; `/content`
can disappear when the runtime resets.

## Step 5: Download INSEE And Financial Data

Run this when starting from zero or when you want to refresh public INSEE and
financial source files.

```python
%cd /content/pfein/back_end

!python collabs/full_pipeline.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --work-dir "/content/pfe_work" \
  --install-deps \
  --no-inpi \
  --no-bodacc \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000
```

This downloads or reuses:

| Source | Stored Under |
|---|---|
| INSEE Sirene bulk files | `source-archives/insee/bulk` |
| Financial Parquet file | `source-archives/financials/data_gouv` |
| Raw Parquet exports | `data-lake/raw` |
| Clean normalized tables | `data-lake/clean` |
| Feature and label tables | `data-lake/features` |

Expected main outputs:

```text
data-lake/features/company_year_features
data-lake/features/risk_labels
data-lake/features/company_features
ml-artifacts
```

## Step 6: Rebuild From Existing Downloads Only

If the files are already in Drive, do not redownload. Rebuild clean and feature
tables only:

```python
%cd /content/pfein/back_end

!python collabs/build_ml_data.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --work-dir "/content/pfe_work" \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000
```

Use this after code fixes, such as cleaner mapping changes.

If you also want the audit report from the same command, add `--audit`:

```python
!python collabs/build_ml_data.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --work-dir "/content/pfe_work" \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000 \
  --audit
```

## Step 7: Generate A Data-Lake Audit Report

Run the audit after each important pipeline change.

```python
%cd /content/pfein/back_end

!python collabs/audit_data_lake.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --max-columns 25 \
  --sample-rows 2
```

Default outputs:

```text
reports/data_lake_audit.md
reports/data_lake_audit.json
```

For a timestamped report:

```python
!python collabs/audit_data_lake.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --max-columns 25 \
  --sample-rows 2 \
  --output-md "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit_after_change.md" \
  --output-json "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit_after_change.json"
```

Check the report timestamp:

```python
!head -20 "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit.md"
```

Important audit fields to inspect:

| Section | What To Check |
|---|---|
| Readiness Gate | Whether training is blocked |
| Dataset Summary | Which raw/clean/features datasets exist |
| `clean_company_identity` | Coverage for activity, status, legal category, name, creation date |
| `features_company_year` | Coverage for final model feature columns |
| Label Balance By Year | Whether labels have positive examples |

## Step 7.1: Generate ML Readiness Audits

Run these audits after feature generation and before treating model metrics as
final evidence.

```python
%cd /content/pfein/back_end

!python collabs/audit_ml_readiness.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --sample-rows 20
```

Outputs:

```text
reports/label_audit.md
reports/leakage_audit.md
reports/feature_safety_audit.md
reports/ml_readiness_audit.json
```

Use `label_audit.md` to explain label balance by year and source,
`leakage_audit.md` to verify target/date leakage risks, and
`feature_safety_audit.md` to review which features are safe historical signals
and which still require verification.

## Step 8: Download BODACC Archives Only

Use this on normal RAM. It downloads historical BODACC archives to Drive but
does not export/process them.

```python
%cd /content/pfein/back_end

!python collabs/download_bodacc.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --work-dir "/content/pfe_work" \
  --repo-dir "/content/pfein/back_end" \
  --mode historical \
  --families PCL,RCS-B \
  --start-year 2017 \
  --end-year 2025 \
  --download \
  --no-export
```

Expected output includes discovery and download progress:

```text
[bodacc] download phase start ...
[bodacc] scanning directory ...
[bodacc] discovery done ...
[bodacc] discovered=... selected=...
[download] start ...
[download] file.taz: ...
[bodacc] download phase done
[bodacc] raw export phase skipped
```

For a small smoke test:

```python
!python collabs/download_bodacc.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --work-dir "/content/pfe_work" \
  --repo-dir "/content/pfein/back_end" \
  --mode historical \
  --families PCL,RCS-B \
  --start-year 2025 \
  --end-year 2025 \
  --max-files 2 \
  --download \
  --no-export
```

## Step 9: Export Existing BODACC Archives

Use this after downloads are complete. Enable High RAM if export or later
feature building hits memory pressure.

```python
%cd /content/pfein/back_end

!python collabs/download_bodacc.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --work-dir "/content/pfe_work" \
  --repo-dir "/content/pfein/back_end" \
  --mode historical \
  --families PCL,RCS-B \
  --start-year 2017 \
  --end-year 2025 \
  --no-download \
  --export
```

This writes BODACC raw Parquet under:

```text
data-lake/raw/bodacc
```

The historical DILA folder has mixed archive layouts. Years `2017` to `2021`
are exposed as folders with per-family archives, while older years and recent
years may be exposed as root-level full-year bundles such as `BODACC_2016.tar`
or `2022.tar.gz`. The Colab downloader includes those full-year bundles
automatically when they fall inside the requested year range.

Then rebuild clean and features:

```python
!python collabs/build_ml_data.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000
```

Then audit again:

```python
!python collabs/audit_data_lake.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --max-columns 25 \
  --sample-rows 2 \
  --output-md "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit_after_bodacc.md" \
  --output-json "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit_after_bodacc.json"
```

After BODACC is working, the audit should show:

```text
raw_bodacc: available
clean_legal_events: available
legal/radiation labels: positive examples may appear
```

## Step 10: INPI Setup And Download

INPI requires credentials. Do not commit credentials to Git.

Set credentials inside Colab:

```python
import os

os.environ["INPI_FTP_HOST"] = "your_host"
os.environ["INPI_FTP_PORT"] = "21"
os.environ["INPI_FTP_USER"] = "your_user"
os.environ["INPI_FTP_PASSWORD"] = "your_password"
os.environ["INPI_FTP_PROTOCOL"] = "ftp"
os.environ["INPI_REMOTE_BASE_DIR"] = "/"
```

Download INPI archives:

```python
%cd /content/pfein/back_end

!python collabs/download_inpi.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --repo-dir "/content/pfein/back_end" \
  --categories comptes_annuels,formalites \
  --niveaux standard,niveau1
```

For a smoke test:

```python
!python collabs/download_inpi.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --repo-dir "/content/pfein/back_end" \
  --categories comptes_annuels,formalites \
  --niveaux standard,niveau1 \
  --max-files 2
```

Export existing INPI ZIP archives to raw Parquet:

```python
!python collabs/export_raw_sources.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --repo-dir "/content/pfein/back_end" \
  --no-insee \
  --inpi \
  --no-bodacc
```

Then rebuild and audit:

```python
!python collabs/build_ml_data.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000

!python collabs/audit_data_lake.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --max-columns 25 \
  --sample-rows 2 \
  --output-md "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit_after_inpi.md" \
  --output-json "/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit_after_inpi.json"
```

## Step 11: One-Command BODACC Pipeline

After wrappers are up to date, this command downloads BODACC, exports it,
rebuilds clean/features, and keeps the `100000` company cap:

```python
%cd /content/pfein/back_end

!python collabs/full_pipeline.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --no-insee \
  --no-bilan \
  --no-inpi \
  --bodacc \
  --bodacc-mode historical \
  --bodacc-families PCL RCS-B \
  --bodacc-start-year 2017 \
  --bodacc-end-year 2025 \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000
```

If you want download only, use `download_bodacc.py` with `--no-export` instead.

## Step 12: Training

Do not train the final model until the audit report shows enough source
coverage and label positives.

Minimum expected readiness:

| Requirement | Why |
|---|---|
| `clean_company_identity` available | Needed for identity and status features |
| `clean_financials` available | Needed for financial features |
| `clean_legal_events` available | Needed for legal distress and radiation labels |
| `features_company_year` available | Model input |
| `features_risk_labels` available | Model target |
| Positive labels exist | A classifier cannot learn a useful event target from all-zero labels |

When ready, run:

```python
!python collabs/build_ml_data.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000 \
  --train
```

For final training, remove the cap only after testing disk/RAM:

```python
!python collabs/build_ml_data.py \
  --drive-root "/content/drive/MyDrive/PFE ML Data/pfe_data" \
  --start-year 2017 \
  --end-year 2025 \
  --train
```

## Common Problems

### `/content/pfein` Does Not Exist

The Colab runtime reset. Drive data is safe. Clone again:

```python
%cd /content
!git clone --branch data-extraction --single-branch https://github.com/zribi1/pfein.git /content/pfein
%cd /content/pfein/back_end
!pip install -q -r collabs/requirements-colab.txt
```

### `fatal: destination path '/content/pfein' already exists`

The code folder already exists. Use pull instead:

```python
%cd /content/pfein
!git pull
%cd /content/pfein/back_end
```

### Pip Dependency Conflict Warnings

Warnings about `google-adk`, `fastapi`, `starlette`, or `uvicorn` are usually
not blockers for the data pipeline. The Colab pipeline does not need to run the
FastAPI backend.

### `--max-companies` Is Unrecognized

Pull the latest code:

```python
%cd /content/pfein
!git pull
%cd /content/pfein/back_end
```

If still blocked, run the lower-level feature builder directly:

```python
!python -m app.tools.build_company_year_features \
  --data-lake-dir "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake" \
  --start-year 2017 \
  --end-year 2025 \
  --max-companies 100000 \
  --overwrite
```

### Audit Report Looks Old

The default audit output is in Drive:

```text
/content/drive/MyDrive/PFE ML Data/pfe_data/reports/data_lake_audit.md
```

The local repo file `docs/data_lake_audit.md` is not automatically updated.
Use timestamped output paths if you want to preserve several audit versions.

### DuckDB Temporary File Error On Google Drive

The project configures DuckDB temp storage under `/content/pfein_duckdb_tmp`
for Colab. If a run fails after a reset, clean only the temp folder:

```python
!rm -rf /content/pfein_duckdb_tmp
!mkdir -p /content/pfein_duckdb_tmp
```

Do not delete the Drive data folder.

### Disk Space Check

```python
!df -h /content
!du -h -d 1 /content 2>/dev/null | sort -h | tail -20
```

Most project data should be under `/content/drive`, not duplicated under
temporary local folders.

## Recommended Order For A Fresh Notebook

1. Mount Drive.
2. Clone or pull code.
3. Install `collabs/requirements-colab.txt`.
4. Check Drive data folder.
5. Rebuild existing INSEE/financial features with `--max-companies 100000`.
6. Run audit.
7. Download BODACC archives only on normal RAM.
8. Enable High RAM only if needed for export/build.
9. Export BODACC and rebuild features.
10. Run audit again.
11. Add INPI after credentials are ready.
12. Train only after audit readiness and label balance are acceptable.
