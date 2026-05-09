# Data Lake Audit Report

> This report is generated automatically from the Parquet data lake. It is intended to support data validation, feature selection, and the decision to train or postpone model training.

## Executive View

| Item | Value |
|---|---:|
| Generated at | `2026-05-09T01:39:59.779095+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |
| Datasets available | 7 / 12 |
| Datasets missing | 5 |
| Total profiled rows | 290,663,708 |
| Training ready | **no** |

## Purpose

This report profiles raw, clean, and feature Parquet datasets before final model training. It is used to understand schema coverage, missingness, date ranges, join quality, and which columns are reliable enough to become model features.

## Readiness Gate

**Decision:** training should wait. The data lake still has blockers that should be resolved or explicitly accepted before model training.

| Check | OK | Meaning |
|---|---:|---|
| `insee_raw` | **pass** | INSEE raw data is required for company identity and administrative status. |
| `financials` | **pass** | Financial raw or clean data is required for accounting features. |
| `bodacc` | **blocker** | BODACC raw data is required for legal distress and radiation labels. |
| `features` | **pass** | Feature and label tables are required before training. |
| `continuity_label_column` | **pass** | The primary continuity-risk label must exist. |

### Current Blockers

- `bodacc`: BODACC raw data is required for legal distress and radiation labels.

## Quality Checks

- `feature_duplicate_company_year`: **pass** `{"key": ["siren", "prediction_year"], "duplicate_keys": 0, "duplicate_rows": 0, "ok": true}`
- `feature_siren_quality`: **pass** `{"rows": 900000, "valid_siren": 900000, "null_siren": 0, "valid_rate": 1.0, "ok": true}`
- `label_duplicate_company_year`: **pass** `{"key": ["siren", "prediction_year"], "duplicate_keys": 0, "duplicate_rows": 0, "ok": true}`

### Label Balance By Year

| prediction_year | rows | continuity_risk_12m_label_positive | continuity_risk_12m_label_rate | legal_distress_risk_12m_label_positive | legal_distress_risk_12m_label_rate | radiation_risk_12m_label_positive | radiation_risk_12m_label_rate | financial_weakness_risk_12m_label_positive | financial_weakness_risk_12m_label_rate | filing_anomaly_risk_12m_label_positive | filing_anomaly_risk_12m_label_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2017 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 98 | 0.00098 | 0 | 0.0 |
| 2018 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 99 | 0.00099 | 0 | 0.0 |
| 2019 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 121 | 0.00121 | 0 | 0.0 |
| 2020 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 76 | 0.00076 | 0 | 0.0 |
| 2021 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 73 | 0.00073 | 0 | 0.0 |
| 2022 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 70 | 0.0007 | 0 | 0.0 |
| 2023 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 55 | 0.00055 | 0 | 0.0 |
| 2024 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 8 | 8e-05 | 0 | 0.0 |
| 2025 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 |
- `label_siren_quality`: **pass** `{"rows": 900000, "valid_siren": 900000, "null_siren": 0, "valid_rate": 1.0, "ok": true}`

## Dataset Summary

| Dataset | Status | Rows | Files | Columns | Main Role |
|---|---:|---:|---:|---:|---|
| `raw_insee` | **available** | 246,453,008 | 5 | 110 | identity source |
| `raw_financials` | **available** | 6,368,964 | 1 | 5 | financial source |
| `raw_inpi` | **missing** | 0 | 0 | 0 | registry source |
| `raw_bodacc` | **missing** | 0 | 0 | 0 | legal event source |
| `clean_company_identity` | **available** | 29,572,772 | 1 | 14 | normalized identity |
| `clean_financials` | **available** | 6,368,964 | 1 | 23 | normalized financials |
| `clean_legal_events` | **missing** | 0 | 0 | 0 | normalized legal events |
| `clean_formalities_events` | **missing** | 0 | 0 | 0 | normalized registry events |
| `clean_annual_accounts` | **missing** | 0 | 0 | 0 | normalized filings |
| `features_company_year` | **available** | 900,000 | 9 | 41 | model features |
| `features_risk_labels` | **available** | 900,000 | 9 | 9 | model labels |
| `features_company` | **available** | 100,000 | 1 | 41 | latest company snapshot |

## raw_insee

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/insee`

**Rows:** 246,453,008

