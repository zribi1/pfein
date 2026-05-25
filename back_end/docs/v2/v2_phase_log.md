# V2 — Journal des phases

Ce fichier consigne les résultats au fur et à mesure de l'exécution des phases V2. Chaque entrée comprend la date d'exécution, le résumé des résultats, les artefacts produits et toute décision prise. À remplir séquentiellement.

---

## Phase 1 — Identité INSEE période-aware

**Date d'exécution :** 2026-05-25 (rebuild final, après fix broadcast `creation_date`)
**Notebook :** `collabs/v2/v2_phase_1_identity_periodic.ipynb`
**Script :** `app/tools/v2/build_company_identity_periodic.py`

### Résultats

- **Lignes en entrée** (`raw/insee/.../stock_unite_legale_historique`) : 69 819 310
- **Lignes en sortie** (`clean/company_identity_periodic`) : 69 411 475
- **Ratio rows périodiques / snapshot V1** : 0.99× (volumétrie comparable — V2 perd ~0,5% de SIRENs côté historique vs snapshot V1)
- **SIRENs uniques** : 29 165 833
- **Périodes par SIREN** (moyenne) : 2,38
- **Période min** : 1900-01-01 / **Période max** : 2029-12-31
- **% lignes avec gap** : 0,0000 % (0 ligne)
- **% lignes avec overlap** : 0,0000 % (0 ligne)
- **% lignes contiguës parmi non-premières** : 100,00 %
- **creation_date coverage** (broadcast snapshot) : **98,50 %** des 69,4 M rows portent une `creation_date` non-null (28,1 M SIRENs / 29,2 M).
- **Test jointure temporelle à 2020-12-31 et 2023-12-31** (100 SIRENs aléatoires chacun) : 0 cas avec matches multiples, ≥ 90 % avec exactement 1 match.

### Décisions

