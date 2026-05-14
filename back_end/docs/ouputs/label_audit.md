# Label Audit

| Élément | Valeur |
|---|---|
| Généré le | `2026-05-14T16:20:47.876242+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |

## Objectif

Ce rapport vérifie la distribution des labels futurs et cherche à expliquer les années avec peu ou zéro positifs.

## Labels Positifs Par Année

| prediction_year | rows | continuity_positive | continuity_rate | legal_distress_positive | radiation_positive | financial_weakness_positive | filing_anomaly_positive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2017 | 20335854 | 264638 | 0.0130134 | 97714 | 180455 | 126013 | 183456 |
| 2018 | 21182127 | 297946 | 0.0140659 | 97167 | 218788 | 122314 | 311184 |
| 2019 | 22168852 | 260031 | 0.0117296 | 78243 | 204787 | 137819 | 293788 |
| 2020 | 23178651 | 302600 | 0.0130551 | 67637 | 244094 | 116197 | 253426 |
| 2021 | 24391406 | 359387 | 0.0147342 | 74319 | 302764 | 120467 | 264093 |
| 2022 | 25592352 | 328742 | 0.0128453 | 91504 | 256350 | 119991 | 294704 |
| 2023 | 26772040 | 354658 | 0.0132473 | 108307 | 268762 | 105978 | 262362 |
| 2024 | 27970861 | 446691 | 0.0159699 | 116302 | 355038 | 10043 | 297161 |
| 2025 | 29210896 | 356 | 1.21872e-05 | 3 | 353 | 0 | 774215 |

## Événements Futurs Par Source

| prediction_year | bodacc_events | inpi_events | insee_events | financial_events |
| --- | --- | --- | --- | --- |
| 2017 | 296977 | 0 | 0 | 126225 |
| 2018 | 336153 | 0 | 0 | 122552 |
| 2019 | 298502 | 0 | 0 | 138110 |
| 2020 | 327950 | 0 | 0 | 116401 |
| 2021 | 394961 | 0 | 0 | 120634 |
| 2022 | 368940 | 0 | 0 | 120193 |
| 2023 | 396940 | 7509 | 0 | 106148 |
| 2024 | 497532 | 4809 | 0 | 10049 |
| 2025 | 52 | 304 | 0 | 0 |

## Événements Utilisés Comme Labels Par Type

| event_family | source | event_count |
| --- | --- | --- |
| liquidation | BODACC | 727780 |
| procedure_collective | BODACC | 859211 |
| radiation | BODACC | 2058796 |
| redressement | BODACC | 119432 |
| sauvegarde | BODACC | 22167 |
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
    "first_future_legal_event_date": "2018-02-16",
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
    "first_future_legal_event_date": "2018-03-02",
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
    "first_future_legal_event_date": "2018-07-27",
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
    "first_future_legal_event_date": "2018-04-10",
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
    "first_future_legal_event_date": "2018-03-09",
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
    "first_future_legal_event_date": "2018-10-30",
    "prediction_year": 2017
  },
  {
    "siren": "006011522",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-11-04",
    "prediction_year": 2017
  },
  {
    "siren": "006041099",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-09-11",
    "prediction_year": 2017
  },
  {
    "siren": "006241657",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-12-31",
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
    "first_future_legal_event_date": "2018-06-30",
    "prediction_year": 2017
  },
  {
    "siren": "006512131",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-12-31",
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
    "siren": "006973606",
    "prediction_date": "2017-12-31",
    "legal_distress_risk_12m_label": false,
    "radiation_risk_12m_label": true,
    "financial_weakness_risk_12m_label": false,
    "filing_anomaly_risk_12m_label": false,
    "continuity_risk_12m_label": true,
    "first_future_legal_event_date": "2018-12-31",
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
    "first_future_legal_event_date": "2018-12-05",
    "prediction_year": 2017
  }
]
```
