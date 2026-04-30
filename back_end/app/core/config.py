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

    MONGO_URI: str = "mongodb://mongo:27017"
    MONGO_DB: str = "pfein"

    ML_ARTIFACTS_DIR: str = "app/ml/artifacts"
    ML_MODEL_FILE: str = "model.joblib"

    SCHEDULER_TIMEZONE: str = "UTC"

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])

    DATAGOUV_API_BASE: str = "https://www.data.gouv.fr/api/1"
    DATAGOUV_DATASET_SLUG: str = "donnees-financieres-detaillees-des-entreprises-format-parquet"
    INGESTION_DATA_DIR: str = "/app/data"
    INGESTION_BATCH_SIZE: int = 1000
    INGESTION_COLLECTION: str = "donnees_financieres_entreprises"
    INGESTION_STATE_COLLECTION: str = "ingestion_state"
    INGESTION_CRON_HOUR: int = 3
    INGESTION_CRON_MINUTE: int = 0

    COMPANY_COLLECTION: str = "companies"
    COMPANY_SYNC_STATE_COLLECTION: str = "company_sync_state"
    COMPANY_SYNC_CRON_HOUR: int = 2
    COMPANY_SYNC_CRON_MINUTE: int = 0
    COMPANY_SYNC_ENABLED: bool = True

    BODACC_BASE_URL: str = "https://bodacc-datadila.opendatasoft.com"
    BODACC_DATASET: str = "annonces-commerciales"
    BODACC_API_VERSION: str = "v2.1"
    BODACC_LIMIT: int = 100
    BODACC_WHERE: str = ""
    BODACC_MAX_PAGES: int = 0
    BODACC_SLEEP_SECONDS: float = 0.25

    INPI_BASE_URL: str = "https://registre-national-entreprises.inpi.fr"
    INPI_ENDPOINT: str = "/api/companies"
    INPI_USERNAME: str = ""
    INPI_PASSWORD: str = ""
    INPI_PER_PAGE: int = 100
    INPI_START_PAGE: int = 1
    INPI_MAX_PAGES: int = 0
    INPI_SLEEP_SECONDS: float = 0.35

    INPI_FTP_HOST: str = ""
    INPI_FTP_PORT: int = 21
    INPI_FTP_USER: str = ""
    INPI_FTP_PASSWORD: str = ""
    INPI_FTP_PROTOCOL: str = "ftp"
    INPI_REMOTE_BASE_DIR: str = "/"
    INPI_LOCAL_DATA_DIR: str = "/app/data/inpi"
    INPI_DELETE_AFTER_INGEST: bool = False
    INPI_RNE_DATASET_SLUG: str = "inpi_rne_bulk"
    INPI_RNE_COLLECTION: str = "rne_companies"
    INPI_RNE_FILES_COLLECTION: str = "inpi_rne_files"
    INPI_RNE_BATCH_SIZE: int = 1000
    INPI_RNE_CRON_HOUR: int = 2
    INPI_RNE_CRON_MINUTE: int = 30
    INPI_RNE_ENABLED: bool = True
    INPI_RNE_MAX_FILES_PER_RUN: int = 0
    INPI_FTP_TIMEOUT: int = 600
    INPI_REMOTE_INCLUDE_GLOB: str = ""

    INSEE_BASE_URL: str = "https://api.insee.fr/api-sirene/3.11/siren"
    INSEE_API_KEY: str = ""
    INSEE_QUERY: str = ""
    INSEE_PAGE_SIZE: int = Field(default=1000, ge=1, le=1000)
    INSEE_MAX_PAGES: int = 0
    INSEE_SLEEP_SECONDS: float = 0.35
    API_RETRY_MAX_ATTEMPTS: int = 5
    API_RETRY_BASE_DELAY_SECONDS: float = 2.0
    API_RETRY_MAX_DELAY_SECONDS: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
