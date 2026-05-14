# Data Lake Audit Report

> This report is generated automatically from the Parquet data lake. It is intended to support data validation, feature selection, and the decision to train or postpone model training.

## Executive View

| Item | Value |
|---|---:|
| Generated at | `2026-05-14T03:15:20.157966+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |
| Datasets available | 12 / 12 |
| Datasets missing | 0 |
| Total profiled rows | 1,026,848,823 |
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
- `feature_siren_quality`: **pass** `{"rows": 266721894, "valid_siren": 266721894, "null_siren": 0, "valid_rate": 1.0, "ok": true}`
- `label_duplicate_company_year`: **pass** `{"key": ["siren", "prediction_year"], "duplicate_keys": 0, "duplicate_rows": 0, "ok": true}`

### Label Balance By Year

| prediction_year | rows | continuity_risk_12m_label_positive | continuity_risk_12m_label_rate | legal_distress_risk_12m_label_positive | legal_distress_risk_12m_label_rate | radiation_risk_12m_label_positive | radiation_risk_12m_label_rate | financial_weakness_risk_12m_label_positive | financial_weakness_risk_12m_label_rate | filing_anomaly_risk_12m_label_positive | filing_anomaly_risk_12m_label_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2017 | 29635766 | 275401 | 0.009293 | 97980 | 0.003306 | 190954 | 0.006443 | 131125 | 0.004425 | 183470 | 0.006191 |
| 2018 | 29635766 | 309626 | 0.010448 | 97429 | 0.003288 | 230214 | 0.007768 | 127294 | 0.004295 | 311206 | 0.010501 |
| 2019 | 29635766 | 270443 | 0.009126 | 78353 | 0.002644 | 215089 | 0.007258 | 142038 | 0.004793 | 293812 | 0.009914 |
| 2020 | 29635766 | 320376 | 0.01081 | 67789 | 0.002287 | 261719 | 0.008831 | 121629 | 0.004104 | 253448 | 0.008552 |
| 2021 | 29635766 | 372693 | 0.012576 | 74528 | 0.002515 | 315864 | 0.010658 | 125707 | 0.004242 | 264115 | 0.008912 |
| 2022 | 29635766 | 340835 | 0.011501 | 91736 | 0.003095 | 268213 | 0.00905 | 124562 | 0.004203 | 294726 | 0.009945 |
| 2023 | 29635766 | 369420 | 0.012465 | 108568 | 0.003663 | 283267 | 0.009558 | 109635 | 0.003699 | 262385 | 0.008854 |
| 2024 | 29635766 | 460496 | 0.015539 | 116583 | 0.003934 | 368599 | 0.012438 | 10113 | 0.000341 | 297165 | 0.010027 |
| 2025 | 29635766 | 371 | 1.3e-05 | 3 | 0.0 | 368 | 1.2e-05 | 0 | 0.0 | 774219 | 0.026124 |
- `label_siren_quality`: **pass** `{"rows": 266721894, "valid_siren": 266721894, "null_siren": 0, "valid_rate": 1.0, "ok": true}`

## Dataset Summary

| Dataset | Status | Rows | Files | Columns | Main Role |
|---|---:|---:|---:|---:|---|
| `raw_insee` | **available** | 246,453,008 | 5 | 110 | identity source |
| `raw_financials` | **available** | 6,368,964 | 1 | 5 | financial source |
| `raw_inpi` | **available** | 66,141,121 | 663 | 14 | registry source |
| `raw_bodacc` | **available** | 17,923,111 | 2660 | 41 | legal event source |
| `clean_company_identity` | **available** | 29,572,772 | 1 | 14 | normalized identity |
| `clean_financials` | **available** | 6,368,964 | 1 | 23 | normalized financials |
| `clean_legal_events` | **available** | 24,800,208 | 3894 | 17 | normalized legal events |
| `clean_formalities_events` | **available** | 53,544,636 | 5 | 10 | normalized registry events |
| `clean_annual_accounts` | **available** | 12,596,485 | 29 | 12 | normalized filings |
| `features_company_year` | **available** | 266,721,894 | 9 | 41 | model features |
| `features_risk_labels` | **available** | 266,721,894 | 9 | 9 | model labels |
| `features_company` | **available** | 29,635,766 | 1 | 41 | latest company snapshot |

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
| `event_date` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 19613 | 0017-08-03 00:00:00+00:00 | 9970-01-13 00:00:00+00:00 |  |
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
| `jugement_date` | `TIMESTAMP WITH TIME ZONE` | 0.080456 | 4911 | 0017-08-03 00:00:00+00:00 | 5202-05-14 00:00:00+00:00 |  |
| `date_cessation_paiement` | `TIMESTAMP WITH TIME ZONE` | 0.022338 | 5345 | 0017-01-15 00:00:00+00:00 | 6202-06-15 00:00:00+00:00 |  |
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
    "activity_code": "32.20Z",
    "administrative_status": "A",
    "legal_category_code": "1000",
    "siren": "801619156",
    "company_name": "BOIVIN",
    "creation_date": "2014-04-11 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": NaN,
    "head_office_siret": "80161915600012",
    "source_updated_at": "2025-12-06 10:36:59",
    "source_file": "/content/pfe_work/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
    "exported_at": "NaT"
  },
  {
    "activity_code": "74.10Z",
    "administrative_status": "C",
    "legal_category_code": "1000",
    "siren": "801619560",
    "company_name": "[ND]",
    "creation_date": "2014-04-10 00:00:00",
    "closure_date": "NaT",
    "status_period_start": "NaT",
    "employee_size_bracket": "NN",
    "employee_size_year": NaN,
    "head_office_siret": "80161956000031",
    "source_updated_at": "2024-03-22 14:26:06",
    "source_file": "/content/pfe_work/data-lake/raw/insee/bulk/stock_unite_legale/StockUniteLegale_utf8/part-00001.parquet",
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
| `exported_at` | `TIMESTAMP WITH TIME ZONE` | 1.0 | 1 | 2026-05-14 01:19:09.056000+00:00 | 2026-05-14 01:19:09.056000+00:00 |  |

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
    "source_file": "/content/pfe_work/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-14 01:19:09.056000+00:00"
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
    "source_file": "/content/pfe_work/data-lake/raw/financials/export-detail-bilan/export-detail-bilan.parquet",
    "exported_at": "2026-05-14 01:19:09.056000+00:00"
  }
]
```

