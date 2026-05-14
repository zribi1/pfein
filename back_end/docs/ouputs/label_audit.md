# Label Audit

| Élément | Valeur |
|---|---|
| Généré le | `2026-05-14T04:27:35.254362+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |

## Objectif

Ce rapport vérifie la distribution des labels futurs et cherche à expliquer les années avec peu ou zéro positifs.

## Labels Positifs Par Année

| prediction_year | rows | continuity_positive | continuity_rate | legal_distress_positive | radiation_positive | financial_weakness_positive | filing_anomaly_positive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2017 | 29635766 | 275401 | 0.00929286 | 97980 | 190954 | 131125 | 183470 |
| 2018 | 29635766 | 309626 | 0.0104477 | 97429 | 230214 | 127294 | 311206 |
| 2019 | 29635766 | 270443 | 0.00912556 | 78353 | 215089 | 142038 | 293812 |
| 2020 | 29635766 | 320376 | 0.0108105 | 67789 | 261719 | 121629 | 253448 |
| 2021 | 29635766 | 372693 | 0.0125758 | 74528 | 315864 | 125707 | 264115 |
| 2022 | 29635766 | 340835 | 0.0115008 | 91736 | 268213 | 124562 | 294726 |
| 2023 | 29635766 | 369420 | 0.0124653 | 108568 | 283267 | 109635 | 262385 |
| 2024 | 29635766 | 460496 | 0.0155385 | 116583 | 368599 | 10113 | 297165 |
| 2025 | 29635766 | 371 | 1.25187e-05 | 3 | 368 | 0 | 774219 |

## Événements Futurs Par Source

| prediction_year | bodacc_events | inpi_events | insee_events | financial_events |
| --- | --- | --- | --- | --- |
| 2017 | 307839 | 0 | 0 | 131349 |
| 2018 | 347933 | 0 | 0 | 127555 |
| 2019 | 309030 | 0 | 0 | 142335 |
| 2020 | 345882 | 0 | 0 | 121849 |
| 2021 | 408766 | 0 | 0 | 125884 |
| 2022 | 381152 | 0 | 0 | 124773 |
| 2023 | 675128 | 7674 | 0 | 109812 |
| 2024 | 557866 | 4979 | 0 | 10121 |
| 2025 | 54 | 317 | 0 | 0 |

## Événements Utilisés Comme Labels Par Type

| event_family | source | event_count |
| --- | --- | --- |
| liquidation | BODACC | 729444 |
| procedure_collective | BODACC | 861077 |
| radiation | BODACC | 2472573 |
| redressement | BODACC | 119600 |
| sauvegarde | BODACC | 22208 |
| cessation_radiation_fermeture | INPI formalites | 12970 |
| negative_result_or_equity | financials | 893678 |

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