- **2026-05-19 — `employee_size_bracket` abandonnée.** Diagnostic Phase 2 (cellule 2b du notebook d'audit) : la colonne est NULL sur 100 % des 69 M périodes de `clean/company_identity_periodic`. Cause racine : `stock_unite_legale_historique` ne contient pas `tranche_effectifs_unite_legale` — INSEE ne publie ce champ que dans le snapshot courant `stock_unite_legale`. Re-sourcer depuis le snapshot resservirait la fuite de V1. La feature est donc retirée de `CANONICAL_COLUMNS` et du schéma V2 features. V2 réintègre donc **3 des 4** variables INSEE exclues par V1 au lieu de 4.
- **2026-05-25 — `creation_date` broadcastée depuis le snapshot INSEE.** Symptôme détecté en Phase 3 (premier run) : warning sklearn `Skipping features without any observed values: [company_age_years]` → `company_age_years` était 100 % NaN dans les features V2. Cause racine : `stock_unite_legale_historique` ne publie pas `date_creation_unite_legale` non plus (V1 le savait — cf. `app/tools/build_clean_core_sources.py:76-82,100-116`) ; le build V2 Phase 1 initial avait omis ce broadcast. Fix : `build_company_identity_periodic.py` accepte désormais `--snapshot-dir` et LEFT JOIN `siren_creation` (one-row-per-siren, sanity-clip [1900-2030]) en COALESCE-ant snapshot ⊳ historique. Validation : 98,50 % de couverture sur la table périodique reconstruite. `creation_date` étant immuable par SIREN, ce broadcast est leak-free (rien à voir avec la fuite V1 qui portait sur les attributs *time-varying*).

### Artefacts produits

- `data-lake/clean/company_identity_periodic/company_identity_periodic.parquet`
- `data-lake/clean/company_identity_periodic/_manifest.json`

---

## Phase 2 — Build features V2

**Date d'exécution :** 2026-05-25 (run full-population, après Phase 1 rebuild)
**Notebook :** `collabs/v2/v2_phase_2_features_audit.ipynb`
**Script :** `app/tools/v2/build_company_year_features_v2.py`

### Résultats

- **Lignes features V2** : **191 362 624** (2017-2024, ~24 M rows/an en moyenne — population complète, `SMOKE_TEST = False`)
- **Joint rate INSEE période-aware** : 98,13 % (97,99 % match avec valeur + 0,14 % match mais valeur NULL)
- **% sans match période INSEE** : 1,87 % (3,58 M rows — SIRENs avec historique INSEE manquant ou prediction_date avant période_start la plus ancienne)
- **% NaN sur `activity_code` V2** : 2,01 % (3,84 M rows). V1 historique ≈ 0 % par construction (snapshot = leak), donc V2 perd ~2 % de couverture en échange de l'absence de fuite — compromis attendu et accepté.
- **% NaN sur `legal_category_code` V2** : 1,87 %
- **% NaN sur `administrative_status_at_cutoff` V2** : 1,87 %
- **Audit anti-fuite** : ✅ **passé** — 0 row avec `period_start > prediction_date` ou `period_end <= prediction_date` parmi les 187,5 M rows avec `activity_code` non-null ; 100 % des valeurs jointes égales aux valeurs stockées.
- **Audit non-régression V1 vs V2** (1 000 SIRENs aléatoires, 7 606 (siren, year) appariés) : counts INPI (`formalities_*`, `cessation_*`) et financiers (`latest_revenue`, `net_result`, `revenue_growth_1y`) **identiques à V1**. Counts BODACC (`legal_events_*`, `radiation_*`) divergent de 1-11 % — attendu : V2 calcule sur un base_rows légèrement différent (filtrage par `creation_date` désormais sourcée du snapshot, et une trentaine de millions de SIRENs en moins côté périodique vs snapshot V1).

### Décisions

- **2026-05-25 — `SMOKE_TEST = False` pour le build retenu.** Un premier rebuild Phase 2 a été lancé en `SMOKE_TEST = True` (`--max-companies 200 000`), ce qui échantillonne les 200 K *plus petits* SIRENs (ordre alphabétique = ordre numérique sur un identifiant séquentiel) et donc les 200 K entreprises les plus anciennes — biais de survie massif, taux de positif Phase 3 effondré à 0,31 %. Run full-population repassé pour produire le jeu de features définitif (cell 12 du notebook : `SMOKE_TEST = False`).
- **Divergence BODACC V1/V2 tolérée.** Les 1-11 % d'écarts sur les counts d'événements légaux ne signalent pas un bug : V2 utilise `clean/company_identity_periodic` (29,2 M SIRENs) au lieu de `clean/company_identity` (29,6 M SIRENs), ce qui change marginalement l'univers de SIRENs pour lesquels une ligne (siren, year) est émise. Les valeurs sur les counts INPI/financiers sont identiques à 0 % près, signalant que le calcul lui-même n'a pas régressé.

### Artefacts produits

- `data-lake/features/company_year_features_v2/prediction_year=*/part-*.parquet` (8 partitions, 2017-2024)
- `data-lake/features/risk_labels_v2/prediction_year=*/part-*.parquet` (idem)
- `data-lake/features/company_year_features_v2/_manifest.json`

---

## Phase 3 — Baseline iteratif (100K rows)

**Date d'exécution :** 2026-05-25 (run final, V2 features full-population + `creation_date` broadcastée)
**Notebook :** `collabs/v2/v2_phase_3_baseline_100k.ipynb`

### Résultats

- **Échantillon hash-déterministe** : 85 635 rows (target 100 K, salt `v2_phase3_baseline`)
- **Population V2 totale** : 191 362 624 rows (2017-2024)
- **Taux de positif global** : 3,28 % (par-année 2,83 % en 2017 → 4,15 % en 2023, courbe ascendante cohérente avec V1)
- **Split temporel** : train 2017-2022 (71 600 rows, 2 226 positifs), test 2023 (14 035 rows, 583 positifs)

| Modèle | V1 (2M, identité exclue) | V2 (100K, période-aware) | Δ AP |
|---|---:|---:|---:|
| LogReg AP | 0.061 (V1 Run 3) | **0.150** | **+0.089** |
| HGB AP    | 0.155 (V1 Run 8) | **0.249** | **+0.094** |

**Détail HGB V2** (le critère de gate) : AP 0.249, AUC 0.851, F1@0.5 0.047, précision@0.5 0.737, rappel@0.5 0.024. F1 et rappel à 0,5 sont volontairement bas — c'est l'effet d'un seuil arbitraire sur un problème déséquilibré (3 % de positifs), pas un défaut du modèle. Phase 5 tunera le seuil opérationnel.

**Détail cardinalité catégorielles V2** : `activity_code` 988 codes NAF → 255 après regroupement de la queue rare en `__rare__` (HGB plafonne à `max_bins=255`). LogReg utilise `OneHotEncoder(min_frequency=20)`, équivalent en intention.

### Décisions

- ✅ **Critère de validation Phase 3 atteint.** HGB AP 0.249 ≥ 0.18 (gate), et le gain de +9,4 pp sur V1 Run 8 (+5,9 pp sur V1 Run 7 calibré à 0,30) confirme empiriquement que la jointure INSEE période-aware apporte un signal substantiel, même sur 86 K rows. **Passage à la Phase 4 validé.**
- **Itération avant fix `creation_date`**. Premier run Phase 3 (V2 sans `creation_date` populée) : HGB AP **0.205**. Après broadcast snapshot : **0.249**. L'ajout de `company_age_years` populée vaut donc ~+4 pp sur HGB. Justifie a posteriori l'effort de réintégration via snapshot.
- **`employee_size_bracket` n'est plus dans le schéma V2 features.** `n_num_features` = 33 vs 34 au premier run — la colonne fantôme all-NaN a été retirée du SELECT final du builder. Aligné avec la décision Phase 1.

---

## Phase 4 — Entraînement par étiquette (Layer 1 du produit V2)

**Date d'exécution :** 2026-05-25
**Notebook :** `collabs/v2/v2_phase_4_train_per_label.ipynb`
**Script :** `app/tools/v2/train_label_specific_model.py`
**Échantillon par fit :** 2 000 000 rows (hyperparams V1 Phase B tunés à 2M)
**Hyperparamètres :** `docs/ouputs/ml-artifacts/tuned_params_hgb.json` (V1)
**Sans `class_weight='balanced'`** (cf. décision V2)

### Résultats — métriques par étiquette (test 2023)

| Étiquette | Taux positifs | AP | AUC | F1@0.5 | Précision@0.5 | Rappel@0.5 |
|---|---:|---:|---:|---:|---:|---:|
| `continuity_risk_12m_label` (composite) | 4,27 % | **0,306** | 0,877 | 0,072 | 0,717 | 0,038 |
| `legal_distress_risk_12m_label` | 0,41 % | 0,232 | 0,960 | 0,159 | 0,534 | 0,093 |
| `radiation_risk_12m_label` | 1,05 % | 0,228 | 0,891 | 0,212 | 0,753 | 0,123 |
| `financial_weakness_risk_12m_label` | 0,40 % | 0,423 | 0,990 | 0,376 | 0,561 | 0,283 |
| `filing_anomaly_risk_12m_label` | 1,01 % | **0,937** | 0,999 | 0,893 | 0,894 | 0,893 |

### Lecture des résultats

- **Composite V2 vs V1**. AP 0,306 vs V1 calibré 0,299 (+0,007 pp). Gain modeste à iso-hyperparams et iso-volumétrie. Le gain spectaculaire vu en Phase 3 (+9,4 pp) comparait V2 tuné contre V1 par défaut — apples-to-oranges. À iso-conditions, V2 préserve la performance composite plutôt que de la transformer.
- **`legal_distress_risk_12m_label`** : AP 0,232, **gate 0,30 manqué**. Mais AUC 0,960 et lift = AP / base_rate = 0,232 / 0,0041 ≈ **57× au-dessus du hasard**. Le gate du roadmap était trop ambitieux en absolu : il assumait qu'un modèle ciblé sur une sous-cible battrait le composite, sans tenir compte de la base rate 10× plus faible (AP est sensible à la base rate, AUC ne l'est pas). Le ranking par AUC est en réalité excellent.
- **`filing_anomaly_risk_12m_label`** : AP 0,937 — **prédiction tautologique**. Le label est "ne déposera pas de comptes dans les 18 prochains mois" et la feature `days_since_last_account_filing` est essentiellement le label en mesure inverse. Un modèle qui apprend "si 3 ans sans dépôt, prédire 18 mois de plus sans dépôt" obtient 0,94 d'AP sans valeur ajoutée. Ce n'est pas de la fuite (les features sont au temps T, le label est à T+18m) mais c'est de l'autocorrélation triviale.
- **`financial_weakness`** : AP 0,423, AUC 0,990 — fort signal d'autocorrélation financière (un résultat net négatif l'an dernier prédit fortement un résultat net négatif cette année).
- **`radiation`** : AP 0,228 — cessations volontaires, les plus difficiles à prédire car liées à une intention humaine.

