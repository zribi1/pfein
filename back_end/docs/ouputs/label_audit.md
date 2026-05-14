# Label Audit

| Élément | Valeur |
|---|---|
| Généré le | `2026-05-14T22:39:38.663274+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |

## Objectif

Ce rapport vérifie la distribution des labels futurs et cherche à expliquer les années avec peu ou zéro positifs.

## Labels Positifs Par Année

| prediction_year | rows | continuity_positive | continuity_rate | legal_distress_positive | radiation_positive | financial_weakness_positive | filing_anomaly_positive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2017 | 20335854 | 267724 | 0.0131651 | 98385 | 183011 | 126013 | 183456 |
| 2018 | 21182127 | 305713 | 0.0144326 | 97381 | 226507 | 122314 | 311184 |
| 2019 | 22168852 | 261502 | 0.0117959 | 78601 | 205961 | 137819 | 293788 |
| 2020 | 23178651 | 307792 | 0.0132791 | 68244 | 248837 | 116197 | 253426 |
| 2021 | 24391406 | 366175 | 0.0150125 | 73980 | 309982 | 120467 | 264093 |
| 2022 | 25592352 | 335820 | 0.0131219 | 91317 | 263689 | 119991 | 294704 |
| 2023 | 26772040 | 364494 | 0.0136147 | 107413 | 279698 | 105978 | 262362 |
| 2024 | 27970861 | 478464 | 0.0171058 | 118922 | 384481 | 10043 | 297161 |
| 2025 | 29210896 | 304 | 1.04071e-05 | 0 | 304 | 0 | 774215 |

## Événements Futurs Par Source

| prediction_year | bodacc_events | inpi_events | insee_events | financial_events |
| --- | --- | --- | --- | --- |
| 2017 | 300339 | 0 | 0 | 126225 |
| 2018 | 344113 | 0 | 0 | 122552 |
| 2019 | 300180 | 0 | 0 | 138110 |
| 2020 | 333395 | 0 | 0 | 116401 |
| 2021 | 401643 | 0 | 0 | 120634 |
| 2022 | 376102 | 0 | 0 | 120193 |
| 2023 | 406754 | 7509 | 0 | 106148 |
| 2024 | 530669 | 4809 | 0 | 10049 |
| 2025 | 0 | 304 | 0 | 0 |

## Événements Utilisés Comme Labels Par Type

| event_family | source | event_count |
| --- | --- | --- |
| liquidation | BODACC | 730560 |
| procedure_collective | BODACC | 862534 |
| radiation | BODACC | 2130661 |
| redressement | BODACC | 119960 |
| sauvegarde | BODACC | 22253 |
| cessation_radiation_fermeture | INPI formalites | 12622 |
| negative_result_or_equity | financials | 860312 |

## Diagnostic

- La distribution des labels ne présente pas d'année totalement vide pour le label principal.

## Exemples De Labels Positifs

```json
[
  {
    "siren": "000000000",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-02-25",
    "prediction_year": 2017
  },
  {
    "siren": "003103498",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-03-27",
    "prediction_year": 2017
  },
  {
    "siren": "005420021",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-08-03",
    "prediction_year": 2017
  },
  {
    "siren": "005480546",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-04-25",
    "prediction_year": 2017
  },
  {
    "siren": "005550108",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-02-16",
    "prediction_year": 2017
  },
  {
    "siren": "005580683",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": true,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-02-11",
    "prediction_year": 2017
  },
  {
    "siren": "005620364",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-08-17",
    "prediction_year": 2017
  },
  {
    "siren": "005671870",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-10-03",
    "prediction_year": 2017
  },
  {
    "siren": "005680384",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-01-09",
    "prediction_year": 2017
  },
  {
    "siren": "005820360",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-04-20",
    "prediction_year": 2017
  },
  {
    "siren": "005850011",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-02-16",
    "prediction_year": 2017
  },
  {
    "siren": "005950134",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-11-07",
    "prediction_year": 2017
  },
  {
    "siren": "006280234",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": true,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-02-15",
    "prediction_year": 2017
  },
  {
    "siren": "006410120",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-06-21",
    "prediction_year": 2017
  },
  {
    "siren": "006572317",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-03-16",
    "prediction_year": 2017
  },
  {
    "siren": "006620066",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-01-18",
    "prediction_year": 2017
  },
  {
    "siren": "007080195",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": false,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-12-21",
    "prediction_year": 2017
  },
  {
    "siren": "007080526",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-01-23",
    "prediction_year": 2017
  },
  {
    "siren": "007180359",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-03-09",
    "prediction_year": 2017
  },
  {
    "siren": "007250046",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": true,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-02-01",
    "prediction_year": 2017
  }
]
```
