# Colab Data Preparation Blocks

For a full runnable notebook, open:

```text
collabs/pfe_ml_colab_workbook.ipynb
```

For model training only, after the data lake and feature tables already exist,
open:

```text
collabs/pfe_ml_colab_training_only.ipynb
```

For a detailed step-by-step user guide, read:

```text
docs/colab_user_guide.md
```

Mount Drive first:

```python
from google.colab import drive
drive.mount("/content/drive")
```

Clone the repo and install dependencies:

```bash
git clone <your-repo-url> /content/pfein
cd /content/pfein/back_end
pip install -q -r collabs/requirements-colab.txt
```

Do not install the backend `requirements.txt` in Colab unless you want to run
the API there. The Colab file avoids conflicts with packages preinstalled by
Google Colab.

Training plots are generated in Colab, so plotting dependencies such as
`matplotlib` live in `collabs/requirements-colab.txt`, not the backend API
requirements.

The default Drive storage root is:

```text
/content/drive/MyDrive/pfe_data
```

For faster Colab runs, use local staging plus Drive persistence:

```bash
--work-dir /content/pfe_work
```

When `--work-dir` is set, downloads and raw Parquet exports run on Colab's
local disk, then completed archives and outputs are synced back to Drive.

## Recommended Download/Export Run

Use `full_pipeline.py --step ...` in separate Colab cells. Each step checks
Drive first; if the expected download or export artifacts are already there,
the step is marked skipped instead of redownloading or re-exporting.

```python
DRIVE_ROOT = "/content/drive/MyDrive/PFE ML Data/pfe_data"
WORK_DIR = "/content/pfe_work"
```

Run one cell at a time:

```bash
python collabs/full_pipeline.py --step download_insee --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --install-deps --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step export_raw_insee --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step download_bilan --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step export_raw_bilan --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step download_inpi --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --start-year 2017 --end-year 2025 --inpi-retries 2
python collabs/full_pipeline.py --step export_raw_inpi --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step download_bodacc --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --bodacc-mode historical --bodacc-families PCL RCS-B --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step export_raw_bodacc --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --bodacc-mode historical --bodacc-families PCL RCS-B --start-year 2017 --end-year 2025
python collabs/full_pipeline.py --step build_ml_data --drive-root "$DRIVE_ROOT" --work-dir "$WORK_DIR" --start-year 2017 --end-year 2025 --audit
```

The step split is:

| Step | Checks In Drive | Pipeline |
|---|---|
| `download_insee` | `source-archives/insee/bulk` | Download INSEE bulk files |
| `export_raw_insee` | `data-lake/raw/insee/bulk` | Seed INSEE files from Drive if needed, then export raw Parquet |
| `download_bilan` | `source-archives/financials/data_gouv` | Download public financial bilan Parquet |
| `export_raw_bilan` | `data-lake/raw/financials` | Seed financial file from Drive if needed, then copy to raw |
| `download_inpi` | `source-archives/inpi` | Download INPI ZIP archives |
| `export_raw_inpi` | `data-lake/raw/inpi` | Seed INPI ZIPs from Drive if needed, then export raw Parquet |
| `download_bodacc` | `source-archives/bodacc` | Download BODACC archives |
| `export_raw_bodacc` | `data-lake/raw/bodacc` | Seed BODACC archives from Drive if needed, then export raw Parquet |

The final `build_ml_data` step is global because it joins all available
sources into clean tables, labels, features, audits, and optional training.

`download_inpi` uses short retries by default. If a transfer fails, rerun the
same cell; partial `.part` files are synced to Drive and resumed.

`download_bodacc` and `export_raw_bodacc` default to the same
`--start-year/--end-year` window used for feature building. Add
`--bodacc-all-years` only when you intentionally want the full archive history.

Use `--force` when you intentionally want to rerun a step even though Drive
already contains the expected artifacts.

You can still run source bundles with `--source insee`, `--source bilan`,
`--source inpi`, or `--source bodacc`; each bundle runs its download step and
then its export step.

