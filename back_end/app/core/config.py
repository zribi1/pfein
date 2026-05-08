from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "Pfein Backend"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/data-lake/logs/pfein-backend.log"

    MONGO_URI: str = "mongodb://mongo:27017"
    MONGO_DB: str = "pfein"

    ML_ARTIFACTS_DIR: str = "app/ml/artifacts"
    ML_MODEL_FILE: str = "model.joblib"

    SCHEDULER_TIMEZONE: str = "UTC"

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])

    DATAGOUV_API_BASE: str = "https://www.data.gouv.fr/api/1"
    DATAGOUV_DATASET_SLUG: str = "donnees-financieres-detaillees-des-entreprises-format-parquet"
    INGESTION_DATA_DIR: str = "/source-archives"
    FINANCIAL_SOURCE_ARCHIVE_DIR: str = "/source-archives/financials/data_gouv"
    DATA_LAKE_DIR: str = "/data-lake"
    INGESTION_STATE_COLLECTION: str = "ingestion_jobs"
    FINANCIAL_EXPORT_DATASET_SLUG: str = "financial_data_lake_export"

    COMPANY_COLLECTION: str = "company_registry"
    PREDICTION_RESULTS_COLLECTION: str = "prediction_results"
    REJECTED_RECORDS_COLLECTION: str = "ingestion_rejected_records"

    BODACC_INIT_BASE_URL: str = "https://echanges.dila.gouv.fr/OPENDATA/BODACC/FluxHistorique/"
    BODACC_INIT_DATA_DIR: str = "/source-archives/bodacc"
    BODACC_IMPORTS_COLLECTION: str = "bodacc_imports"
    BODACC_ANNONCES_COLLECTION: str = "bodacc_annonces"
    BODACC_INIT_FILES_COLLECTION: str = "bodacc_historical_archive_files"
    BODACC_INIT_DATASET_SLUG: str = "bodacc_init"
    BODACC_INIT_MAX_FILES_PER_RUN: int = 0
    BODACC_INIT_DELETE_AFTER_INGEST: bool = False
    BODACC_CURRENT_BASE_URL: str = "https://echanges.dila.gouv.fr/OPENDATA/BODACC/FluxAnneeCourante/"
    BODACC_CURRENT_DATA_DIR: str = "/source-archives/bodacc/current"
    BODACC_CURRENT_FILES_COLLECTION: str = "bodacc_current_archive_files"
    BODACC_CURRENT_DATASET_SLUG: str = "bodacc_current"
    BODACC_CURRENT_MAX_FILES_PER_RUN: int = 0
    BODACC_CURRENT_DELETE_AFTER_INGEST: bool = False
    BODACC_LABEL_EXPORT_DATASET_SLUG: str = "bodacc_current_label_export"
    BODACC_LABEL_EXPORT_PROGRESS_FILE: str = "/data-lake/raw/bodacc/current_label_export_progress_v2.json"
    BODACC_LABEL_EXPORT_BATCH_SIZE: int = 100_000
    BODACC_HTTP_TIMEOUT_SECONDS: float = 180.0
    BODACC_DEBUG_BAD_XML_ENABLED: bool = False
    BODACC_DEBUG_BAD_XML_DIR: str = "/source-archives/bodacc/debug_bad_xml"
    BODACC_DEBUG_SAMPLE_XML_ENABLED: bool = False
    BODACC_DEBUG_SAMPLE_XML_DIR: str = "/source-archives/bodacc/debug_xml_samples"
    BODACC_DEBUG_SAMPLE_XML_MAX_PER_FAMILY: int = 3

    INPI_FTP_HOST: str = ""
    INPI_FTP_PORT: int = 21
    INPI_FTP_USER: str = ""
    INPI_FTP_PASSWORD: str = ""
    INPI_FTP_PROTOCOL: str = "ftp"
    INPI_REMOTE_BASE_DIR: str = "/"
    INPI_LOCAL_DATA_DIR: str = "/source-archives/inpi"
    INPI_DELETE_AFTER_INGEST: bool = False
    INPI_RNE_DATASET_SLUG: str = "inpi_rne_bulk"
    INPI_RNE_FORMALITES_COLLECTION: str = "inpi_formalities_raw"
    INPI_RNE_FORMALITES_NIVEAU1_COLLECTION: str = "inpi_formalities_level1_raw"
    INPI_RNE_COMPTES_ANNUELS_COLLECTION: str = "inpi_annual_accounts_raw"
    INPI_RNE_COMPTES_ANNUELS_NIVEAU1_COLLECTION: str = "inpi_annual_accounts_level1_raw"
    INPI_RNE_FILES_COLLECTION: str = "inpi_rne_source_files"
    INPI_RNE_BATCH_SIZE: int = 1000
    INPI_RNE_CRON_HOUR: int = 2
    INPI_RNE_CRON_MINUTE: int = 30
    INPI_RNE_ENABLED: bool = False
    INPI_RNE_MAX_FILES_PER_RUN: int = 0
    INPI_FTP_TIMEOUT: int = 600
    INPI_REMOTE_INCLUDE_GLOB: str = ""
    INPI_SOURCE_DOWNLOAD_DATASET_SLUG: str = "inpi_source_download"
    INPI_PARQUET_EXPORT_DATASET_SLUG: str = "inpi_parquet_export"
    INPI_PARQUET_EXPORT_PROGRESS_FILE: str = "/data-lake/raw/inpi/parquet_export_progress.json"
    INPI_PARQUET_EXPORT_BATCH_SIZE: int = 100_000

    INSEE_BULK_DATASET_SLUG: str = "base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret"
    INSEE_BULK_SOURCE_DIR: str = "/source-archives/insee/bulk"
    INSEE_BULK_EXPORT_DATASET_SLUG: str = "insee_bulk_export"
    API_RETRY_MAX_ATTEMPTS: int = 5
    API_RETRY_BASE_DELAY_SECONDS: float = 2.0
    API_RETRY_MAX_DELAY_SECONDS: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
