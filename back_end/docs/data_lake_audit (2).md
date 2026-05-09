# Data Lake Audit Report

> This report is generated automatically from the Parquet data lake. It is intended to support data validation, feature selection, and the decision to train or postpone model training.

## Executive View

| Item | Value |
|---|---:|
| Generated at | `2026-05-09T18:53:57.640037+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |
| Datasets available | 11 / 12 |
| Datasets missing | 1 |
| Total profiled rows | 311,473,153 |
| Training ready | **yes** |

## Purpose

This report profiles raw, clean, and feature Parquet datasets before final model training. It is used to understand schema coverage, missingness, date ranges, join quality, and which columns are reliable enough to become model features.

## Readiness Gate

**Decision:** the audited data lake passes the basic readiness gate for a baseline training run.

| Check | OK | Meaning |
|---|---:|---|
| `insee_raw` | **pass** | INSEE raw data is required for company identity and administrative status. |
| `financials` | **pass** | Financial raw or clean data is required for accounting features. |
| `bodacc` | **pass** | BODACC raw data is required for legal distress and radiation labels. |
| `features` | **pass** | Feature and label tables are required before training. |
| `continuity_label_column` | **pass** | The primary continuity-risk label must exist. |

## Quality Checks

- `feature_duplicate_company_year`: **pass** `{"key": ["siren", "prediction_year"], "duplicate_keys": 0, "duplicate_rows": 0, "ok": true}`
- `feature_siren_quality`: **pass** `{"rows": 900000, "valid_siren": 900000, "null_siren": 0, "valid_rate": 1.0, "ok": true}`
- `label_duplicate_company_year`: **pass** `{"key": ["siren", "prediction_year"], "duplicate_keys": 0, "duplicate_rows": 0, "ok": true}`

### Label Balance By Year

| prediction_year | rows | continuity_risk_12m_label_positive | continuity_risk_12m_label_rate | legal_distress_risk_12m_label_positive | legal_distress_risk_12m_label_rate | radiation_risk_12m_label_positive | radiation_risk_12m_label_rate | financial_weakness_risk_12m_label_positive | financial_weakness_risk_12m_label_rate | filing_anomaly_risk_12m_label_positive | filing_anomaly_risk_12m_label_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2017 | 100000 | 119 | 0.00119 | 31 | 0.00031 | 93 | 0.00093 | 98 | 0.00098 | 102 | 0.00102 |
| 2018 | 100000 | 204 | 0.00204 | 21 | 0.00021 | 187 | 0.00187 | 99 | 0.00099 | 124 | 0.00124 |
| 2019 | 100000 | 72 | 0.00072 | 14 | 0.00014 | 63 | 0.00063 | 121 | 0.00121 | 128 | 0.00128 |
| 2020 | 100000 | 56 | 0.00056 | 11 | 0.00011 | 45 | 0.00045 | 76 | 0.00076 | 130 | 0.0013 |
| 2021 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 73 | 0.00073 | 114 | 0.00114 |
| 2022 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 70 | 0.0007 | 98 | 0.00098 |
| 2023 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 55 | 0.00055 | 95 | 0.00095 |
| 2024 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 8 | 8e-05 | 88 | 0.00088 |
| 2025 | 100000 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 0 | 0.0 | 431 | 0.00431 |
- `label_siren_quality`: **pass** `{"rows": 900000, "valid_siren": 900000, "null_siren": 0, "valid_rate": 1.0, "ok": true}`

## Dataset Summary

| Dataset | Status | Rows | Files | Columns | Main Role |
|---|---:|---:|---:|---:|---|
| `raw_insee` | **available** | 246,453,008 | 5 | 110 | identity source |
| `raw_financials` | **available** | 6,368,964 | 1 | 5 | financial source |
| `raw_inpi` | **available** | 6,287,057 | 63 | 14 | registry source |
| `raw_bodacc` | **available** | 4,164,036 | 2520 | 41 | legal event source |
| `clean_company_identity` | **available** | 29,572,772 | 1 | 14 | normalized identity |
| `clean_financials` | **available** | 6,368,964 | 1 | 23 | normalized financials |
| `clean_legal_events` | **available** | 4,071,295 | 770 | 17 | normalized legal events |
| `clean_formalities_events` | **missing** | 0 | 0 | 0 | normalized registry events |
| `clean_annual_accounts` | **available** | 6,287,057 | 15 | 12 | normalized filings |
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

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/inpi`

