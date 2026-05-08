# Data Storage Layout

The backend uses two durable filesystem roots inside Docker:

```text
/source-archives
/data-lake
```

They serve different purposes and should not be mixed.

## Source Archives

`/source-archives` contains official downloaded files exactly as they came from
the provider. These files are inputs, not analytical tables.

```text
/source-archives/
  inpi/
    stock_RNE_comptes_annuels_*.zip
    stock_RNE_formalites_*.zip
  bodacc/
    OPENDATA/BODACC/FluxHistorique/*.taz
    current/OPENDATA/BODACC/FluxAnneeCourante/*.taz
  financials/
    data_gouv/<run-name>/*.parquet
  insee/
    bulk/<dataset-type>/<official-file>
    api/<run-name>/page-*.json
```

Host mount:

```text
D:/PFE_volumes/source-archives -> /source-archives
```

The active source archive root is `D:/PFE_volumes/source-archives`.

Financial source Parquet is preserved under `/source-archives/financials` on
new downloads, then copied into `/data-lake/raw/financials` for analytical
processing.

INSEE bulk files are the primary source. API page preservation exists only for
legacy/targeted refresh paths.

## Data Lake

`/data-lake` contains Parquet datasets and pipeline outputs. This is the
analytical source of truth.

```text
/data-lake/
  raw/
    inpi/
      comptes_annuels/<niveau>/<source-zip-name>/part-*.parquet
      formalites/<niveau>/<source-zip-name>/part-*.parquet
    bodacc/<mode>/<year>/<source-archive-name>/part-*.parquet
    insee/unites_legales/<run-name>/part-*.parquet
    financials/<source-run>/*.parquet
  clean/
    company_identity/
    legal_events/
    formalities_events/
    annual_accounts/
    financials/
  features/
    company_year_features/
    risk_labels/
    company_features/
  logs/
```

Host mount:

```text
D:/PFE_volumes/data-lake -> /data-lake
```

## INPI Flow

The INPI path is:

```text
INPI FTP/SFTP
  -> /source-archives/inpi/*.zip
  -> /data-lake/raw/inpi/<category>/<niveau>/<zip-name>/part-*.parquet
  -> /data-lake/clean/annual_accounts
  -> /data-lake/clean/formalities_events
  -> /data-lake/features/...
```

## Financial Flow

```text
data.gouv.fr financial Parquet
  -> /source-archives/financials/data_gouv/<run-name>/<file>.parquet
  -> /data-lake/raw/financials/<run-name>/<file>.parquet
  -> /data-lake/clean/financials
  -> /data-lake/features/...
```

## INSEE Bulk Flow

```text
INSEE Sirene data.gouv.fr bulk files
  -> /source-archives/insee/bulk/<dataset-type>/<official-file>
  -> /data-lake/raw/insee/bulk/<dataset-type>/<source-name>/part-*.parquet
  -> /data-lake/clean/company_identity
  -> /data-lake/clean/establishments
  -> /data-lake/features/...
```

The INSEE API path is legacy/optional. It can still preserve page JSON under
`/source-archives/insee/api/<run-name>/`, but full platform rebuilds should use
bulk files.

The source download step only mirrors ZIP files. The Parquet export step turns
those ZIP files into raw Parquet. The clean-source builder groups and normalizes
raw Parquet into model-friendly tables.

## Rule of Thumb

Use `/source-archives` when asking "what did we download?"

Use `/data-lake/raw` when asking "what did we extract?"

Use `/data-lake/clean` when asking "what table should analytics or ML read?"

Use `/data-lake/features` when asking "what does the model train or score on?"
