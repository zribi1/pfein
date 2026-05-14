# Leakage Audit

| Élément | Valeur |
|---|---|
| Généré le | `2026-05-14T16:20:47.876242+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |

## Objectif

Ce rapport vérifie les principaux risques de fuite temporelle ou de fuite de target dans les entrées du modèle.

**Résultat global:** FAIL

## Checks

| check | ok | result | details |
| --- | --- | --- | --- |
| Forbidden columns absent from feature table | False | FAIL | `{"forbidden_found": ["prediction_date", "siren"]}` |
| Target columns are stored outside feature table | True | PASS | `{}` |
| first_future_legal_event_date not in feature table | True | PASS | `{}` |
| siren excluded by training tool | True | PASS | `{"note": "siren exists for joins but is excluded by train_continuity_model.EXCLUDE_COLUMNS"}` |
| Future legal label dates inside 12-month window | True | PASS | `{"violations": 0}` |
| Financial feature years not after prediction year | True | PASS | `{"violations": 0}` |