## clean_legal_events

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/clean/legal_events`

**Rows:** 24,800,208

**Files:** 3894

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `event_date` | `DATE` | 1.0 | 17810 | 0017-08-03 | 9970-01-13 |  |
| `siren` | `VARCHAR` | 1.0 | 7108938 |  |  |  |
| `event_type` | `VARCHAR` | 0.999961 | 48 |  |  |  |
| `is_risk_event` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `is_radiation` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_liquidation` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_redressement` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_sauvegarde` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_procedure_collective` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `flag_cessation_paiement` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `nojo` | `VARCHAR` | 1.0 | 13070699 |  |  |  |
| `denomination` | `VARCHAR` | 0.898124 | 3800263 |  |  |  |
| `source_file` | `VARCHAR` | 1.0 | 2657 |  |  |  |
| `source_member` | `VARCHAR` | 1.0 | 5953 |  |  |  |
| `exported_at` | `TIMESTAMP` | 1.0 | 18688265 | 2026-05-13 18:02:55.963249 | 2026-05-13 20:21:36.908661 |  |
| `event_category` | `VARCHAR` | 1.0 | 4 |  |  |  |
| `event_year` | `BIGINT` | 1.0 | 175 | 17 | 9970 | 2022.7 |

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
    "exported_at": "2026-05-13 18:13:56.978866",
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
    "exported_at": "2026-05-13 18:04:07.977410",
    "event_category": "procedure_collective",
    "event_year": 17
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
    "event_date": "2024-12-26 00:00:00",
    "siren": "000391216",
    "event_type": "formalites",
    "event_text": "formalites",
    "record_key": "d9dbe4732d483f88825b9ec8df74b86afa404ab70b7a4d2960a1344784b88db2",
    "inpi_id": "63f860316379117d0f0c70b3",
    "source_file": "stock_RNE_formalites_NIVEAU1_20260304_1400.zip",
    "exported_at": "2026-05-13 10:59:23.057822",
    "event_year": 2024,
    "niveau": "niveau1"
  },
  {
    "event_date": "2024-05-19 00:00:00",
    "siren": "001303346",
    "event_type": "formalites",
    "event_text": "KATCHIT",
    "record_key": "4f9cd8ccd4fd33f9dae4a8da531bd050fe63ca5b2bf53dd00efa513bdeb1cb95",
    "inpi_id": "64060b4c363a4f0cd40a5d33",
    "source_file": "stock_RNE_formalites_NIVEAU1_20260304_1400.zip",
    "exported_at": "2026-05-13 10:59:23.057995",
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
| `closing_date` | `DATE` | 1.0 | 1964 | 1919-09-30 | 2029-12-31 |  |
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
    "exported_at": "2026-05-13 08:30:24.758349",
    "filing_year": 2012,
    "niveau": "niveau1"
  }
]
```

