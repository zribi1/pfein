# Colab Data Preparation Blocks

For a full runnable notebook, open:

```text
collabs/pfe_ml_colab_workbook.ipynb
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
