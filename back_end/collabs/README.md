# Colab Data Preparation Blocks

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

Export BODACC archives already placed in Drive:

```text
/content/drive/MyDrive/pfe_data/source-archives/bodacc
```

```bash
python collabs/download_bodacc.py --mode=current --families=PCL,RCS-B
```

Build ML-ready tables:

```bash
python collabs/build_ml_data.py --start-year 2017 --end-year 2025
```

Train too:

```bash
python collabs/build_ml_data.py --start-year 2017 --end-year 2025 --train
```

Run the public-source pipeline in one command:

```bash
python collabs/full_pipeline.py --install-deps --no-inpi --no-bodacc --start-year 2017 --end-year 2025
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