## features_company_year

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_year_features`

**Rows:** 266,721,894

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.997148 | 2691 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 43 | 0 | 59 | 0.0891083 |
| `company_age_years` | `BIGINT` | 0.958326 | 257 | -11 | 2024 | 15.1512 |
| `days_since_last_account_filing` | `BIGINT` | 0.039546 | 4023 | 0 | 4811 | 657.414 |
| `financial_years_available` | `BIGINT` | 1.0 | 26 | 0 | 26 | 0.143097 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.043386 | 20 | 2004 | 2025 | 2019.72 |
| `legal_category_code` | `VARCHAR` | 0.997874 | 253 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0180943 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 59 | 0 | 142 | 0.0655747 |
| `prediction_date` | `DATE` | 1.0 | 10 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 10 | 2017 | 2025 | 2021 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 25 | 0 | 123 | 0.0404523 |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.043386 | 21 | 0 | 18 | 1.72061 |
| `company_name` | `VARCHAR` | 0.99785 | 10457938 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.997874 | 17 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.997874 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 124 | 0 | 267 | 0.236628 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0185608 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 10 | 0 | 21 | 0.00377186 |
| `days_since_last_legal_event` | `BIGINT` | 0.11736 | 23008 | 0 | 733163 | 875.302 |
| `formalities_count_all` | `BIGINT` | 1.0 | 5 | 0 | 4 | 0.351644 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 5 | 0 | 4 | 0.194582 |

### Sample Rows

```json
[
  {
    "activity_code": "74.30Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 25,
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
    "siren": "388482150",
    "years_since_last_financial_statement": NaN,
    "company_name": "SVESS",
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
    "activity_code": "47.52A",
    "annual_accounts_count_24m": 0,
    "company_age_years": 25,
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
    "siren": "388505463",
    "years_since_last_financial_statement": NaN,
    "company_name": "ROGIER",
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

**Rows:** 266,721,894

**Files:** 9

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `continuity_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `filing_anomaly_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `financial_weakness_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `legal_distress_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `prediction_date` | `DATE` | 1.0 | 10 | 2017-12-31 | 2025-12-31 |  |
| `prediction_year` | `BIGINT` | 1.0 | 10 | 2017 | 2025 | 2021 |
| `radiation_risk_12m_label` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `first_future_legal_event_date` | `DATE` | 0.048547 | 3022 | 2018-01-01 | 2026-12-08 |  |

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
    "siren": "303454300",
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
    "siren": "303454334",
    "first_future_legal_event_date": "NaT"
  }
]
```

## features_company

**Path:** `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake/features/company_features`

**Rows:** 29,635,766

**Files:** 1

### Column Coverage

| Column | Type | Coverage | Distinct | Min | Max | Avg |
|---|---|---:|---:|---|---|---:|
| `activity_code` | `VARCHAR` | 0.997148 | 2691 |  |  |  |
| `annual_accounts_count_24m` | `BIGINT` | 1.0 | 39 | 0 | 59 | 0.0920881 |
| `company_age_years` | `BIGINT` | 0.958326 | 175 | -3 | 2024 | 19.1512 |
| `days_since_last_account_filing` | `BIGINT` | 0.053306 | 3694 | 0 | 4811 | 1065.9 |
| `financial_years_available` | `BIGINT` | 1.0 | 26 | 0 | 26 | 0.214908 |
| `has_confidential_financials` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `has_financial_data` | `BOOLEAN` | 1.0 | 2 |  |  |  |
| `latest_financial_year` | `INTEGER` | 0.052647 | 20 | 2009 | 2025 | 2021.48 |
| `legal_category_code` | `VARCHAR` | 0.997874 | 253 |  |  |  |
| `legal_distress_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0331737 |
| `legal_events_count_12m` | `BIGINT` | 1.0 | 35 | 0 | 130 | 0.12494 |
| `prediction_date` | `DATE` | 1.0 | 1 | 2025-12-31 | 2025-12-31 |  |
| `prediction_year` | `INTEGER` | 1.0 | 1 | 2025 | 2025 | 2025 |
| `radiation_events_count_all` | `BIGINT` | 1.0 | 20 | 0 | 123 | 0.0801703 |
| `siren` | `VARCHAR` | 1.0 | 28586411 |  |  |  |
| `years_since_last_financial_statement` | `INTEGER` | 0.052647 | 20 | 0 | 16 | 3.5231 |
| `company_name` | `VARCHAR` | 0.99785 | 10457938 |  |  |  |
| `employee_size_bracket` | `VARCHAR` | 0.997874 | 17 |  |  |  |
| `administrative_status_at_cutoff` | `VARCHAR` | 0.997874 | 2 |  |  |  |
| `legal_events_count_all` | `BIGINT` | 1.0 | 85 | 0 | 267 | 0.598572 |
| `legal_risk_events_count_all` | `BIGINT` | 1.0 | 17 | 0 | 22 | 0.0340254 |
| `legal_risk_events_count_12m` | `BIGINT` | 1.0 | 6 | 0 | 5 | 0.00478108 |
| `days_since_last_legal_event` | `BIGINT` | 0.233796 | 12541 | 0 | 733163 | 951.426 |
| `formalities_count_all` | `BIGINT` | 1.0 | 5 | 0 | 4 | 1.75124 |
| `formalities_count_12m` | `BIGINT` | 1.0 | 5 | 0 | 4 | 0.337686 |

