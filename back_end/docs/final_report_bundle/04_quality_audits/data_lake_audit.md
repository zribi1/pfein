# Data Lake Audit Report

> This report is generated automatically from the Parquet data lake. It is intended to support data validation, feature selection, and the decision to train or postpone model training.

## Executive View

| Item | Value |
|---|---:|
| Generated at | `2026-05-14T22:31:08.432739+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |
| Datasets available | 12 / 12 |
| Datasets missing | 0 |
| Total profiled rows | 927,525,347 |
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
- `feature_siren_quality`: **pass** `{"rows": 220803039, "valid_siren": 220803039, "null_siren": 0, "valid_rate": 1.0, "ok": true}`
- `label_duplicate_company_year`: **pass** `{"key": ["siren", "prediction_year"], "duplicate_keys": 0, "duplicate_rows": 0, "ok": true}`

### Label Balance By Year

| prediction_year | rows | continuity_risk_12m_label_positive | continuity_risk_12m_label_rate | legal_distress_risk_12m_label_positive | legal_distress_risk_12m_label_rate | radiation_risk_12m_label_positive | radiation_risk_12m_label_rate | financial_weakness_risk_12m_label_positive | financial_weakness_risk_12m_label_rate | filing_anomaly_risk_12m_label_positive | filing_anomaly_risk_12m_label_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2017 | 20335854 | 267724 | 0.013165 | 98385 | 0.004838 | 183011 | 0.008999 | 126013 | 0.006197 | 183456 | 0.009021 |
| 2018 | 21182127 | 305713 | 0.014433 | 97381 | 0.004597 | 226507 | 0.010693 | 122314 | 0.005774 | 311184 | 0.014691 |
| 2019 | 22168852 | 261502 | 0.011796 | 78601 | 0.003546 | 205961 | 0.009291 | 137819 | 0.006217 | 293788 | 0.013252 |
| 2020 | 23178651 | 307792 | 0.013279 | 68244 | 0.002944 | 248837 | 0.010736 | 116197 | 0.005013 | 253426 | 0.010934 |
| 2021 | 24391406 | 366175 | 0.015012 | 73980 | 0.003033 | 309982 | 0.012709 | 120467 | 0.004939 | 264093 | 0.010827 |
| 2022 | 25592352 | 335820 | 0.013122 | 91317 | 0.003568 | 263689 | 0.010303 | 119991 | 0.004689 | 294704 | 0.011515 |
| 2023 | 26772040 | 364494 | 0.013615 | 107413 | 0.004012 | 279698 | 0.010447 | 105978 | 0.003959 | 262362 | 0.0098 |
| 2024 | 27970861 | 478464 | 0.017106 | 118922 | 0.004252 | 384481 | 0.013746 | 10043 | 0.000359 | 297161 | 0.010624 |
| 2025 | 29210896 | 304 | 1e-05 | 0 | 0.0 | 304 | 1e-05 | 0 | 0.0 | 774215 | 0.026504 |
- `label_siren_quality`: **pass** `{"rows": 220803039, "valid_siren": 220803039, "null_siren": 0, "valid_rate": 1.0, "ok": true}`

## Dataset Summary

| Dataset | Status | Rows | Files | Columns | Main Role |
|---|---:|---:|---:|---:|---|
| `raw_insee` | **available** | 246,453,008 | 5 | 110 | identity source |
| `raw_financials` | **available** | 6,368,964 | 1 | 5 | financial source |
| `raw_inpi` | **available** | 66,141,121 | 663 | 14 | registry source |
| `raw_bodacc` | **available** | 17,923,111 | 2660 | 41 | legal event source |
| `clean_company_identity` | **available** | 29,572,772 | 1 | 14 | normalized identity |
| `clean_financials` | **available** | 6,368,963 | 1 | 23 | normalized financials |
| `clean_legal_events` | **available** | 17,739,313 | 35 | 17 | normalized legal events |
| `clean_formalities_events` | **available** | 53,544,636 | 5 | 10 | normalized registry events |
| `clean_annual_accounts` | **available** | 12,596,485 | 29 | 12 | normalized filings |
| `features_company_year` | **available** | 220,803,039 | 9 | 41 | model features |
| `features_risk_labels` | **available** | 220,803,039 | 9 | 9 | model labels |
| `features_company` | **available** | 29,210,896 | 1 | 41 | latest company snapshot |

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

**Rows:** 66,141,121

**Files:** 663

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `date_cloture` | `VARCHAR` | 0.190449 | 1763 |  |  |  |
| `date_depot` | `VARCHAR` | 0.190449 | 3349 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 26522538 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 74423382 |  |  |  |
| `denomination` | `VARCHAR` | 0.525532 | 7816245 |  |  |  |
| `category` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `niveau` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 4 |  |  |  |
| `inpi_id` | `VARCHAR` | 1.0 | 35852950 |  |  |  |
| `updated_at_source` | `VARCHAR` | 1.0 | 6571303 |  |  |  |
| `type_bilan` | `VARCHAR` | 0.190449 | 9 |  |  |  |
| `confidentiality` | `VARCHAR` | 0.190449 | 3 |  |  |  |
| `deleted` | `BOOLEAN` | 0.190449 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 69928583 | 2026-05-13 07:48:39.779894+00:00 | 2026-05-13 13:21:10.368956+00:00 |  |

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
    "exported_at": "2026-05-13 08:23:04.596137+00:00"
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
    "exported_at": "2026-05-13 08:23:04.596320+00:00"
  }
]
```