## Separate Blocks

Download/export INSEE:

```bash
python collabs/download_insee.py --install-deps
```

Download/copy financial bilan data:

```bash
python collabs/download_bilan.py
```

Download INPI with credentials from environment variables:

```python
import os
os.environ["INPI_FTP_HOST"] = "..."
os.environ["INPI_FTP_PORT"] = "21"
os.environ["INPI_FTP_USER"] = "..."
os.environ["INPI_FTP_PASSWORD"] = "..."
os.environ["INPI_FTP_PROTOCOL"] = "ftp"
os.environ["INPI_REMOTE_BASE_DIR"] = "/"
```

```bash
python collabs/download_inpi.py --categories=comptes_annuels,formalites --niveaux=standard,niveau1
python collabs/export_raw_sources.py --no-insee --inpi --no-bodacc
```

Download and export BODACC historical label archives:

```text
/content/drive/MyDrive/pfe_data/source-archives/bodacc
```

```bash
python collabs/download_bodacc.py --work-dir /content/pfe_work --mode=historical --families=PCL,RCS-B --start-year 2010 --end-year 2025
```

This discovers DILA BODACC archives, downloads selected `PCL` and `RCS-B`
archives into Drive, and exports them to `/data-lake/raw/bodacc`. For years
where DILA publishes only a full-year bundle such as `BODACC_2016.tar` or
`2022.tar.gz`, the bundle is included automatically because it contains several
BODACC families inside one archive.

Build ML-ready tables:

```bash
python collabs/build_ml_data.py --work-dir /content/pfe_work --start-year 2017 --end-year 2025
```

Build ML-ready tables and generate the audit report in one run:

```bash
python collabs/build_ml_data.py --work-dir /content/pfe_work --start-year 2017 --end-year 2025 --audit
```

Audit raw, clean, and feature datasets:

```bash
python collabs/audit_data_lake.py --drive-root "/content/drive/MyDrive/pfe_data"
```

The audit writes:

```text
<drive-root>/reports/data_lake_audit.json
<drive-root>/reports/data_lake_audit.md
```

Use this before training to inspect column coverage, missingness, date ranges,
sample rows, and which fields are reliable candidates for model features.

Audit ML labels, leakage, and feature safety:

```bash
python collabs/audit_ml_readiness.py --drive-root "/content/drive/MyDrive/pfe_data"
```

This writes:

```text
<drive-root>/reports/label_audit.md
<drive-root>/reports/leakage_audit.md
<drive-root>/reports/feature_safety_audit.md
<drive-root>/reports/ml_readiness_audit.json
```

Train too:

```bash
python collabs/build_ml_data.py --start-year 2017 --end-year 2025 --train
```

Run the public-source pipeline in one command:

```bash
python collabs/full_pipeline.py --work-dir /content/pfe_work --install-deps --no-inpi --no-bodacc --start-year 2017 --end-year 2025
```

Run the public-source pipeline plus historical BODACC labels:

```bash
python collabs/full_pipeline.py --install-deps --no-inpi --bodacc --bodacc-mode=historical --bodacc-start-year 2010 --bodacc-end-year 2025 --start-year 2010 --end-year 2025
```

Run with INPI after setting environment variables:

```bash
python collabs/full_pipeline.py --inpi --no-bodacc --start-year 2017 --end-year 2025
```

## Outputs

```text
/content/drive/MyDrive/pfe_data/source-archives
/content/drive/MyDrive/pfe_data/data-lake/raw
/content/drive/MyDrive/pfe_data/data-lake/clean
/content/drive/MyDrive/pfe_data/data-lake/features/company_year_features
/content/drive/MyDrive/pfe_data/data-lake/features/risk_labels
/content/drive/MyDrive/pfe_data/data-lake/features/company_features
/content/drive/MyDrive/pfe_data/ml-artifacts
```

Do not commit real INPI credentials.