**Files:** 5

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `siren` | `VARCHAR` | 0.960964 | 28586411 |  |  |  |
| `nic` | `VARCHAR` | 0.557674 | 70386 |  |  |  |
| `siret` | `VARCHAR` | 0.557674 | 47732907 |  |  |  |
| `statutDiffusionEtablissement` | `VARCHAR` | 0.175756 | 2 |  |  |  |
| `dateCreationEtablissement` | `DATE` | 0.161848 | 31031 | 0001-01-16 | 5015-04-05 |  |
| `trancheEffectifsEtablissement` | `VARCHAR` | 0.175756 | 17 |  |  |  |
| `anneeEffectifsEtablissement` | `BIGINT` | 0.010077 | 1 | 2023 | 2023 | 2023 |
| `activitePrincipaleRegistreMetiersEtablissement` | `VARCHAR` | 0.012412 | 520 |  |  |  |
| `dateDernierTraitementEtablissement` | `TIMESTAMP` | 0.175756 | 3418664 | 2024-03-22 15:40:57 | 2026-04-30 23:55:58 |  |
| `etablissementSiege` | `BOOLEAN` | 0.175756 | 2 |  |  |  |
| `nombrePeriodesEtablissement` | `BIGINT` | 0.175756 | 47 | 1 | 52 | 2.17301 |
| `complementAdresseEtablissement` | `VARCHAR` | 0.050256 | 2607333 |  |  |  |
| `numeroVoieEtablissement` | `VARCHAR` | 0.143248 | 9333 |  |  |  |
| `indiceRepetitionEtablissement` | `VARCHAR` | 0.027507 | 41 |  |  |  |
| `dernierNumeroVoieEtablissement` | `VARCHAR` | 0.021783 | 357 |  |  |  |
| `indiceRepetitionDernierNumeroVoieEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `typeVoieEtablissement` | `VARCHAR` | 0.155159 | 503 |  |  |  |
| `libelleVoieEtablissement` | `VARCHAR` | 0.172446 | 1834047 |  |  |  |
| `codePostalEtablissement` | `VARCHAR` | 0.174522 | 20408 |  |  |  |
| `libelleCommuneEtablissement` | `VARCHAR` | 0.174293 | 40535 |  |  |  |
| `libelleCommuneEtrangerEtablissement` | `VARCHAR` | 0.001342 | 126590 |  |  |  |
| `distributionSpecialeEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `codeCommuneEtablissement` | `VARCHAR` | 0.174293 | 44356 |  |  |  |
| `codeCedexEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `libelleCedexEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |

### Sample Rows

```json
[
  {
    "siren": "000325175",
    "nic": "00016",
    "siret": "00032517500016",
    "statutDiffusionEtablissement": "O",
    "dateCreationEtablissement": "2000-09-26 00:00:00",
    "trancheEffectifsEtablissement": "NN",
    "anneeEffectifsEtablissement": NaN,
    "activitePrincipaleRegistreMetiersEtablissement": "3212ZZ",
    "dateDernierTraitementEtablissement": "2024-03-22 15:40:57",
    "etablissementSiege": false,
    "nombrePeriodesEtablissement": 3,
    "complementAdresseEtablissement": null,
    "numeroVoieEtablissement": null,
    "indiceRepetitionEtablissement": null,
    "dernierNumeroVoieEtablissement": null,
    "indiceRepetitionDernierNumeroVoieEtablissement": null,
    "typeVoieEtablissement": null,
    "libelleVoieEtablissement": "MANIHI COTE MONTAGNE TUAMOTU",
    "codePostalEtablissement": "98770",
    "libelleCommuneEtablissement": "MANIHI",
    "libelleCommuneEtrangerEtablissement": null,
    "distributionSpecialeEtablissement": null,
    "codeCommuneEtablissement": "98727",
    "codeCedexEtablissement": null,
    "libelleCedexEtablissement": null
  },
  {
    "siren": "000325175",
    "nic": "00024",
    "siret": "00032517500024",
    "statutDiffusionEtablissement": "O",
    "dateCreationEtablissement": "2008-05-20 00:00:00",
    "trancheEffectifsEtablissement": "NN",
    "anneeEffectifsEtablissement": NaN,
    "activitePrincipaleRegistreMetiersEtablissement": null,
    "dateDernierTraitementEtablissement": "2024-03-30 05:08:28",
    "etablissementSiege": false,
    "nombrePeriodesEtablissement": 2,
    "complementAdresseEtablissement": null,
    "numeroVoieEtablissement": "1",
    "indiceRepetitionEtablissement": null,
    "dernierNumeroVoieEtablissement": null,
    "indiceRepetitionDernierNumeroVoieEtablissement": null,
    "typeVoieEtablissement": "PLACE",
    "libelleVoieEtablissement": "LEONCE DE SEYNES",
    "codePostalEtablissement": "84000",
    "libelleCommuneEtablissement": "AVIGNON",
    "libelleCommuneEtrangerEtablissement": null,
    "distributionSpecialeEtablissement": null,
    "codeCommuneEtablissement": "84007",
    "codeCedexEtablissement": null,
    "libelleCedexEtablissement": null
  }
]
```