## raw_bodacc

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/raw/bodacc`

**Rows:** 17,923,111

**Files:** 2660

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `date_parution` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 3132 | 2017-01-03 00:00:00+00:00 | 2025-12-31 00:00:00+00:00 |  |
| `event_date` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 3132 | 2017-01-03 00:00:00+00:00 | 2025-12-31 00:00:00+00:00 |  |
| `siren` | `VARCHAR` | 0.989745 | 7108938 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 13070699 |  |  |  |
| `nojo` | `VARCHAR` | 1.0 | 13070699 |  |  |  |
| `denomination` | `VARCHAR` | 0.864485 | 3800263 |  |  |  |
| `nom` | `VARCHAR` | 0.135513 | 532880 |  |  |  |
| `prenom` | `VARCHAR` | 0.135513 | 696060 |  |  |  |
| `personne_type` | `VARCHAR` | 0.587404 | 2 |  |  |  |
| `bodacc_family` | `VARCHAR` | 1.0 | 5 |  |  |  |
| `bodacc_edition` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `event_category` | `VARCHAR` | 1.0 | 5 |  |  |  |
| `event_type` | `VARCHAR` | 0.999932 | 48 |  |  |  |
| `jugement_date` | `TIMESTAMP WITH TIME ZONE` | 0.080454 | 4698 | 1930-03-29 00:00:00+00:00 | 2026-08-16 00:00:00+00:00 |  |
| `date_cessation_paiement` | `TIMESTAMP WITH TIME ZONE` | 0.022334 | 5345 | 1917-10-16 00:00:00+00:00 | 2026-11-30 00:00:00+00:00 |  |
| `date_cloture_comptes` | `TIMESTAMP WITH TIME ZONE` | 0.412559 | 1307 | 1993-12-31 00:00:00+00:00 | 2025-11-30 00:00:00+00:00 |  |
| `numero_annonce` | `VARCHAR` | 1.0 | 34779 |  |  |  |
| `numero_departement` | `VARCHAR` | 1.0 | 99 |  |  |  |
| `tribunal` | `VARCHAR` | 1.0 | 914 |  |  |  |
| `greffe` | `VARCHAR` | 0.989745 | 1406 |  |  |  |
| `forme_juridique` | `VARCHAR` | 0.861591 | 2303 |  |  |  |
| `activite` | `VARCHAR` | 0.342116 | 3779401 |  |  |  |
| `adresse` | `VARCHAR` | 0.930614 | 5047925 |  |  |  |
| `code_postal` | `VARCHAR` | 0.929566 | 11750 |  |  |  |
| `ville` | `VARCHAR` | 0.929566 | 73773 |  |  |  |

### Sample Rows

```json
[
  {
    "date_parution": "2017-01-03 00:00:00+00:00",
    "event_date": "2017-01-03 00:00:00+00:00",
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
    "event_date": "2017-01-03 00:00:00+00:00",
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
| `creation_date` | `DATE` | 0.960365 | 32187 | 1900-01-01 | 2027-04-20 |  |
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
    "activity_code": "01.43Z",
    "administrative_status": "A",
    "legal_category_code": "6597",
    "siren": "884783044",
    "company_name": "ELEVAGE DE CUVELETTE SCEA",
    "creation_date": "2020-07-01 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": NaN,
    "head_office_siret": "88478304400016",
    "source_updated_at": "2025-12-06 11:05:43",
    "source_file": "/content/pfe_work/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  },
  {
    "activity_code": "66.30Z",
    "administrative_status": "A",
    "legal_category_code": "5499",
    "siren": "884783242",
    "company_name": "MARGUERITE BLEUE",
    "creation_date": "2019-07-31 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": NaN,
    "head_office_siret": "88478324200016",
    "source_updated_at": "2025-12-06 10:16:21",
    "source_file": "/content/pfe_work/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  }
]
```

## clean_financials

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/financials`

**Rows:** 6,368,963

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `closing_date` | `DATE` | 1.0 | 1483 | 1919-09-30 | 2026-01-10 |  |
| `debt` | `DOUBLE` | 0.754473 | 2404882 | -9.73595e+08 | 2.14748e+09 | 6.78954e+06 |
| `equity` | `DOUBLE` | 0.756781 | 2015394 | -2.14748e+09 | 2.14748e+09 | 5.34646e+06 |
| `financial_year` | `INTEGER` | 1.0 | 24 | 1919 | 2026 | 2019.84 |
| `net_result` | `DOUBLE` | 0.549422 | 1368891 | -2.14748e+09 | 2.14748e+09 | 532682 |
| `revenue` | `DOUBLE` | 0.474076 | 2000388 | -1.07345e+09 | 2.14748e+09 | 1.08105e+07 |
| `siren` | `VARCHAR` | 1.0 | 1798383 |  |  |  |
| `total_assets` | `DOUBLE` | 0.757039 | 2877955 | -1.03997e+09 | 2.14748e+09 | 1.09487e+07 |
| `account_type` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `total_liabilities_and_equity` | `DOUBLE` | 0.757054 | 2717464 | -1.866e+09 | 2.14748e+09 | 1.12723e+07 |
| `share_capital` | `DOUBLE` | 0.755581 | 145741 | -2.14748e+09 | 2.14748e+09 | 2.26476e+06 |
| `goods_sales` | `DOUBLE` | 0.474076 | 1849892 | -1.07345e+09 | 2.14748e+09 | 5.49375e+06 |
| `services_sales` | `DOUBLE` | 0.474076 | 319596 | -5.25e+07 | 2.14748e+09 | 1.07465e+06 |
| `net_margin` | `DOUBLE` | 0.462366 | 3571757 | -1.14478e+08 | 9.07618e+07 | -33.2726 |
| `debt_to_assets` | `DOUBLE` | 0.738798 | 5155015 | -8.49348e+08 | 2.14748e+09 | 272.08 |
| `equity_ratio` | `DOUBLE` | 0.740834 | 4797776 | -1.3978e+07 | 2.14748e+09 | 472.715 |
| `debt_to_equity` | `DOUBLE` | 0.754178 | 4196633 | -1.74633e+07 | 1.79101e+07 | 27.5461 |
| `has_negative_result` | `BOOLEAN` | 0.549422 | 2 |  |  |  |
| `has_negative_equity` | `BOOLEAN` | 0.756781 | 2 |  |  |  |
| `source` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 1 | 2026-05-14 21:20:01.482000+00:00 | 2026-05-14 21:20:01.482000+00:00 |  |

### Sample Rows

```json
[
  {
    "closing_date": "2018-12-31 00:00:00",
    "debt": 1464579374.0,
    "equity": 317376298.0,
    "financial_year": 2018,
    "net_result": 23176851.0,
    "revenue": 518852407.0,
    "siren": "313606477",
    "total_assets": 2147483647.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 1784974528.0,
    "share_capital": 14040000.0,
    "goods_sales": 518852407.0,
    "services_sales": 0.0,
    "net_margin": 0.044669448743638575,
    "debt_to_assets": 0.681997916978783,
    "equity_ratio": 0.14778985555646468,
    "debt_to_equity": 4.614646346401079,
    "has_negative_result": false,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/pfe_work/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-14 21:20:01.482000+00:00"
  },
  {
    "closing_date": "2022-12-31 00:00:00",
    "debt": 1745638967.0,
    "equity": 516236440.0,
    "financial_year": 2022,
    "net_result": 58679022.0,
    "revenue": 613230744.0,
    "siren": "313606477",
    "total_assets": 2147483647.0,
    "account_type": "C",
    "confidentiality": "Public",
    "total_liabilities_and_equity": 2147483647.0,
    "share_capital": 14040000.0,
    "goods_sales": 613230744.0,
    "services_sales": 0.0,
    "net_margin": 0.09568832380654418,
    "debt_to_assets": 0.8128764889262973,
    "equity_ratio": 0.24039132531750543,
    "debt_to_equity": 3.381471805826028,
    "has_negative_result": false,
    "has_negative_equity": false,
    "source": "data_gouv_financial_parquet",
    "source_file": "/content/pfe_work/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-14 21:20:01.482000+00:00"
  }
]
```

## clean_legal_events

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/legal_events`

**Rows:** 17,739,313

**Files:** 35

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `event_date` | `DATE` | 1.0 | 2185 | 2017-01-03 | 2025-12-31 |  |
| `siren` | `VARCHAR` | 1.0 | 7108938 |  |  |  |
| `event_type` | `VARCHAR` | 0.999945 | 48 |  |  |  |
| `is_risk_event` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `is_radiation` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_liquidation` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_redressement` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_sauvegarde` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_procedure_collective` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_cessation_paiement` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `nojo` | `VARCHAR` | 1.0 | 13070699 |  |  |  |
| `denomination` | `VARCHAR` | 0.86922 | 3800263 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 2657 |  |  |  |
| `source_member` | `VARCHAR` | 1.0 | 5953 |  |  |  |
| `exported_at` | `TIMESTAMP` | 1.0 | 14275198 | 2026-05-14 19:08:50.328959 | 2026-05-14 21:10:57.726653 |  |
| `event_category` | `VARCHAR` | 1.0 | 4 |  |  |  |
| `event_year` | `BIGINT` | 1.0 | 10 | 2017 | 2025 | 2022.54 |

### Sample Rows

```json
[
  {
    "event_date": "2017-01-03 00:00:00",
    "siren": "390432326",
    "event_type": "liquidation_judiciaire",
    "is_risk_event": true,
    "is_radiation": false,
    "flag_liquidation": true,
    "flag_redressement": false,
    "flag_sauvegarde": false,
    "flag_procedure_collective": true,
    "flag_cessation_paiement": true,
    "nojo": "002016122600100",
    "denomination": "ASSOCIATION AIDE AUX DEPLACEMENTS EN THIERACHE",
    "source_file": "PCL_BXA20170001.taz",
    "source_member": "PCL_BXA20170001.xml",
    "exported_at": "2026-05-14 19:08:50.328959",
    "event_category": "procedure_collective",
    "event_year": 2017
  },
  {
    "event_date": "2017-01-03 00:00:00",
    "siren": "500105242",
    "event_type": "liquidation_judiciaire",
    "is_risk_event": true,
    "is_radiation": false,
    "flag_liquidation": true,
    "flag_redressement": false,
    "flag_sauvegarde": false,
    "flag_procedure_collective": true,
    "flag_cessation_paiement": true,
    "nojo": "002016122600098",
    "denomination": "SCI VIDAL",
    "source_file": "PCL_BXA20170001.taz",
    "source_member": "PCL_BXA20170001.xml",
    "exported_at": "2026-05-14 19:08:50.328983",
    "event_category": "procedure_collective",
    "event_year": 2017
  }
]
```

## clean_formalities_events

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/formalities_events`

**Rows:** 53,544,636

**Files:** 5

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `event_date` | `DATE` | 1.0 | 663 | 2024-01-04 | 2026-03-05 |  |
| `siren` | `VARCHAR` | 1.0 | 26522538 |  |  |  |
| `event_type` | `VARCHAR` | 1.0 | 1 |  |  |  |
| `event_text` | `VARCHAR` | 1.0 | 7440802 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 66088658 |  |  |  |
| `inpi_id` | `VARCHAR` | 1.0 | 28794234 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `exported_at` | `TIMESTAMP` | 1.0 | 57951921 | 2026-05-13 08:58:14.916779 | 2026-05-13 13:21:10.368956 |  |
| `event_year` | `BIGINT` | 1.0 | 3 | 2024 | 2026 | 2024.25 |
| `niveau` | `VARCHAR` | 1.0 | 2 |  |  |  |

### Sample Rows

```json
[
  {
    "event_date": "2024-07-05 00:00:00",
    "siren": "307136309",
    "event_type": "formalites",
    "event_text": "formalites",
    "record_key": "276be03916b2d3a8ea1f7e70a690f9ed607522a5cd7f15dcd37a1428617d11bb",
    "inpi_id": "63a493e4f5da5674900bfc91",
    "source_file": "stock_RNE_formalites_NIVEAU1_20260304_1400.zip",
    "exported_at": "2026-05-13 11:01:55.060713",
    "event_year": 2024,
    "niveau": "niveau1"
  },
  {
    "event_date": "2024-07-05 00:00:00",
    "siren": "307136663",
    "event_type": "formalites",
    "event_text": "formalites",
    "record_key": "86498e89588542dcd1907285d5d049e5fdd7dacfc0d8199bd9dfd180348bab15",
    "inpi_id": "63a493e8f5da5674900bfca5",
    "source_file": "stock_RNE_formalites_NIVEAU1_20260304_1400.zip",
    "exported_at": "2026-05-13 11:01:55.060955",
    "event_year": 2024,
    "niveau": "niveau1"
  }
]
```

## clean_annual_accounts

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/annual_accounts`

**Rows:** 12,596,485

**Files:** 29

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `closing_date` | `DATE` | 1.0 | 1964 | 1919-09-30 | 2026-02-28 |  |
| `filing_date` | `DATE` | 1.0 | 4172 | 2012-09-06 | 2026-03-13 |  |
| `siren` | `VARCHAR` | 1.0 | 1823790 |  |  |  |
| `account_type` | `VARCHAR` | 1.0 | 9 |  |  |  |
| `confidentiality` | `VARCHAR` | 1.0 | 3 |  |  |  |
| `record_key` | `VARCHAR` | 1.0 | 14994139 |  |  |  |
| `inpi_id` | `VARCHAR` | 1.0 | 7617973 |  |  |  |
| `deleted` | `BOOLEAN` | 1.0 | 1 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 2 |  |  |  |
| `exported_at` | `TIMESTAMP` | 1.0 | 11438935 | 2026-05-13 07:48:39.779894 | 2026-05-13 08:58:11.719224 |  |
| `filing_year` | `BIGINT` | 1.0 | 17 | 2012 | 2026 | 2020.97 |
| `niveau` | `VARCHAR` | 1.0 | 2 |  |  |  |

### Sample Rows

```json
[
  {
    "closing_date": "2012-06-30 00:00:00",
    "filing_date": "2012-10-26 00:00:00",
    "siren": "338211915",
    "account_type": "C",
    "confidentiality": "Public",
    "record_key": "295974b59d5be9b91129c67037022594dc095aacb2778aa8c496d9829718d653",
    "inpi_id": "649e1458335d69d7bd0b4c88",
    "deleted": false,
    "source_file": "stock_RNE_comptes_annuels_NIVEAU1_20260320_1400.zip",
    "exported_at": "2026-05-13 08:25:33.850483",
    "filing_year": 2012,
    "niveau": "niveau1"
  },
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
    "exported_at": "2026-05-13 08:30:04.522670",
    "filing_year": 2012,
    "niveau": "niveau1"
  }
]
```

## features_company_year

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_year_features`

**Rows:** 220,803,039

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.996555 | 2691 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 43 | 0 | 59 | 0.107632 |
| `company_age_years` | `BIGINT` | 0.949657 | 128 | 0 | 125 | 19.2373 |
| `days_since_last_account_filing` | `BIGINT` | 0.047768 | 4023 | 0 | 4811 | 657.432 |
| `financial_years_available` | `BIGINT` | 1.0 | 26 | 0 | 26 | 0.172845 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.052405 | 20 | 2004 | 2025 | 2019.72 |
| `legal_category_code` | `VARCHAR` | 0.997432 | 253 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0217716 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 59 | 0 | 142 | 0.0802437 |
| `prediction_date` | `DATE` | 1.0 | 10 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 10 | 2017 | 2025 | 2021.31 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 27 | 0 | 123 | 0.0474769 |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.052405 | 21 | 0 | 18 | 1.7207 |
| `company_name` | `VARCHAR` | 0.997403 | 9438428 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.997432 | 17 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.997432 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 118 | 0 | 267 | 0.277875 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0223274 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 10 | 0 | 22 | 0.00456688 |
| `days_since_last_legal_event` | `BIGINT` | 0.136406 | 3139 | 0 | 3284 | 702.333 |
| `formalities_count_all` | `BIGINT` | 1.0 | 5 | 0 | 4 | 0.42451 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 5 | 0 | 4 | 0.234788 |

### Sample Rows

```json
[
  {
    "activity_code": "55.20Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 19,
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
    "siren": "419841218",
    "years_since_last_financial_statement": NaN,
    "company_name": "[ND]",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 0,
    "formalities_count_12m": 0
  },
  {
    "activity_code": "43.21A",
    "annual_accounts_count_24m": 0,
    "company_age_years": 19,
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
    "siren": "419842968",
    "years_since_last_financial_statement": NaN,
    "company_name": "EMLEK",
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

## features_risk_labels

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/risk_labels`

**Rows:** 220,803,039

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `continuity_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `filing_anomaly_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `financial_weakness_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `legal_distress_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `prediction_date` | `DATE` | 1.0 | 10 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 10 | 2017 | 2025 | 2021.31 |
| `radiation_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `first_future_legal_event_date` | `DATE` | 0.051962 | 1900 | 2018-01-03 | 2025-12-31 |  |

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
    "siren": "831636485",
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
    "siren": "831636519",
    "first_future_legal_event_date": "NaT"
  }
]
```

## features_company

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_features`

**Rows:** 29,210,896

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.997107 | 2691 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 39 | 0 | 59 | 0.0934271 |
| `company_age_years` | `BIGINT` | 0.957717 | 128 | 0 | 125 | 19.4531 |
| `days_since_last_account_filing` | `BIGINT` | 0.054081 | 3694 | 0 | 4811 | 1065.9 |
| `financial_years_available` | `BIGINT` | 1.0 | 26 | 0 | 26 | 0.218033 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.053413 | 20 | 2009 | 2025 | 2021.48 |
| `legal_category_code` | `VARCHAR` | 0.997843 | 253 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0336568 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 35 | 0 | 130 | 0.129912 |
| `prediction_date` | `DATE` | 1.0 | 1 | 2025-12-31 | 2025-12-31 |  |
| `prediction_year` | `INTEGER` | 1.0 | 1 | 2025 | 2025 | 2025 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 20 | 0 | 123 | 0.0813382 |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.053413 | 20 | 0 | 16 | 3.52311 |
| `company_name` | `VARCHAR` | 0.997819 | 9438428 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.997843 | 17 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.997843 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 85 | 0 | 267 | 0.607096 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0345209 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 6 | 0 | 5 | 0.00497581 |
| `days_since_last_legal_event` | `BIGINT` | 0.237015 | 2575 | 0 | 3284 | 873.025 |
| `formalities_count_all` | `BIGINT` | 1.0 | 5 | 0 | 4 | 1.77595 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 5 | 0 | 4 | 0.34185 |

### Sample Rows

```json
[
  {
    "activity_code": "03.20",
    "annual_accounts_count_24m": 0,
    "company_age_years": 46,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "1000",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "315890467",
    "years_since_last_financial_statement": NaN,
    "company_name": "GUINOT",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "C",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 2,
    "formalities_count_12m": 0
  },
  {
    "activity_code": "43.99C",
    "annual_accounts_count_24m": 0,
    "company_age_years": 46,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "1000",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "315901694",
    "years_since_last_financial_statement": NaN,
    "company_name": "DURAND",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "C",
    "legal_events_count_all": 0,
    "legal_risk_events_count_all": 0,
    "legal_risk_events_count_12m": 0,
    "days_since_last_legal_event": NaN,
    "formalities_count_all": 2,
    "formalities_count_12m": 0
  }
]
```

## Initial Insights

- raw_insee: available with 246,453,008 rows and 110 columns.
- raw_insee: siren coverage is 0.960964; this controls join reliability.
- raw_financials: available with 6,368,964 rows and 5 columns.
- raw_financials: siren coverage is 1.0; this controls join reliability.
- raw_inpi: available with 66,141,121 rows and 14 columns.
- raw_inpi: siren coverage is 1.0; this controls join reliability.
- raw_bodacc: available with 17,923,111 rows and 41 columns.
- raw_bodacc: siren coverage is 0.989745; this controls join reliability.
- clean_company_identity: available with 29,572,772 rows and 14 columns.
- clean_company_identity: siren coverage is 1.0; this controls join reliability.
- clean_financials: available with 6,368,963 rows and 23 columns.
- clean_financials: siren coverage is 1.0; this controls join reliability.
- clean_legal_events: available with 17,739,313 rows and 17 columns.
- clean_legal_events: siren coverage is 1.0; this controls join reliability.
- clean_formalities_events: available with 53,544,636 rows and 10 columns.
- clean_formalities_events: siren coverage is 1.0; this controls join reliability.
- clean_annual_accounts: available with 12,596,485 rows and 12 columns.
- clean_annual_accounts: siren coverage is 1.0; this controls join reliability.
- features_company_year: available with 220,803,039 rows and 41 columns.
- features_company_year: siren coverage is 1.0; this controls join reliability.
- features_risk_labels: available with 220,803,039 rows and 9 columns.
- features_risk_labels: siren coverage is 1.0; this controls join reliability.
- features_risk_labels: continuity_risk_12m_label coverage is 1.0.
- features_risk_labels: legal_distress_risk_12m_label coverage is 1.0.
- features_risk_labels: radiation_risk_12m_label coverage is 1.0.
- features_company: available with 29,210,896 rows and 41 columns.
- features_company: siren coverage is 1.0; this controls join reliability.

## Recommendations

- Review high-coverage feature columns first; sparse columns should become missingness or recency features before model use.

## How This Improves Feature Selection

Columns with high coverage and clear temporal meaning are stronger candidates for the first model. Columns with weak coverage may still be useful, but they should be transformed into robust features such as missingness indicators, counts, recency variables, or source-availability flags. Raw source lineage columns should remain available for auditability but should not be used directly as model inputs.