**Rows:** 6,287,057

**Files:** 63

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `date_cloture` | `VARCHAR` | 1.0 | 1669 |  |  |  |
| `date_depot` | `VARCHAR` | 1.0 | 3349 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 1765587 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 6224338 |  |  |  |
| `denomination` | `VARCHAR` | 1.0 | 1569287 |  |  |  |
| `category` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `niveau` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `inpi_id` | `VARCHAR` | 1.0 | 7263029 |  |  |  |
| `updated_at_source` | `VARCHAR` | 1.0 | 1963971 |  |  |  |
| `type_bilan` | `VARCHAR` | 1.0 | 9 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `deleted` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 7530668 | 2026-05-09 16:41:22.751628+00:00 | 2026-05-09 17:01:41.671524+00:00 |  |

### Sample Rows

```json
[
  {
    "date_cloture": "2016-12-31",
    "date_depot": "2017-11-10",
    "siren": "005880596",
    "record_key": "a0bbc0000314fa23b08a09f5911a913c70f70287a7a79870095d304d56aea2a9",
    "denomination": "GEDIMO HOLDING",
    "category": "comptes_annuels",
    "niveau": "niveau1",
    "source_file": "stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip",
    "inpi_id": "63ec89b3c90370f18005a937",
    "updated_at_source": "2023-06-24T15:51:50+02:00",
    "type_bilan": "C",
    "confidentiality": "Public",
    "deleted": false,
    "exported_at": "2026-05-09 16:41:22.751628+00:00"
  },
  {
    "date_cloture": "2017-12-31",
    "date_depot": "2019-01-21",
    "siren": "005880596",
    "record_key": "a3c5d4fceab18d61450d04348d84079cc6e1c7678f7cebebddb1ba3786b6cbcf",
    "denomination": "GEDIMO HOLDING",
    "category": "comptes_annuels",
    "niveau": "niveau1",
    "source_file": "stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip",
    "inpi_id": "63ec89b3c90370f18005a938",
    "updated_at_source": "2023-06-24T15:51:50+02:00",
    "type_bilan": "C",
    "confidentiality": "Public",
    "deleted": false,
    "exported_at": "2026-05-09 16:41:22.751731+00:00"
  }
]
```