## raw_financials

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials`

**Rows:** 6,368,964

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `siren` | `VARCHAR` | 1.0 | 1798383 |  |  |  |
| `date_cloture_exercice` | `DATE` | 1.0 | 1483 | 1919-09-30 | 2029-12-31 |  |
| `type_bilan` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 3 |  |  |  |

### Sample Rows

```json
[
  {
    "siren": "005420120",
    "date_cloture_exercice": "2018-12-31 00:00:00",
    "type_bilan": "C",
    "confidentiality": "Public"
  },
  {
    "siren": "005420120",
    "date_cloture_exercice": "2021-12-31 00:00:00",
    "type_bilan": "C",
    "confidentiality": "Public"
  }
]
```

## raw_inpi

**Status:** missing. No files were found for this dataset.

## raw_bodacc

**Status:** missing. No files were found for this dataset.

## clean_company_identity

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/company_identity`

**Rows:** 29,572,772

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `administrative_status` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `legal_category_code` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `company_name` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `creation_date` | `DATE` | 0.0 | 0 |  |  |  |
| `closure_date` | `DATE` | 0.0 | 0 |  |  |  |
| `status_period_start` | `DATE` | 0.0 | 0 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `employee_size_year` | `INTEGER` | 0.0 | 0 |  |  |  |
| `head_office_siret` | `INTEGER` | 0.0 | 0 |  |  |  |
| `source_updated_at` | `TIMESTAMP` | 0.0 | 0 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP` | 0.0 | 0 |  |  |  |

### Sample Rows

```json
[
  {
    "activity_code": null,
    "administrative_status": null,
    "legal_category_code": null,
    "siren": "005411483",
    "company_name": null,
    "creation_date": "NaT",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": null,
    "employee_size_year": NaN,
    "head_office_siret": NaN,
    "source_updated_at": "NaT",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  },
  {
    "activity_code": null,
    "administrative_status": null,
    "legal_category_code": null,
    "siren": "005420039",
    "company_name": null,
    "creation_date": "NaT",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": null,
    "employee_size_year": NaN,
    "head_office_siret": NaN,
    "source_updated_at": "NaT",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  }
]
```

## clean_financials

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/financials`

**Rows:** 6,368,964

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `closing_date` | `DATE` | 1.0 | 1483 | 1919-09-30 | 2029-12-31 |  |
| `debt` | `DOUBLE` | 0.754473 | 2404882 | -9.73595e+08 | 2.14748e+09 | 6.78954e+06 |
| `equity` | `DOUBLE` | 0.756781 | 2015394 | -2.14748e+09 | 2.14748e+09 | 5.34646e+06 |
| `financial_year` | `INTEGER` | 1.0 | 26 | 1919 | 2029 | 2019.84 |
| `net_result` | `DOUBLE` | 0.549422 | 1368891 | -2.14748e+09 | 2.14748e+09 | 532682 |
| `revenue` | `DOUBLE` | 0.474076 | 2000388 | -1.07345e+09 | 2.14748e+09 | 1.08105e+07 |
| `siren` | `VARCHAR` | 1.0 | 1798383 |  |  |  |
| `total_assets` | `DOUBLE` | 0.757039 | 2877955 | -1.03997e+09 | 2.14748e+09 | 1.09487e+07 |
| `account_type` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `total_liabilities_and_equity` | `DOUBLE` | 0.757054 | 2717464 | -1.866e+09 | 2.14748e+09 | 1.12723e+07 |
| `share_capital` | `DOUBLE` | 0.755581 | 145741 | -2.14748e+09 | 2.14748e+09 | 2.26476e+06 |
| `goods_sales` | `DOUBLE` | 0.474076 | 1849892 | -1.07345e+09 | 2.14748e+09 | 5.49374e+06 |
| `services_sales` | `DOUBLE` | 0.474076 | 319596 | -5.25e+07 | 2.14748e+09 | 1.07465e+06 |
| `net_margin` | `DOUBLE` | 0.462366 | 3571757 | -1.14478e+08 | 9.07618e+07 | -33.2725 |
| `debt_to_assets` | `DOUBLE` | 0.738798 | 5155015 | -8.49348e+08 | 2.14748e+09 | 272.08 |
| `equity_ratio` | `DOUBLE` | 0.740834 | 4797776 | -1.3978e+07 | 2.14748e+09 | 472.715 |
| `debt_to_equity` | `DOUBLE` | 0.754178 | 4196633 | -1.74633e+07 | 1.79101e+07 | 27.5461 |
| `has_negative_result` | `BOOLEAN` | 0.549422 | 2 |  |  |  |
| `has_negative_equity` | `BOOLEAN` | 0.756781 | 2 |  |  |  |
| `source` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 1 | 2026-05-09 00:22:31.058000+00:00 | 2026-05-09 00:22:31.058000+00:00 |  |