### Sample Rows

```json
[
  {
    "activity_code": "90.01Z",
    "annual_accounts_count_24m": 0,
    "company_age_years": 7,
    "days_since_last_account_filing": NaN,
    "financial_years_available": 0,
    "has_confidential_financials": false,
    "has_financial_data": false,
    "latest_financial_year": NaN,
    "legal_category_code": "9220",
    "legal_distress_events_count_all": 0,
    "legal_events_count_12m": 0,
    "prediction_date": "2025-12-31 00:00:00",
    "prediction_year": 2025,
    "radiation_events_count_all": 0,
    "siren": "845200740",
    "years_since_last_financial_statement": NaN,
    "company_name": "YOKATTA RECORDS",
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
    "activity_code": "43.22A",
    "annual_accounts_count_24m": 0,
    "company_age_years": 6,
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
    "siren": "845202795",
    "years_since_last_financial_statement": NaN,
    "company_name": "YAHIA BENATTIA",
    "employee_size_bracket": "NN",
    "administrative_status_at_cutoff": "A",
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
- clean_financials: available with 6,368,964 rows and 23 columns.
- clean_financials: siren coverage is 1.0; this controls join reliability.
- clean_legal_events: available with 24,800,208 rows and 17 columns.
- clean_legal_events: siren coverage is 1.0; this controls join reliability.
- clean_formalities_events: available with 53,544,636 rows and 10 columns.
- clean_formalities_events: siren coverage is 1.0; this controls join reliability.
- clean_annual_accounts: available with 12,596,485 rows and 12 columns.
- clean_annual_accounts: siren coverage is 1.0; this controls join reliability.
- features_company_year: available with 266,721,894 rows and 41 columns.
- features_company_year: siren coverage is 1.0; this controls join reliability.
- features_risk_labels: available with 266,721,894 rows and 9 columns.
- features_risk_labels: siren coverage is 1.0; this controls join reliability.
- features_risk_labels: continuity_risk_12m_label coverage is 1.0.
- features_risk_labels: legal_distress_risk_12m_label coverage is 1.0.
- features_risk_labels: radiation_risk_12m_label coverage is 1.0.
- features_company: available with 29,635,766 rows and 41 columns.
- features_company: siren coverage is 1.0; this controls join reliability.

## Recommendations

- Review high-coverage feature columns first; sparse columns should become missingness or recency features before model use.

## How This Improves Feature Selection

Columns with high coverage and clear temporal meaning are stronger candidates for the first model. Columns with weak coverage may still be useful, but they should be transformed into robust features such as missingness indicators, counts, recency variables, or source-availability flags. Raw source lineage columns should remain available for auditability but should not be used directly as model inputs.