## raw_bodacc

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/bodacc`

**Rows:** 4,164,036

**Files:** 2520

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `date_parution` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 1261 | 2017-01-03 00:00:00+00:00 | 2021-12-31 00:00:00+00:00 |  |
| `event_date` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 14347 | 0017-08-03 00:00:00+00:00 | 9970-01-13 00:00:00+00:00 |  |
| `siren` | `VARCHAR` | 0.977728 | 2456668 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 3245169 |  |  |  |
| `nojo` | `VARCHAR` | 1.0 | 3245169 |  |  |  |
| `denomination` | `VARCHAR` | 0.836027 | 1784539 |  |  |  |
| `nom` | `VARCHAR` | 0.163971 | 210467 |  |  |  |
| `prenom` | `VARCHAR` | 0.163971 | 213910 |  |  |  |
| `personne_type` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `bodacc_family` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `bodacc_edition` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `event_category` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `event_type` | `VARCHAR` | 0.999816 | 43 |  |  |  |
| `jugement_date` | `TIMESTAMP WITH TIME ZONE` | 0.192084 | 2461 | 0017-08-03 00:00:00+00:00 | 3019-06-20 00:00:00+00:00 |  |
| `date_cessation_paiement` | `TIMESTAMP WITH TIME ZONE` | 0.046498 | 3044 | 0017-01-15 00:00:00+00:00 | 5017-11-17 00:00:00+00:00 |  |
| `date_cloture_comptes` | `TIMESTAMP WITH TIME ZONE` | 0.0 | 0 |  |  |  |
| `numero_annonce` | `VARCHAR` | 1.0 | 10102 |  |  |  |
| `numero_departement` | `VARCHAR` | 1.0 | 103 |  |  |  |
| `tribunal` | `VARCHAR` | 1.0 | 733 |  |  |  |
| `greffe` | `VARCHAR` | 0.977728 | 930 |  |  |  |
| `forme_juridique` | `VARCHAR` | 0.831928 | 1596 |  |  |  |
| `activite` | `VARCHAR` | 0.38348 | 835692 |  |  |  |
| `adresse` | `VARCHAR` | 0.791215 | 1567595 |  |  |  |
| `code_postal` | `VARCHAR` | 0.789444 | 10076 |  |  |  |
| `ville` | `VARCHAR` | 0.789444 | 49411 |  |  |  |

### Sample Rows

```json
[
  {
    "date_parution": "2017-01-03 00:00:00+00:00",
    "event_date": "2016-12-14 00:00:00+00:00",
    "siren": "390432326",
    "record_key": "002016122600100",
    "nojo": "002016122600100",
    "denomination": "ASSOCIATION AIDE AUX DEPLACEMENTS EN THIERACHE",
    "nom": null,
    "prenom": null,
    "personne_type": "morale",
    "bodacc_family": "PCL",
    "bodacc_edition": "A",
    "event_category": "procedure_collective",
    "event_type": "liquidation_judiciaire",
    "jugement_date": "2016-12-14 00:00:00+00:00",
    "date_cessation_paiement": "2016-12-14 00:00:00+00:00",
    "date_cloture_comptes": "NaT",
    "numero_annonce": "1106",
    "numero_departement": "02",
    "tribunal": "TRIBUNAL DE GRANDE INSTANCE DE LAON",
    "greffe": "Laon",
    "forme_juridique": "Association",
    "activite": "non précisée",
    "adresse": "rue du Hautbert Maison du Quartier",
    "code_postal": "02500",
    "ville": "Hirson"
  },
  {
    "date_parution": "2017-01-03 00:00:00+00:00",
    "event_date": "2016-12-14 00:00:00+00:00",
    "siren": "500105242",
    "record_key": "002016122600098",
    "nojo": "002016122600098",
    "denomination": "SCI VIDAL",
    "nom": null,
    "prenom": null,
    "personne_type": "morale",
    "bodacc_family": "PCL",
    "bodacc_edition": "A",
    "event_category": "procedure_collective",
    "event_type": "liquidation_judiciaire",
    "jugement_date": "2016-12-14 00:00:00+00:00",
    "date_cessation_paiement": "2016-12-14 00:00:00+00:00",
    "date_cloture_comptes": "NaT",
    "numero_annonce": "1107",
    "numero_departement": "02",
    "tribunal": "TRIBUNAL DE GRANDE INSTANCE DE LAON",
    "greffe": "Laon",
    "forme_juridique": "S.C.I.",
    "activite": "non précisée",
    "adresse": "5 Bis avenue du Général de Gaulle",
    "code_postal": "02700",
    "ville": "Tergnier"
  }
]
```

## clean_company_identity

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/company_identity`