### Sample Rows

```json
[
  {
    "closing_date": "2016-10-31 00:00:00",
    "debt": 78524.0,
    "equity": 20507.0,
    "financial_year": 2016,
    "net_result": 12123.0,
    "revenue": 25077.0,
    "siren": "085480010",
    "total_assets": 163592.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 99032.0,
    "share_capital": 7622.0,
    "goods_sales": 25077.0,
    "services_sales": 0.0,
    "net_margin": 0.48343103242014596,
    "debt_to_assets": 0.4799990219570639,
    "equity_ratio": 0.12535454056433076,
    "debt_to_equity": 3.8291315160676844,
    "has_negative_result": false,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 00:22:31.058000+00:00"
  },
  {
    "closing_date": "2020-10-31 00:00:00",
    "debt": 95501.0,
    "equity": 23187.0,
    "financial_year": 2020,
    "net_result": 14802.0,
    "revenue": 33141.0,
    "siren": "085480010",
    "total_assets": 179958.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 118688.0,
    "share_capital": 7622.0,
    "goods_sales": 33141.0,
    "services_sales": 0.0,
    "net_margin": 0.4466370960441749,
    "debt_to_assets": 0.5306849375965503,
    "equity_ratio": 0.12884673090387758,
    "debt_to_equity": 4.118730323025834,
    "has_negative_result": false,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 00:22:31.058000+00:00"
  }
]
```

## clean_legal_events

**Status:** missing. No files were found for this dataset.

## clean_formalities_events

**Status:** missing. No files were found for this dataset.

## clean_annual_accounts

**Status:** missing. No files were found for this dataset.

## features_company_year

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_year_features`

**Rows:** 900,000

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `company_age_years` | `BIGINT` | 0.0 | 0 |  |  |  |
| `days_since_last_account_filing` | `BIGINT` | 0.0 | 0 |  |  |  |
| `financial_years_available` | `BIGINT` | 1.0 | 19 | 0 | 18 | 0.0308944 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.006933 | 11 | 2015 | 2025 | 2019.95 |
| `legal_category_code` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `prediction_date` | `DATE` | 1.0 | 9 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 9 | 2017 | 2025 | 2021 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.006933 | 10 | 0 | 9 | 1.13894 |
| `company_name` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `days_since_last_legal_event` | `BIGINT` | 0.0 | 0 |  |  |  |
| `formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |

### Sample Rows

```json
[
  {
    "activity_code": null,
    "annual_accounts_count_24m": 0,
    "company_age_years": NaN,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": null,
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "038963195",
    "years_since_last_financial_statement": NaN,
    "company_name": null,
    "employee_size_bracket": null,
    "administrative_status_at_cutoff": null,
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  },
  {
    "activity_code": null,
    "annual_accounts_count_24m": 0,
    "company_age_years": NaN,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": null,
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "038963427",
    "years_since_last_financial_statement": NaN,
    "company_name": null,
    "employee_size_bracket": null,
    "administrative_status_at_cutoff": null,
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  }
]
```

