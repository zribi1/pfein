# Data Lake Audit Report

> This report is generated automatically from the Parquet data lake. It is intended to support data validation, feature selection, and the decision to train or postpone model training.

## Executive View

| Item | Value |
|---|---:|
| Generated at | `2026-05-09T10:36:03.514043+00:00` |
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
| `siren` | `VARCHAR` | 0.960964 | 27866277 |  |  |  |
| `nic` | `VARCHAR` | 0.557674 | 56470 |  |  |  |
| `siret` | `VARCHAR` | 0.557674 | 36732586 |  |  |  |
| `statutDiffusionEtablissement` | `VARCHAR` | 0.175756 | 2 |  |  |  |
| `dateCreationEtablissement` | `DATE` | 0.161848 | 31031 | 0001-01-16 | 5015-04-05 |  |
| `trancheEffectifsEtablissement` | `VARCHAR` | 0.175756 | 17 |  |  |  |
| `anneeEffectifsEtablissement` | `BIGINT` | 0.010077 | 1 | 2023 | 2023 | 2023 |
| `activitePrincipaleRegistreMetiersEtablissement` | `VARCHAR` | 0.012412 | 594 |  |  |  |
| `dateDernierTraitementEtablissement` | `TIMESTAMP` | 0.175756 | 3418664 | 2024-03-22 15:40:57 | 2026-04-30 23:55:58 |  |
| `etablissementSiege` | `BOOLEAN` | 0.175756 | 2 |  |  |  |
| `nombrePeriodesEtablissement` | `BIGINT` | 0.175756 | 47 | 1 | 52 | 2.17301 |
| `complementAdresseEtablissement` | `VARCHAR` | 0.050256 | 3351631 |  |  |  |
| `numeroVoieEtablissement` | `VARCHAR` | 0.143248 | 9946 |  |  |  |
| `indiceRepetitionEtablissement` | `VARCHAR` | 0.027507 | 41 |  |  |  |
| `dernierNumeroVoieEtablissement` | `VARCHAR` | 0.021783 | 493 |  |  |  |
| `indiceRepetitionDernierNumeroVoieEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `typeVoieEtablissement` | `VARCHAR` | 0.155159 | 636 |  |  |  |
| `libelleVoieEtablissement` | `VARCHAR` | 0.172446 | 2111185 |  |  |  |
| `codePostalEtablissement` | `VARCHAR` | 0.174522 | 18767 |  |  |  |
| `libelleCommuneEtablissement` | `VARCHAR` | 0.174293 | 40552 |  |  |  |
| `libelleCommuneEtrangerEtablissement` | `VARCHAR` | 0.001342 | 122612 |  |  |  |
| `distributionSpecialeEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `codeCommuneEtablissement` | `VARCHAR` | 0.174293 | 36792 |  |  |  |
| `codeCedexEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `libelleCedexEtablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `codePaysEtrangerEtablissement` | `VARCHAR` | 0.001449 | 193 |  |  |  |
| `libellePaysEtrangerEtablissement` | `VARCHAR` | 0.001449 | 291 |  |  |  |
| `identifiantAdresseEtablissement` | `VARCHAR` | 0.140302 | 2504579 |  |  |  |
| `coordonneeLambertAbscisseEtablissement` | `VARCHAR` | 0.132779 | 10233407 |  |  |  |
| `coordonneeLambertOrdonneeEtablissement` | `VARCHAR` | 0.132779 | 9602988 |  |  |  |
| `complementAdresse2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `numeroVoie2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `indiceRepetition2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `typeVoie2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `libelleVoie2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `codePostal2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `libelleCommune2Etablissement` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `libelleCommuneEtranger2Etablissement` | `VARCHAR` | 0.0 | 0 |  |  |  |
| `distributionSpeciale2Etablissement` | `VARCHAR` | 0.021717 | 1 |  |  |  |
| `codeCommune2Etablissement` | `VARCHAR` | 0.0 | 0 |  |  |  |

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
    "anneeEffectifsEtablissement": null,
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
    "libelleCedexEtablissement": null,
    "codePaysEtrangerEtablissement": null,
    "libellePaysEtrangerEtablissement": null,
    "identifiantAdresseEtablissement": null,
    "coordonneeLambertAbscisseEtablissement": null,
    "coordonneeLambertOrdonneeEtablissement": null,
    "complementAdresse2Etablissement": null,
    "numeroVoie2Etablissement": null,
    "indiceRepetition2Etablissement": null,
    "typeVoie2Etablissement": null,
    "libelleVoie2Etablissement": null,
    "codePostal2Etablissement": null,
    "libelleCommune2Etablissement": null,
    "libelleCommuneEtranger2Etablissement": null,
    "distributionSpeciale2Etablissement": null,
    "codeCommune2Etablissement": null
  },
  {
    "siren": "000325175",
    "nic": "00024",
    "siret": "00032517500024",
    "statutDiffusionEtablissement": "O",
    "dateCreationEtablissement": "2008-05-20 00:00:00",
    "trancheEffectifsEtablissement": "NN",
    "anneeEffectifsEtablissement": null,
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
    "libelleCedexEtablissement": null,
    "codePaysEtrangerEtablissement": null,
    "libellePaysEtrangerEtablissement": null,
    "identifiantAdresseEtablissement": "84007cvsr_B",
    "coordonneeLambertAbscisseEtablissement": "851150.0982592739",
    "coordonneeLambertOrdonneeEtablissement": "6317267.146094748",
    "complementAdresse2Etablissement": null,
    "numeroVoie2Etablissement": null,
    "indiceRepetition2Etablissement": null,
    "typeVoie2Etablissement": null,
    "libelleVoie2Etablissement": null,
    "codePostal2Etablissement": null,
    "libelleCommune2Etablissement": null,
    "libelleCommuneEtranger2Etablissement": null,
    "distributionSpeciale2Etablissement": null,
    "codeCommune2Etablissement": null
  },
  {
    "siren": "000325175",
    "nic": "00032",
    "siret": "00032517500032",
    "statutDiffusionEtablissement": "O",
    "dateCreationEtablissement": "2009-05-27 00:00:00",
    "trancheEffectifsEtablissement": "NN",
    "anneeEffectifsEtablissement": null,
    "activitePrincipaleRegistreMetiersEtablissement": null,
    "dateDernierTraitementEtablissement": "2024-03-30 05:56:39",
    "etablissementSiege": false,
    "nombrePeriodesEtablissement": 2,
    "complementAdresseEtablissement": "ECONOMIS",
    "numeroVoieEtablissement": "6",
    "indiceRepetitionEtablissement": null,
    "dernierNumeroVoieEtablissement": null,
    "indiceRepetitionDernierNumeroVoieEtablissement": null,
    "typeVoieEtablissement": "AVENUE",
    "libelleVoieEtablissement": "FRANCOIS MAURIAC",
    "codePostalEtablissement": "84000",
    "libelleCommuneEtablissement": "AVIGNON",
    "libelleCommuneEtrangerEtablissement": null,
    "distributionSpecialeEtablissement": null,
    "codeCommuneEtablissement": "84007",
    "codeCedexEtablissement": null,
    "libelleCedexEtablissement": null,
    "codePaysEtrangerEtablissement": null,
    "libellePaysEtrangerEtablissement": null,
    "identifiantAdresseEtablissement": "840072225_B",
    "coordonneeLambertAbscisseEtablissement": "848084.2366812509",
    "coordonneeLambertOrdonneeEtablissement": "6316548.347114814",
    "complementAdresse2Etablissement": null,
    "numeroVoie2Etablissement": null,
    "indiceRepetition2Etablissement": null,
    "typeVoie2Etablissement": null,
    "libelleVoie2Etablissement": null,
    "codePostal2Etablissement": null,
    "libelleCommune2Etablissement": null,
    "libelleCommuneEtranger2Etablissement": null,
    "distributionSpeciale2Etablissement": null,
    "codeCommune2Etablissement": null
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
| `siren` | `VARCHAR` | 1.0 | 1563939 |  |  |  |
| `date_cloture_exercice` | `DATE` | 1.0 | 1483 | 1919-09-30 | 2029-12-31 |  |
| `type_bilan` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 4 |  |  |  |

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
  },
  {
    "siren": "005420120",
    "date_cloture_exercice": "2017-12-31 00:00:00",
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
| `activity_code` | `VARCHAR` | 0.999272 | 1996 |  |  |  |
| `administrative_status` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `legal_category_code` | `VARCHAR` | 1.0 | 291 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 27866277 |  |  |  |
| `company_name` | `VARCHAR` | 0.999976 | 9358245 |  |  |  |
| `creation_date` | `DATE` | 0.960367 | 32187 | 0001-01-16 | 2028-01-01 |  |
| `closure_date` | `DATE` | 0.0 | 0 |  |  |  |
| `status_period_start` | `DATE` | 0.0 | 0 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 1.0 | 17 |  |  |  |
| `employee_size_year` | `INTEGER` | 0.067926 | 1 | 2023 | 2023 | 2023 |
| `head_office_siret` | `VARCHAR` | 1.0 | 25394787 |  |  |  |
| `source_updated_at` | `TIMESTAMP` | 1.0 | 2826147 | 2024-03-22 14:26:06 | 2026-04-30 23:55:58 |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP` | 0.0 | 0 |  |  |  |

### Sample Rows

```json
[
  {
    "activity_code": "60.2L",
    "administrative_status": "C",
    "legal_category_code": "1000",
    "siren": "419976220",
    "company_name": "DE OLIVEIRA",
    "creation_date": "1998-09-01 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": null,
    "head_office_siret": "41997622000014",
    "source_updated_at": "2024-03-22 14:26:06",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  },
  {
    "activity_code": "21.2L",
    "administrative_status": "C",
    "legal_category_code": "5599",
    "siren": "419976444",
    "company_name": "TUBILAIRE",
    "creation_date": "1998-08-27 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": null,
    "head_office_siret": "41997644400010",
    "source_updated_at": "2024-03-22 14:26:06",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  },
  {
    "activity_code": "94.99Z",
    "administrative_status": "A",
    "legal_category_code": "9220",
    "siren": "419976485",
    "company_name": "COMITE DEPARTEMENTAL TOURISME FLUVIAL",
    "creation_date": "1998-02-02 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": null,
    "head_office_siret": "41997648500013",
    "source_updated_at": "2025-12-06 10:19:17",
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
| `siren` | `VARCHAR` | 1.0 | 1563939 |  |  |  |
| `total_assets` | `DOUBLE` | 0.757039 | 2877955 | -1.03997e+09 | 2.14748e+09 | 1.09487e+07 |
| `account_type` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 4 |  |  |  |
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
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 1 | 2026-05-09 10:24:54.446000+00:00 | 2026-05-09 10:24:54.446000+00:00 |  |

### Sample Rows

```json
[
  {
    "closing_date": "2018-12-31 00:00:00",
    "debt": 4341098.0,
    "equity": 90269342.0,
    "financial_year": 2018,
    "net_result": -289131.0,
    "revenue": 135797.0,
    "siren": "005420120",
    "total_assets": 102067174.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 97498351.0,
    "share_capital": 711840.0,
    "goods_sales": 135797.0,
    "services_sales": 0.0,
    "net_margin": -2.1291412917811146,
    "debt_to_assets": 0.042531774221553346,
    "equity_ratio": 0.884411103612999,
    "debt_to_equity": 0.04809050231029711,
    "has_negative_result": true,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 10:24:54.446000+00:00"
  },
  {
    "closing_date": "2021-12-31 00:00:00",
    "debt": 3346300.0,
    "equity": 86469939.0,
    "financial_year": 2021,
    "net_result": -1974866.0,
    "revenue": 271605.0,
    "siren": "005420120",
    "total_assets": 96128752.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 92582739.0,
    "share_capital": 711840.0,
    "goods_sales": 271605.0,
    "services_sales": 0.0,
    "net_margin": -7.271095892932752,
    "debt_to_assets": 0.034810604843803654,
    "equity_ratio": 0.8995221221638247,
    "debt_to_equity": 0.038698998041388696,
    "has_negative_result": true,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 10:24:54.446000+00:00"
  },
  {
    "closing_date": "2017-12-31 00:00:00",
    "debt": 9001422.0,
    "equity": 90919571.0,
    "financial_year": 2017,
    "net_result": -376691.0,
    "revenue": 98112.0,
    "siren": "005420120",
    "total_assets": 107166241.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 102937095.0,
    "share_capital": 711840.0,
    "goods_sales": 98112.0,
    "services_sales": 0.0,
    "net_margin": -3.839397831050228,
    "debt_to_assets": 0.08399494016030663,
    "equity_ratio": 0.8483975004777857,
    "debt_to_equity": 0.09900422869351198,
    "has_negative_result": true,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 10:24:54.446000+00:00"
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
| `activity_code` | `VARCHAR` | 0.99798 | 1170 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `company_age_years` | `BIGINT` | 0.90285 | 103 | 7 | 125 | 30.6733 |
| `days_since_last_account_filing` | `BIGINT` | 0.0 | 0 |  |  |  |
| `financial_years_available` | `BIGINT` | 1.0 | 19 | 0 | 18 | 0.0308944 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.006933 | 11 | 2015 | 2025 | 2019.95 |
| `legal_category_code` | `VARCHAR` | 1.0 | 77 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `prediction_date` | `DATE` | 1.0 | 9 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 9 | 2017 | 2025 | 2021 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.006933 | 10 | 0 | 9 | 1.13894 |
| `company_name` | `VARCHAR` | 0.99999 | 85332 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 1.0 | 14 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `days_since_last_legal_event` | `BIGINT` | 0.0 | 0 |  |  |  |
| `formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `cessation_formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `annual_accounts_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `latest_account_closing_year` | `BIGINT` | 0.0 | 0 |  |  |  |
| `latest_revenue` | `DOUBLE` | 0.005766 | 2745 | -13944 | 2.14748e+09 | 1.99098e+07 |
| `latest_net_result` | `DOUBLE` | 0.005978 | 2902 | -1.61801e+08 | 2.14748e+09 | 1.78812e+06 |
| `latest_equity` | `DOUBLE` | 0.006643 | 3779 | -7.99e+08 | 8.851e+08 | 6.88054e+06 |
| `latest_debt` | `DOUBLE` | 0.006638 | 3770 | 337 | 2.14748e+09 | 1.11539e+07 |
| `latest_total_assets` | `DOUBLE` | 0.006643 | 3738 | 0 | 8.73444e+08 | 1.97766e+07 |
| `latest_net_margin` | `DOUBLE` | 0.005742 | 2763 | -4474.78 | 627.15 | -5.17977 |
| `latest_debt_to_assets` | `DOUBLE` | 0.006622 | 3747 | 5.28926e-05 | 101.87 | 0.409906 |
| `latest_equity_ratio` | `DOUBLE` | 0.006627 | 3749 | -24.3876 | 1 | 0.289914 |
| `latest_debt_to_equity` | `DOUBLE` | 0.006638 | 3778 | -313.842 | 471.64 | 1.13622 |
| `has_negative_result_history` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_negative_equity_history` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `revenue_growth_1y` | `DOUBLE` | 0.003389 | 2273 | -38.1391 | 7526.91 | 2.52463 |

### Sample Rows

```json
[
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 22,
    "days_since_last_account_filing": null,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": null,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "038790689",
    "years_since_last_financial_statement": null,
    "company_name": "SYND.COPR. 67 RUE DE NORMANDIE  92 COURB",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": null,
    "formalities_count_all": 0,
    "formalities_count_12m": 0,
    "cessation_formalities_count_all": 0,
    "annual_accounts_count_all": 0,
    "latest_account_closing_year": null,
    "latest_revenue": NaN,
    "latest_net_result": NaN,
    "latest_equity": NaN,
    "latest_debt": NaN,
    "latest_total_assets": NaN,
    "latest_net_margin": NaN,
    "latest_debt_to_assets": NaN,
    "latest_equity_ratio": NaN,
    "latest_debt_to_equity": NaN,
    "has_negative_result_history": false,
    "has_negative_equity_history": false,
    "revenue_growth_1y": NaN
  },
  {
    "activity_code": "70.3C",
    "annual_accounts_count_24m": 0,
    "company_age_years": 20,
    "days_since_last_account_filing": null,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": null,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "038866703",
    "years_since_last_financial_statement": null,
    "company_name": "SYNDICAT DE COPROPRIETE RES BEAUVALLON",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "C",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": null,
    "formalities_count_all": 0,
    "formalities_count_12m": 0,
    "cessation_formalities_count_all": 0,
    "annual_accounts_count_all": 0,
    "latest_account_closing_year": null,
    "latest_revenue": NaN,
    "latest_net_result": NaN,
    "latest_equity": NaN,
    "latest_debt": NaN,
    "latest_total_assets": NaN,
    "latest_net_margin": NaN,
    "latest_debt_to_assets": NaN,
    "latest_equity_ratio": NaN,
    "latest_debt_to_equity": NaN,
    "has_negative_result_history": false,
    "has_negative_equity_history": false,
    "revenue_growth_1y": NaN
  },
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 22,
    "days_since_last_account_filing": null,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": null,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "038979332",
    "years_since_last_financial_statement": null,
    "company_name": "SYND.COPR. 12 AV. PARMENTIER    75011 PA",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": null,
    "formalities_count_all": 0,
    "formalities_count_12m": 0,
    "cessation_formalities_count_all": 0,
    "annual_accounts_count_all": 0,
    "latest_account_closing_year": null,
    "latest_revenue": NaN,
    "latest_net_result": NaN,
    "latest_equity": NaN,
    "latest_debt": NaN,
    "latest_total_assets": NaN,
    "latest_net_margin": NaN,
    "latest_debt_to_assets": NaN,
    "latest_equity_ratio": NaN,
    "latest_debt_to_equity": NaN,
    "has_negative_result_history": false,
    "has_negative_equity_history": false,
    "revenue_growth_1y": NaN
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
    "siren": "043819408",
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
    "siren": "043819416",
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
    "siren": "043819424",
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
| `activity_code` | `VARCHAR` | 0.99798 | 1170 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `company_age_years` | `BIGINT` | 0.90285 | 79 | 15 | 125 | 34.6733 |
| `days_since_last_account_filing` | `BIGINT` | 0.0 | 0 |  |  |  |
| `financial_years_available` | `BIGINT` | 1.0 | 18 | 0 | 18 | 0.04519 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.00714 | 10 | 2016 | 2025 | 2022.2 |
| `legal_category_code` | `VARCHAR` | 1.0 | 77 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `prediction_date` | `DATE` | 1.0 | 1 | 2025-12-31 | 2025-12-31 |  |
| `prediction_year` | `INTEGER` | 1.0 | 1 | 2025 | 2025 | 2025 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.00714 | 10 | 0 | 9 | 2.80112 |
| `company_name` | `VARCHAR` | 0.99999 | 85332 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 1.0 | 14 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `days_since_last_legal_event` | `BIGINT` | 0.0 | 0 |  |  |  |
| `formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `cessation_formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `annual_accounts_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `latest_account_closing_year` | `BIGINT` | 0.0 | 0 |  |  |  |
| `latest_revenue` | `DOUBLE` | 0.00612 | 599 | -13944 | 2.14748e+09 | 2.11842e+07 |
| `latest_net_result` | `DOUBLE` | 0.00632 | 631 | -1.61801e+08 | 1.0539e+09 | 1.72916e+06 |
| `latest_equity` | `DOUBLE` | 0.00689 | 689 | -4.56882e+07 | 8.851e+08 | 7.54666e+06 |
| `latest_debt` | `DOUBLE` | 0.00689 | 689 | 997 | 2.14748e+09 | 1.19793e+07 |
| `latest_total_assets` | `DOUBLE` | 0.00689 | 681 | 0 | 8.73444e+08 | 2.15304e+07 |
| `latest_net_margin` | `DOUBLE` | 0.0061 | 610 | -4474.78 | 627.15 | -5.81066 |
| `latest_debt_to_assets` | `DOUBLE` | 0.00688 | 688 | 0.000872596 | 22.523 | 0.393703 |
| `latest_equity_ratio` | `DOUBLE` | 0.00688 | 688 | -24.3876 | 1 | 0.291362 |
| `latest_debt_to_equity` | `DOUBLE` | 0.00689 | 689 | -313.842 | 113.565 | 0.558743 |
| `has_negative_result_history` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_negative_equity_history` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `revenue_growth_1y` | `DOUBLE` | 0.00239 | 33 | -0.974142 | 0.314838 | -0.0152976 |

### Sample Rows

```json
[
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 31,
    "days_since_last_account_filing": null,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": null,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "038596979",
    "years_since_last_financial_statement": null,
    "company_name": "COPR 5 7 R KURNAGEL",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": null,
    "formalities_count_all": 0,
    "formalities_count_12m": 0,
    "cessation_formalities_count_all": 0,
    "annual_accounts_count_all": 0,
    "latest_account_closing_year": null,
    "latest_revenue": NaN,
    "latest_net_result": NaN,
    "latest_equity": NaN,
    "latest_debt": NaN,
    "latest_total_assets": NaN,
    "latest_net_margin": NaN,
    "latest_debt_to_assets": NaN,
    "latest_equity_ratio": NaN,
    "latest_debt_to_equity": NaN,
    "has_negative_result_history": false,
    "has_negative_equity_history": false,
    "revenue_growth_1y": NaN
  },
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 31,
    "days_since_last_account_filing": null,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": null,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "038597308",
    "years_since_last_financial_statement": null,
    "company_name": "COPR 12 R CESAR JULIEN",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": null,
    "formalities_count_all": 0,
    "formalities_count_12m": 0,
    "cessation_formalities_count_all": 0,
    "annual_accounts_count_all": 0,
    "latest_account_closing_year": null,
    "latest_revenue": NaN,
    "latest_net_result": NaN,
    "latest_equity": NaN,
    "latest_debt": NaN,
    "latest_total_assets": NaN,
    "latest_net_margin": NaN,
    "latest_debt_to_assets": NaN,
    "latest_equity_ratio": NaN,
    "latest_debt_to_equity": NaN,
    "has_negative_result_history": false,
    "has_negative_equity_history": false,
    "revenue_growth_1y": NaN
  },
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 31,
    "days_since_last_account_filing": null,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": null,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "038597431",
    "years_since_last_financial_statement": null,
    "company_name": "COPR 10 R LOUIS APFFEL",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": null,
    "formalities_count_all": 0,
    "formalities_count_12m": 0,
    "cessation_formalities_count_all": 0,
    "annual_accounts_count_all": 0,
    "latest_account_closing_year": null,
    "latest_revenue": NaN,
    "latest_net_result": NaN,
    "latest_equity": NaN,
    "latest_debt": NaN,
    "latest_total_assets": NaN,
    "latest_net_margin": NaN,
    "latest_debt_to_assets": NaN,
    "latest_equity_ratio": NaN,
    "latest_debt_to_equity": NaN,
    "has_negative_result_history": false,
    "has_negative_equity_history": false,
    "revenue_growth_1y": NaN
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