**Rows:** 29,572,772

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.999272 | 2691 |  |  |  |
| `administrative_status` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `legal_category_code` | `VARCHAR` | 1.0 | 253 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `company_name` | `VARCHAR` | 0.999976 | 10457938 |  |  |  |
| `creation_date` | `DATE` | 0.960367 | 32187 | 0001-01-16 | 2028-01-01 |  |
| `closure_date` | `DATE` | 0.0 | 0 |  |  |  |
| `status_period_start` | `DATE` | 0.0 | 0 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 1.0 | 17 |  |  |  |
| `employee_size_year` | `INTEGER` | 0.067926 | 1 | 2023 | 2023 | 2023 |
| `head_office_siret` | `VARCHAR` | 1.0 | 32719884 |  |  |  |
| `source_updated_at` | `TIMESTAMP` | 1.0 | 2826147 | 2024-03-22 14:26:06 | 2026-04-30 23:55:58 |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP` | 0.0 | 0 |  |  |  |

### Sample Rows

```json
[
  {
    "activity_code": "62.11",
    "administrative_status": "C",
    "legal_category_code": "1000",
    "siren": "005410519",
    "company_name": "ANDRIEUX",
    "creation_date": "1954-12-25 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": NaN,
    "head_office_siret": "00541051900010",
    "source_updated_at": "2024-03-22 14:26:06",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  },
  {
    "activity_code": "38.40",
    "administrative_status": "C",
    "legal_category_code": "1000",
    "siren": "005471784",
    "company_name": "JAHAN",
    "creation_date": "1954-12-25 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": NaN,
    "head_office_siret": "00547178400016",
    "source_updated_at": "2024-03-22 14:26:06",
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
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 1 | 2026-05-09 17:27:20.362000+00:00 | 2026-05-09 17:27:20.362000+00:00 |  |

### Sample Rows

```json
[
  {
    "closing_date": "2018-03-31 00:00:00",
    "debt": NaN,
    "equity": 30726000.0,
    "financial_year": 2018,
    "net_result": 1483000.0,
    "revenue": 22929000.0,
    "siren": "306140039",
    "total_assets": 147073000.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 143241000.0,
    "share_capital": 15139000.0,
    "goods_sales": 0.0,
    "services_sales": 0.0,
    "net_margin": 0.06467791879279515,
    "debt_to_assets": NaN,
    "equity_ratio": 0.20891666043393417,
    "debt_to_equity": NaN,
    "has_negative_result": false,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 17:27:20.362000+00:00"
  },
  {
    "closing_date": "2018-03-31 00:00:00",
    "debt": 189761000.0,
    "equity": 58391000.0,
    "financial_year": 2018,
    "net_result": NaN,
    "revenue": 162512000.0,
    "siren": "306140039",
    "total_assets": 337653000.0,
    "account_type": "K",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 331721000.0,
    "share_capital": 15139000.0,
    "goods_sales": 0.0,
    "services_sales": 0.0,
    "net_margin": NaN,
    "debt_to_assets": 0.5620000414626851,
    "equity_ratio": 0.17293197454191137,
    "debt_to_equity": 3.2498330222123273,
    "has_negative_result": NaN,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-09 17:27:20.362000+00:00"
  }
]
```

## clean_legal_events

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/legal_events`

**Rows:** 4,071,295

**Files:** 770

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `event_date` | `DATE` | 1.0 | 14339 | 0017-08-03 | 9970-01-13 |  |
| `siren` | `VARCHAR` | 1.0 | 2456668 |  |  |  |
| `event_type` | `VARCHAR` | 0.999853 | 42 |  |  |  |
| `is_risk_event` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `is_radiation` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_liquidation` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_redressement` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_sauvegarde` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_procedure_collective` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_cessation_paiement` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `nojo` | `VARCHAR` | 1.0 | 3166170 |  |  |  |
| `denomination` | `VARCHAR` | 0.850177 | 1773768 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 2520 |  |  |  |
| `source_member` | `VARCHAR` | 1.0 | 2520 |  |  |  |
| `exported_at` | `TIMESTAMP` | 1.0 | 4071295 | 2026-05-09 12:19:56.238167 | 2026-05-09 13:05:22.234413 |  |
| `event_category` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `event_year` | `BIGINT` | 1.0 | 152 | 17 | 9970 | 2018.68 |

### Sample Rows

```json
[
  {
    "event_date": "1198-11-11 00:00:00",
    "siren": "420291221",
    "event_type": "radiation_rcs",
    "is_risk_event": false,
    "is_radiation": true,
    "flag_liquidation": false,
    "flag_redressement": false,
    "flag_sauvegarde": false,
    "flag_procedure_collective": false,
    "flag_cessation_paiement": false,
    "nojo": "000005002153105",
    "denomination": null,
    "source_file": "RCS-B_BXB20180249.taz",
    "source_member": "RCS-B_BXB20180249.xml",
    "exported_at": "2026-05-09 12:36:41.338417",
    "event_category": "radiation",
    "event_year": 1198
  },
  {
    "event_date": "0017-08-03 00:00:00",
    "siren": "504988924",
    "event_type": "depot_de_l_etat_des_creances_et_du_projet_de_repartition",
    "is_risk_event": false,
    "is_radiation": false,
    "flag_liquidation": false,
    "flag_redressement": false,
    "flag_sauvegarde": false,
    "flag_procedure_collective": false,
    "flag_cessation_paiement": false,
    "nojo": "860218602400280",
    "denomination": null,
    "source_file": "PCL_BXA20170163.taz",
    "source_member": "PCL_BXA20170163.xml",
    "exported_at": "2026-05-09 12:21:54.509127",
    "event_category": "procedure_collective",
    "event_year": 17
  }
]
```

## clean_formalities_events

**Status:** missing. No files were found for this dataset.

## clean_annual_accounts

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/annual_accounts`

**Rows:** 6,287,057

**Files:** 15

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `closing_date` | `DATE` | 1.0 | 1964 | 1919-09-30 | 2029-12-31 |  |
| `filing_date` | `DATE` | 1.0 | 4172 | 2012-09-06 | 2026-03-13 |  |
| `siren` | `VARCHAR` | 1.0 | 1765587 |  |  |  |
| `account_type` | `VARCHAR` | 1.0 | 9 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 6224338 |  |  |  |
| `inpi_id` | `VARCHAR` | 1.0 | 7263029 |  |  |  |
| `deleted` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP` | 1.0 | 7530668 | 2026-05-09 16:41:22.751628 | 2026-05-09 17:01:41.671524 |  |
| `filing_year` | `BIGINT` | 1.0 | 17 | 2012 | 2026 | 2021.1 |
| `niveau` | `VARCHAR` | 1.0 | 1 |  |  |  |

### Sample Rows

```json
[
  {
    "closing_date": "2012-06-30 00:00:00",
    "filing_date": "2012-11-27 00:00:00",
    "siren": "409144177",
    "account_type": "C",
    "confidentiality": "Public",
    "record_key": "0e5f2c02cdb6cf8ed51dc0c5754a7b30bb592108ae3ac8d66fbdbf4898df174e",
    "inpi_id": "63ec66b93fdc867bc5119f5e",
    "deleted": false,
    "source_file": "stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip",
    "exported_at": "2026-05-09 16:45:34.025848",
    "filing_year": 2012,
    "niveau": "niveau1"
  },
  {
    "closing_date": "2012-03-31 00:00:00",
    "filing_date": "2012-10-05 00:00:00",
    "siren": "411652977",
    "account_type": "S",
    "confidentiality": "Public",
    "record_key": "b6ffaeaff268e4b811a4ae676c2915d015f5952f00ac7c0f1460dfb0aff733d1",
    "inpi_id": "63e62e1a54febda17c088bda",
    "deleted": false,
    "source_file": "stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip",
    "exported_at": "2026-05-09 16:45:43.973859",
    "filing_year": 2012,
    "niveau": "niveau1"
  }
]
```

## features_company_year

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_year_features`

**Rows:** 900,000

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.99722 | 1170 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 11 | 0 | 14 | 0.00990889 |
| `company_age_years` | `BIGINT` | 0.90209 | 103 | 7 | 125 | 30.6774 |
| `days_since_last_account_filing` | `BIGINT` | 0.006697 | 1495 | 0 | 3283 | 481.484 |
| `financial_years_available` | `BIGINT` | 1.0 | 19 | 0 | 18 | 0.0308944 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.006933 | 11 | 2015 | 2025 | 2019.95 |
| `legal_category_code` | `VARCHAR` | 0.99924 | 77 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 9 | 0 | 17 | 0.00121889 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 11 | 0 | 45 | 0.00263111 |
| `prediction_date` | `DATE` | 1.0 | 9 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 9 | 2017 | 2025 | 2021 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 8 | 0 | 123 | 0.00603778 |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.006933 | 10 | 0 | 9 | 1.13894 |
| `company_name` | `VARCHAR` | 0.99923 | 85259 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.99924 | 14 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.99924 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 18 | 0 | 147 | 0.0196389 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 9 | 0 | 17 | 0.00125222 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 6 | 0 | 7 | 0.000158889 |
| `days_since_last_legal_event` | `BIGINT` | 0.010956 | 2636 | 0 | 732781 | 2817.89 |
| `formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |

### Sample Rows

```json
[
  {
    "activity_code": "62.43",
    "annual_accounts_count_24m": 0,
    "company_age_years": 59,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "5599",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "015851637",
    "years_since_last_financial_statement": NaN,
    "company_name": "CHARCUTERIE BOUGAULT",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "C",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  },
  {
    "activity_code": "55.4B",
    "annual_accounts_count_24m": 0,
    "company_age_years": 58,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "1000",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2017-12-31 00:00:00",
    "prediction_year": 2017,
    "radiation_events_count_all": 0,
    "siren": "015971179",
    "years_since_last_financial_statement": NaN,
    "company_name": "SOULET",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "C",
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
| `continuity_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `filing_anomaly_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `financial_weakness_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `legal_distress_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `prediction_date` | `DATE` | 1.0 | 9 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 9 | 2017 | 2025 | 2021 |
| `radiation_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `first_future_legal_event_date` | `DATE` | 0.00144 | 585 | 2018-01-04 | 2021-12-28 |  |

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
    "siren": "043818228",
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
    "siren": "043818236",
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
| `activity_code` | `VARCHAR` | 0.99722 | 1170 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 7 | 0 | 7 | 0.00937 |
| `company_age_years` | `BIGINT` | 0.90209 | 79 | 15 | 125 | 34.6774 |
| `days_since_last_account_filing` | `BIGINT` | 0.0072 | 463 | 1 | 3283 | 827.001 |
| `financial_years_available` | `BIGINT` | 1.0 | 18 | 0 | 18 | 0.04519 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.00714 | 10 | 2016 | 2025 | 2022.2 |
| `legal_category_code` | `VARCHAR` | 0.99924 | 77 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 6 | 0 | 17 | 0.00143 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `prediction_date` | `DATE` | 1.0 | 1 | 2025-12-31 | 2025-12-31 |  |
| `prediction_year` | `INTEGER` | 1.0 | 1 | 2025 | 2025 | 2025 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 5 | 0 | 123 | 0.0072 |
| `siren` | `VARCHAR` | 1.0 | 100000 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.00714 | 10 | 0 | 9 | 2.80112 |
| `company_name` | `VARCHAR` | 0.99923 | 85259 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.99924 | 14 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.99924 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 15 | 0 | 147 | 0.02431 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 6 | 0 | 17 | 0.00147 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `days_since_last_legal_event` | `BIGINT` | 0.01284 | 613 | 1464 | 732781 | 3654.83 |
| `formalities_count_all` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 1 | 0 | 0 | 0 |

### Sample Rows

```json
[
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 30,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "019763242",
    "years_since_last_financial_statement": NaN,
    "company_name": "CTIM SOLEIL",
    "employee_size_bracket": "01",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  },
  {
    "activity_code": "81.10Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 30,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "9110",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "019763382",
    "years_since_last_financial_statement": NaN,
    "company_name": "CTIM JARDINS DE CIMIEZ",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
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
- raw_inpi: available with 6,287,057 rows and 14 columns.
- raw_inpi: siren coverage is 1.0; this controls join reliability.
- raw_bodacc: available with 4,164,036 rows and 41 columns.
- raw_bodacc: siren coverage is 0.977728; this controls join reliability.
- clean_company_identity: available with 29,572,772 rows and 14 columns.
- clean_company_identity: siren coverage is 1.0; this controls join reliability.
- clean_financials: available with 6,368,964 rows and 23 columns.
- clean_financials: siren coverage is 1.0; this controls join reliability.
- clean_legal_events: available with 4,071,295 rows and 17 columns.
- clean_legal_events: siren coverage is 1.0; this controls join reliability.
- clean_formalities_events: missing; no feature or quality conclusion can be drawn yet.
- clean_annual_accounts: available with 6,287,057 rows and 12 columns.
- clean_annual_accounts: siren coverage is 1.0; this controls join reliability.
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

- Review high-coverage feature columns first; sparse columns should become missingness or recency features before model use.

## How This Improves Feature Selection

Columns with high coverage and clear temporal meaning are stronger candidates for the first model. Columns with weak coverage may still be useful, but they should be transformed into robust features such as missingness indicators, counts, recency variables, or source-availability flags. Raw source lineage columns should remain available for auditability but should not be used directly as model inputs.
