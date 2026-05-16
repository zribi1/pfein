# V2 — Journal des phases

Ce fichier consigne les résultats au fur et à mesure de l'exécution des phases V2. Chaque entrée comprend la date d'exécution, le résumé des résultats, les artefacts produits et toute décision prise. À remplir séquentiellement.

---

## Phase 1 — Identité INSEE période-aware

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_1_identity_periodic.ipynb`
**Script :** `app/tools/v2/build_company_identity_periodic.py`

### Résultats

- **Lignes en entrée** (`raw/insee/.../stock_unite_legale_historique`) : _(à remplir)_
- **Lignes en sortie** (`clean/company_identity_periodic`) : _(à remplir)_
- **Ratio rows périodiques / snapshot V1** : _(à remplir)_
- **SIRENs uniques** : _(à remplir)_
- **% SIRENs sans gap entre périodes** : _(à remplir)_
- **% SIRENs sans overlap entre périodes** : _(à remplir)_

### Décisions

_(à remplir)_

### Artefacts produits

- `data-lake/clean/company_identity_periodic/part-*.parquet`

---

## Phase 2 — Build features V2

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_2_features_audit.ipynb`
**Script :** `app/tools/v2/build_company_year_features_v2.py`

### Résultats

- **Lignes features V2** : _(à remplir)_ (devrait être identique à V1 : ~17 M)
- **Joint rate INSEE période-aware** : _(à remplir)_
- **% NaN sur `activity_code` V2 vs V1** : _(à remplir vs ~0 % V1, devrait être ≤)_
- **Audit anti-fuite** : passé / échoué (avec détail)

### Décisions

_(à remplir)_

### Artefacts produits

- `data-lake/features/company_year_features_v2/part-*.parquet`

---

## Phase 3 — Baseline iteratif (100K rows)

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_3_baseline_100k.ipynb`

### Résultats

| Modèle | V1 (snapshot exclus) | V2 (période-aware) | Δ |
|---|---:|---:|---:|
| LogReg AP | 0.061 (V1 Run 3 sur 2M) | _(à remplir, 100K)_ | _(à remplir)_ |
| HGB AP | 0.155 (V1 Run 8 sur 2M) | _(à remplir, 100K)_ | _(à remplir)_ |

### Décisions

_(à remplir : V2 est-elle validée pour passer en Phase 4 ?)_

---

## Phase 4 — Entraînement par étiquette

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_4_train_per_label.ipynb`
**Script :** `app/tools/v2/train_label_specific_model.py`

### Résultats — métriques par étiquette (test 2023)

| Étiquette | Taux positifs | AP | AUC | F1@0.5 | Run folder |
|---|---:|---:|---:|---:|---|
| `continuity_risk_12m_label` (référence) | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `legal_distress_risk_12m_label` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `radiation_risk_12m_label` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `financial_weakness_risk_12m_label` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `filing_anomaly_risk_12m_label` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |

### Décisions

_(à remplir)_

### Artefacts produits

- `ml-artifacts/v2/per_label/<label>/model.joblib` × 5
- `ml-artifacts/v2/per_label/<label>/run_summary.md` × 5

---

## Phase 5 — Tuning des seuils par étiquette

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_5_threshold_tuning.ipynb`

### Résultats — seuils retenus

| Étiquette | Seuil amber | Précision @ amber | Rappel @ amber | Seuil red | Précision @ red |
|---|---:|---:|---:|---:|---:|
| `continuity_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `legal_distress_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `radiation_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `financial_weakness_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `filing_anomaly_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |

### Décisions

_(à remplir)_

### Artefacts produits

- `ml-artifacts/v2/per_label_thresholds.json`

---

## Phase 6 — Bootstrap confidence intervals

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_6_bootstrap_ci.ipynb`
**Script :** `app/tools/v2/bootstrap_metrics.py`

### Résultats — métriques avec IC bootstrap 95 % (B=1000)

| Étiquette | AP [IC] | AUC [IC] | F1@amber [IC] |
|---|---|---|---|
| `continuity_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `legal_distress_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `radiation_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `financial_weakness_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `filing_anomaly_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |

### Décisions

_(à remplir : V2 vs V1, le gain est-il significatif ?)_

---

## Phase 7 — Validation externe

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_7_external_validation.ipynb`
**Script :** `app/tools/v2/holdout_splits.py`

### Résultats — Performance hors distribution

| Étiquette | AP in-distrib. | AP géo-holdout | Δ géo | AP sectoriel-holdout | Δ sectoriel |
|---|---:|---:|---:|---:|---:|
| `continuity_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| `legal_distress_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| ... | | | | | |

### Décisions

_(à remplir : robustesse hors-distribution validée ou limites documentées ?)_

---

## Phase 8 — Calibration

**Date d'exécution :** _(à remplir)_
**Notebook :** `collabs/v2/v2_phase_8_calibration.ipynb`

### Résultats — ECE et Brier par variante

| Étiquette | ECE brut (sans class_weight) | Brier brut | ECE après CalibratedClassifierCV | Brier après CCC |
|---|---:|---:|---:|---:|
| `continuity_risk` | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ | _(à remplir)_ |
| ... | | | | |

### Décisions

_(à remplir : pour chaque modèle, retient-on la variante brute ou calibrée ?)_

### Artefacts produits

- `ml-artifacts/v2/per_label/<label>/model.joblib` (variante retenue par modèle)

---

## Phase 9 — Intégration backend V2

**Date d'exécution :** _(à remplir)_
**Code :** `app/ml/v2/loader_v2.py`, `app/api/v2/endpoints/predictions.py`, `app/schemas/company_prediction_v2.py`

### Smoke tests

| Test | Statut |
|---|---|
| Chargement de `MLRegistryV2` au startup | _(passé / échoué)_ |
| `GET /api/v2/predictions/{siren_test_1}` | _(passé / échoué)_ |
| `GET /api/v2/predictions/{siren_test_2}` | _(passé / échoué)_ |
| Validation schéma `CompanyPredictionV2` | _(passé / échoué)_ |
| Affichage frontend Angular | _(passé / échoué)_ |

### Décisions

_(à remplir)_

---

## Phase 10 — Rapport V2 et comparaison V1/V2

**Date d'exécution :** _(à remplir)_

### Tableau de synthèse V1 vs V2

| Critère | V1 | V2 | Commentaire |
|---|---|---|---|
| AP cible composite (2023) | 0.299 | _(à remplir)_ | _(à remplir)_ |
| AP procédure collective (2023) | n/a (un seul modèle) | _(à remplir)_ | _(à remplir)_ |
| Calibration (ECE) | 0.006 (avec calibrateur) | _(à remplir)_ | _(à remplir)_ |
| Robustesse géo-holdout | non testée | _(à remplir)_ | _(à remplir)_ |
| Complexité opérationnelle | 2 artefacts | _(à remplir)_ | _(à remplir)_ |

### Verdict

_(à remplir : V2 supérieure ? sur quels axes ? quels axes restent défavorables à V2 ?)_
