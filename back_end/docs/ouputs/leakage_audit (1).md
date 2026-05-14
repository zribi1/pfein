# Leakage Audit

| Élément | Valeur |
|---|---|
| Généré le | `2026-05-14T22:39:38.663274+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |

## Objectif

Ce rapport vérifie les principaux risques de fuite temporelle ou de fuite de target dans les entrées du modèle.

**Résultat global:** PASS

## Checks

| check | ok | result | details |
| --- | --- | --- | --- |
| Forbidden columns excluded from model inputs | True | PASS | `{"stored_in_feature_table": ["prediction_date", "siren"], "still_in_model": []}` |
| Display-only columns excluded from model inputs | True | PASS | `{"still_in_model": []}` |
| Target columns are stored outside feature table | True | PASS | `{}` |
| first_future_legal_event_date not in feature table | True | PASS | `{}` |
| siren available for joins and excluded by training tool | True | PASS | `{}` |
| Future legal label dates inside 12-month window | True | PASS | `{"violations": 0}` |
| Financial feature years not after prediction year | True | PASS | `{"violations": 0}` |