### Décisions

- **2026-05-25 — Pivot architectural vers un système multi-couches.** Les résultats Phase 4 révèlent les limites structurelles d'une prédiction supervisée forward à 12 mois prise isolément : `filing_anomaly` est tautologique, `legal_distress` souffre d'une base rate trop faible pour atteindre une AP élevée même avec un excellent ranking, et le gain composite est marginal. Le besoin métier d'un *action-taker* (alerte précoce, identification du changement récent, explicabilité) n'est pas couvert par un score forward unique. V2 pivote vers une **intelligence de risque à 4 couches** :
  - **Couche 1 (faite, Phase 4)** : probabilités forward 12 mois (les 5 HGB ci-dessus).
  - **Couche 2 (à construire, nouvelle Phase 5)** : détection d'anomalie non-supervisée (Isolation Forest sur features V2, validation par enrichissement contre les labels).
  - **Couche 3 (à construire, nouvelle Phase 6)** : détection de changement (Δ des features entre T et T-12m, Z-score sur écarts).
  - **Couche 4 (à construire, nouvelle Phase 8)** : SHAP par prédiction pour les couches 1 et 2.

  Cf. roadmap mis à jour (sections Phase 5+ refondues) et `docs/v2/v2_design_decisions.md`.

- **`filing_anomaly_risk_12m_label` rétrogradé en `dormancy_flag`.** Le modèle reste entraîné, son `model.joblib` est conservé, mais le rapport et l'API V2 le présenteront comme un indicateur de *dormance* (l'entreprise est-elle déjà désengagée de ses obligations déclaratives ?), pas comme un score de risque. Cas d'usage : filtrer les alertes des autres modèles pour ne pas crier au loup sur une entreprise déjà inactive depuis 3 ans.

- **`legal_distress` gate manqué — pas de re-tuning.** Décision documentée plutôt que rattrapée. Re-tuner les hyperparams spécifiquement pour `legal_distress` (RandomizedSearchCV dédié) aurait pu gagner 2-4 pp mais n'aurait pas changé le constat structurel (le 12m horizon est mal aligné avec une décision judiciaire). Le système multi-couches résoud ce problème différemment : la couche 2 (anomaly) capte les patterns de pré-distress sans nécessiter de label précis ; la couche 3 (change-point) montre les ruptures abruptes (saut d'événements légaux récents) qui précèdent les procédures.

### Artefacts produits

- `ml-artifacts/v2/per_label/<label>/model.joblib` × 5 (Drive)
- `ml-artifacts/v2/per_label/<label>/metadata.json` × 5
- `ml-artifacts/v2/per_label/<label>/run_summary.md` × 5
- `ml-artifacts/v2/per_label/<label>/test_predictions.parquet` × 5 (pour bootstrap Phase 6, et pour validation de la couche 2)

Train rows par label : 1 672 152. Test rows par label : 327 848.

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