## features_risk_labels

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/risk_labels`

**Rows:** 900,000

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `continuity_risk_12m_label` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `filing_anomaly_risk_12m_label` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `financial_weakness_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `legal_distress_risk_12m_label` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `prediction_date` | `DATE` | 1.0 | 9 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 9 | 2017 | 2025 | 2021 |
| `radiation_risk_12m_label` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `first_future_legal_event_date` | `DATE` | 0.0 | 0 |  |  |  |

### Sample Rows

```json
[
  {
    "continuity_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "legal_distress_risk_12m_label": false,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_risk_12m_label": false,
    "siren": "001807254",
    "first_future_legal_event_date": "NaT"
  },
  {
    "continuity_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "legal_distress_risk_12m_label": false,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_risk_12m_label": false,
    "siren": "005410220",
    "first_future_legal_event_date": "NaT"
  }
]
```

## features_company

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_features`

**Rows:** 100,000

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `company_age_years` | `BIGINT` | 0.0 | 0 |  |  |  |
| `days_since_last_account_filing` | `BIGINT` | 0.0 | 0 |  |  |  |
| `financial_years_available` | `BIGINT` | 1.0 | 18 | 0 | 18 | 0.04519 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.00714 | 10 | 2016 | 2025 | 2022.2 |
| `legal_category_code` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `prediction_date` | `DATE` | 1.0 | 1 | 2025-12-31 | 2025-12-31 |  |
| `prediction_year` | `INTEGER` | 1.0 | 1 | 2025 | 2025 | 2025 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.00714 | 10 | 0 | 9 | 2.80112 |
| `company_name` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `days_since_last_legal_event` | `BIGINT` | 0.0 | 0 |  |  |  |
| `formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |

### Sample Rows

```json
[
  {
    "activity_code": null,
    "annual_accounts_count_24m": 0,
    "company_age_years": NaN,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": null,
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "042286625",
    "years_since_last_financial_statement": NaN,
    "company_name": null,
    "employee_size_bracket": null,
    "administrative_status_at_cutoff": null,
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  },
  {
    "activity_code": null,
    "annual_accounts_count_24m": 0,
    "company_age_years": NaN,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": null,
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "042286971",
    "years_since_last_financial_statement": NaN,
    "company_name": null,
    "employee_size_bracket": null,
    "administrative_status_at_cutoff": null,
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  }
]
```

## Initial Insights

- raw_insee: available with 246,453,008 rows and 110 columns.
- raw_insee: siren coverage is 0.960964; this controls join reliability.
- raw_financials: available with 6,368,964 rows and 5 columns.
- raw_financials: siren coverage is 1.0; this controls join reliability.
- raw_inpi: missing; no feature or quality conclusion can be drawn yet.
- raw_bodacc: missing; no feature or quality conclusion can be drawn yet.
- clean_company_identity: available with 29,572,772 rows and 14 columns.
- clean_company_identity: siren coverage is 1.0; this controls join reliability.
- clean_financials: available with 6,368,964 rows and 23 columns.
- clean_financials: siren coverage is 1.0; this controls join reliability.
- clean_legal_events: missing; no feature or quality conclusion can be drawn yet.
- clean_formalities_events: missing; no feature or quality conclusion can be drawn yet.
- clean_annual_accounts: missing; no feature or quality conclusion can be drawn yet.
- features_company_year: available with 900,000 rows and 41 columns.
- features_company_year: siren coverage is 1.0; this controls join reliability.
- features_risk_labels: available with 900,000 rows and 9 columns.
- features_risk_labels: siren coverage is 1.0; this controls join reliability.
- features_risk_labels: continuity_risk_12m_label coverage is 1.0.
- features_risk_labels: legal_distress_risk_12m_label coverage is 1.0.
- features_risk_labels: radiation_risk_12m_label coverage is 1.0.
- features_company: available with 100,000 rows and 41 columns.
- features_company: siren coverage is 1.0; this controls join reliability.

## Recommendations

- Do not train the final model yet; resolve or document the blockers above first.
- Add BODACC historical `PCL` and `RCS-B` archives to improve legal distress and radiation labels.
- Add INPI formalities and annual accounts to improve registry activity and filing-behavior features.
- Review high-coverage feature columns first; sparse columns should become missingness or recency features before model use.

## How This Improves Feature Selection

Columns with high coverage and clear temporal meaning are stronger candidates for the first model. Columns with weak coverage may still be useful, but they should be transformed into robust features such as missingness indicators, counts, recency variables, or source-availability flags. Raw source lineage columns should remain available for auditability but should not be used directly as model inputs.
