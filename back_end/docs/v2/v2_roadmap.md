# V2 — Feuille de route détaillée

> **Refonte architecturale du 2026-05-25.** Après les résultats Phase 4 (cf. `v2_phase_log.md`), V2 est passée d'un système monolithique de 5 classifieurs forward 12 mois à une **intelligence de risque à 4 couches** orientée action-taker. Les Phases 1-4 (features V2 + 5 modèles HGB) restent valides : elles fournissent la **Couche 1** du produit. Les Phases 5-10 sont refondues pour livrer les Couches 2, 3 et 4 + l'intégration.
>
> Motivation : un score forward seul ne couvre pas le besoin opérationnel (« qu'est-ce qui a changé ? », « pourquoi alerter ? », « comparer à mon portefeuille »). Cf. `docs/v2/v2_design_decisions.md` section 2026-05-25.

## Architecture cible — 4 couches

| Couche | Question répondue | Modèle | Statut |
|---|---|---|---|
| **1 — Probabilités forward** | « Probabilité d'événement à 12 mois ? » | 5 HGB supervisés (per-label) | ✅ Phase 4 |
| **2 — Score d'anomalie** | « Cette entreprise dévie-t-elle de la norme ? » | Isolation Forest non-supervisé | Phase 5 |
| **3 — Détection de changement** | « Qu'est-ce qui a changé depuis 12 mois ? » | Δ-features + Z-score | Phase 6 |
| **4 — Explicabilité** | « Pourquoi alerter sur cette entreprise ? » | SHAP par-prédiction (couches 1 et 2) | Phase 8 |

La sortie consolidée pour l'action-taker fusionne les 4 couches : tier composite (amber/red), probabilités par mode de défaillance, score d'anomalie en percentile, liste des changements récents, top-3 drivers SHAP.

Dix phases, exécutées séquentiellement. Chaque phase produit des artefacts vérifiables avant de débloquer la suivante. Le temps cumulé restant (Phases 5-10) est estimé à 5-7 semaines de travail effectif, hors temps de calcul des notebooks Colab. Défense PFE prévue juillet-août 2026.

## Structure de fichiers à créer

```
back_end/
├── app/tools/v2/
│   ├── __init__.py
│   ├── build_company_identity_periodic.py     # Phase 1
│   ├── build_company_year_features_v2.py      # Phase 2
│   ├── train_label_specific_model.py          # Phase 4 (1 fichier, paramétré par --label)
│   ├── bootstrap_metrics.py                   # Phase 6 (utilitaire)
│   ├── holdout_splits.py                      # Phase 7 (utilitaire)
│   └── _common.py                             # imports partagés depuis V1
├── app/ml/v2/
│   ├── __init__.py
│   ├── loader_v2.py                           # MLRegistryV2
│   └── artifacts/                             # joblib des 4 modèles V2
├── collabs/v2/
│   ├── v2_phase_1_identity_periodic.ipynb
│   ├── v2_phase_2_features_audit.ipynb
│   ├── v2_phase_3_baseline_100k.ipynb
│   ├── v2_phase_4_train_per_label.ipynb
│   ├── v2_phase_5_threshold_tuning.ipynb
│   ├── v2_phase_6_bootstrap_ci.ipynb
│   ├── v2_phase_7_external_validation.ipynb
│   ├── v2_phase_8_calibration.ipynb
│   └── v2_phase_9_integration_test.ipynb
└── docs/v2/
    ├── README.md
    ├── v2_roadmap.md (ce fichier)
    ├── v2_design_decisions.md
    ├── v2_phase_log.md
    └── v2_rapport_final_fr.md (à créer Phase 10)
```

---

## Phase 1 — Identité INSEE période-aware

**Objectif.** Reconstruire `data-lake/clean/company_identity_periodic/` depuis `data-lake/raw/insee/bulk/stock_unite_legale_historique/` avec granularité `(siren, period_start, period_end)` au lieu d'un snapshot par siren.

**Pourquoi.** En V1 (Run 3), nous avons exclu les quatre variables d'identité INSEE (`activity_code`, `legal_category_code`, `employee_size_bracket`, `administrative_status_at_cutoff`) parce que `clean/company_identity` était un snapshot non-périodique. Le SHAP (Phase D V1) confirme que ces variables auraient été les plus prédictives. Les réintégrer légitimement est la priorité d'amélioration N°1.

> **Restriction découverte en Phase 2.** Le flux INSEE `stock_unite_legale_historique` ne publie *pas* `tranche_effectifs_unite_legale` en version historique (cette colonne n'existe que dans le snapshot courant `stock_unite_legale`). V2 ne réintègre donc que **trois** des quatre variables : `activity_code`, `legal_category_code`, `administrative_status_at_cutoff`. La quatrième est explicitement abandonnée pour ne pas resservir la fuite de V1.

**Travail.**

1. Lire les fichiers `StockUniteLegaleHistorique_utf8.parquet` sous `data-lake/raw/insee/bulk/stock_unite_legale_historique/`.
2. Pour chaque SIREN, conserver toutes les périodes (un row par `(siren, date_debut_periode, date_fin_periode)`).
3. Si `date_fin_periode` est null pour la période courante, remplir avec une date sentinelle `9999-12-31`.
4. Valider : pour chaque SIREN multi-période, les périodes sont contiguës (pas de trou, pas d'overlap).
5. Écrire en parquet partitionné dans `data-lake/clean/company_identity_periodic/`.

**Code à écrire.** `app/tools/v2/build_company_identity_periodic.py` (CLI `python -m app.tools.v2.build_company_identity_periodic`).

**Notebook Colab.** `collabs/v2/v2_phase_1_identity_periodic.ipynb` qui :
- Lance le build.
- Compare le nombre de rows avec `clean/company_identity` V1 (devrait être ~3-5× plus, multi-périodes).
- Spot-check 50 SIRENs connus, vérifie qu'on retrouve bien plusieurs périodes pour les entreprises ayant changé de catégorie juridique / NAF.
- Vérifie l'absence de gaps et d'overlaps.

**Délivrable.** Parquet `data-lake/clean/company_identity_periodic/` opérationnel + rapport d'audit dans `v2_phase_log.md`.

**Critère de validation.** ≥ 95 % des SIRENs ont des périodes contiguës et sans overlap. Volumétrie attendue : 60 à 120 millions de rows (3 à 4× la table snapshot).

**Temps prévu.** 2-3 h.

---

## Phase 2 — Build features V2

**Objectif.** Construire `data-lake/features/company_year_features_v2/` qui inclut les features d'identité jointes par période, en plus de toutes les features non-identité de V1.

**Pourquoi.** Tester si la réintégration légitime des features d'identité INSEE améliore effectivement les performances par rapport à V1 leakage-free (Phase 3 fournit la comparaison).

**Travail.**

1. Copier `app/tools/build_company_year_features.py` en `app/tools/v2/build_company_year_features_v2.py`.
2. Modifier la jointure INSEE : remplacer la jointure sur `clean/company_identity` (snapshot) par une jointure sur `clean/company_identity_periodic` avec la condition :
   ```sql
   LEFT JOIN clean.company_identity_periodic i
     ON i.siren = b.siren
     AND i.period_start <= b.prediction_date
     AND (i.period_end IS NULL OR i.period_end > b.prediction_date)
   ```
3. Retirer les quatre colonnes INSEE de la liste `EXCLUDE_COLUMNS` (elles ne sont plus une fuite).
4. Écrire la sortie sous `data-lake/features/company_year_features_v2/` (n'écrase pas V1).

**Code à écrire.** `app/tools/v2/build_company_year_features_v2.py`.

**Notebook Colab.** `collabs/v2/v2_phase_2_features_audit.ipynb` qui :
- Lance le build sur 2017-2025.
- Audit anti-fuite : vérifie que pour chaque row, `period_start <= prediction_date` strictement.
- Compare le nombre de NaN sur `activity_code` et `legal_category_code` entre V1 et V2 (devrait être ≤).
- Vérifie que les autres features (BODACC, INPI, financières) sont identiques à V1 ligne par ligne (sanity check de non-régression).

**Délivrable.** Parquet `data-lake/features/company_year_features_v2/` opérationnel + audit dans `v2_phase_log.md`.

**Critère de validation.** Audit anti-fuite passe à 100 %. Joint rate INSEE ≥ 99 % (la quasi-totalité des SIRENs trouvent une période matchant leur prediction_date).

**Temps prévu.** 2-3 h.

---

## Phase 3 — Baseline iteratif (100K rows)

**Objectif.** Sur un échantillon réduit à 100 000 rows, entraîner un HGB par défaut et un LogReg, et confirmer que les features V2 produisent un signal supérieur à V1 leakage-free.

**Pourquoi.** Itération rapide pour valider la qualité des features V2 avant de lancer le full sweep. Discipline d'ingénieur : pas de run de 2M lignes avant d'avoir vérifié la sanité sur 100K. C'est l'un des regrets explicites de V1.

**Travail.**

1. Reprendre le notebook `v2_phase_3_baseline_100k.ipynb` qui charge `company_year_features_v2/` filtré à 100K lignes par échantillonnage hash-déterministe (même graine que V1, juste threshold différent).
2. Entraîner LogReg (avec OneHot et StandardScaler) — point de comparaison avec V1 Run 3.
3. Entraîner HGB par défaut — point de comparaison avec V1 Run 8 (AP 0.155).
4. Reporter AP, AUC, F1, taux de positifs pour chaque modèle.

**Notebook Colab.** `collabs/v2/v2_phase_3_baseline_100k.ipynb`.

**Délivrable.** Tableau comparatif dans `v2_phase_log.md` :

| Modèle | V1 (snapshot exclus) | V2 (période-aware) | Gain |
|---|---:|---:|---:|
| LogReg AP | 0.061 (Run 3) | ? | ? |
| HGB AP | 0.155 (Run 8) | ? | ? |

**Critère de validation pour passer à la Phase 4.** HGB V2 doit obtenir AP ≥ 0.18 sur 100K rows (gain ≥ 2.5 pp sur V1 à échantillon réduit). Si AP < 0.16, audit avant Phase 4 — quelque chose ne va pas dans la jointure période-aware.

**Temps prévu.** 1-2 h.

---

## Phase 4 — Entraînement par étiquette

**Objectif.** Entraîner quatre modèles HGB **distincts**, un par étiquette : `legal_distress_risk_12m_label`, `radiation_risk_12m_label`, `financial_weakness_risk_12m_label`, `filing_anomaly_risk_12m_label`. La cible composite `continuity_risk_12m_label` est conservée comme cinquième modèle de référence/comparaison.

**Pourquoi.** En V1, on agrège quatre événements aux dynamiques prédictives très différentes en un seul label. Les procédures collectives sont mieux prédites que les cessations volontaires. Un modèle par label expose une probabilité **interprétable** ("risque de procédure collective : X %") à l'utilisateur final.

**Travail.**

1. Copier `app/tools/train_continuity_model.py` en `app/tools/v2/train_label_specific_model.py`.
2. **Supprimer `class_weight='balanced'`** des classifieurs.
3. Paramétrer le label cible via `--target` (déjà supporté par V1, on profite).
4. Lancer 5 entraînements : `continuity` (référence), `legal_distress`, `radiation`, `financial_weakness`, `filing_anomaly`.
5. Hyperparamètres : ceux trouvés en V1 Phase B (`tuned_params_hgb.json`), supposés transférer raisonnablement.

**Notebook Colab.** `collabs/v2/v2_phase_4_train_per_label.ipynb` qui lance les 5 trainings en séquence.

**Délivrable.** 5 modèles `joblib` dans `ml-artifacts/v2/per_label/<label>/model.joblib` + tableau de métriques dans `v2_phase_log.md`.

**Critère de validation.** AP de `legal_distress_risk` ≥ 0.30 (procédures collectives mieux prédites que la cible composite V1 à AP 0.30). Si oui, la décomposition par label est validée.

**Temps prévu.** 3-4 h (compute) + 1 h analyse.

---

## Phase 5 — Couche 2 : détection d'anomalie non-supervisée

**Objectif.** Entraîner un **Isolation Forest** sur les features V2 *sans utiliser les labels*, produire un score d'anomalie par (siren, prediction_date), et le valider en montrant que les rows à fort score d'anomalie au temps T sont sur-représentées dans les événements de risque connus à T+12m.

**Pourquoi.** Un classifieur supervisé forward capture les patterns qui *précédent les événements labellisés*. Mais un action-taker veut aussi être alerté sur les patterns *atypiques*, même quand aucun label spécifique ne s'applique encore. L'Isolation Forest isole les rows « différentes » sans avoir besoin de savoir ce qui est « mauvais » : il apprend la structure de la population et flagge les écarts. Méthodologie standard en détection de fraude, en surveillance réseau, et en QC industrielle.

**Travail.**

1. **Préprocessing**. Imputation médiane pour numériques, OneHot avec `min_frequency=20` pour catégorielles. Isolation Forest sklearn ne gère pas nativement les NaN ni les catégorielles → préproc explicite.
2. **Fit** sur train 2017-2022 (hash-deterministic sample 2M rows pour itération rapide ; full V2 191M en re-run validatoire après).
3. **Score** sur test 2023. Le score sklearn `decision_function` est interprété en percentile sur la distribution train.
4. **Validation par enrichissement label**. Pour chaque label (continuity_risk, legal_distress_risk, radiation_risk, financial_weakness_risk) :
   - Prendre les top-K % par score d'anomalie (K ∈ {1, 5, 10}).
   - Mesurer le taux de positifs label dans ces top-K %.
   - Comparer à la base rate. Calculer le *lift* : `lift = précision_top_K / base_rate`.
   - Reporter une « ROC-style » courbe : x = fraction de la population flaggée, y = rappel cumulé du label.
5. **Comparer au baseline supervisé**. Pour chaque label, montrer la courbe précision-rappel de la couche 2 (isolation forest, *sans avoir vu les labels*) vs la couche 1 (HGB *entraîné sur les labels*). L'anomaly doit perdre en AP pure mais gagner en généralité (capter des patterns hors label).
6. **Score peer-group** (optionnel, v2.1). Ajuster le score d'anomalie en fonction du secteur NAF de l'entreprise : « est-elle atypique *parmi ses pairs* ? » plutôt que « atypique *globalement* ». Améliore la pertinence sectorielle.

**Code à écrire.** `app/tools/v2/train_anomaly_detector.py` (Isolation Forest pipeline + score persisting).

**Notebook Colab.** `collabs/v2/v2_phase_5_anomaly_detection.ipynb` qui :
- Lance le fit Isolation Forest sur train 2017-2022.
- Score 2023.
- Calcule l'enrichissement par label (table top-K vs base rate).
- Trace la courbe rappel-cumulé par label.
- Compare au baseline supervisé Phase 4.

**Délivrables.**
- `ml-artifacts/v2/anomaly_detector/model.joblib`
- `ml-artifacts/v2/anomaly_detector/test_scores.parquet` (siren, prediction_year, anomaly_score, anomaly_percentile)
- `ml-artifacts/v2/anomaly_detector/run_summary.md` (table enrichissement par label)

**Critère de validation.**
- Pour chaque label de Phase 4, **lift top-5 % ≥ 3** (un score d'anomalie sur la top-5 % est au moins 3× plus susceptible de présager un événement que la base rate). Si moins, le modèle ne capte rien d'utile.
- **AP top-5 % anomaly ≥ AP top-5 % aléatoire × 2** (sanity check : il fait mieux que de l'aléatoire).

**Temps prévu.** 1 semaine (design + fit + validation + comparaisons).

---

## Phase 6 — Couche 3 : détection de changement (Δ-features)

**Objectif.** Pour chaque (siren, prediction_year), calculer les écarts (deltas) sur les features clés entre l'année t et l'année t-1 (ou t-2 selon le signal). Flagger les changements abrupts via Z-score. Construire une couche **« qu'est-ce qui a changé ? »** que l'UI affiche à côté du score d'anomalie pour expliquer *quoi* a déclenché l'alerte.

**Pourquoi.** Un score d'anomalie en lui-même ne dit rien à l'action-taker. La couche 3 répond à la question évidente suivante : « OK il est anormal, mais en quoi ? ». Pour cela on dérive des features dérivées (deltas, taux de croissance, signaux booléens « a changé de NAF section ») et on Z-score celles qui ont du sens.

**Travail.**

1. Pour chaque feature numérique pertinente, ajouter sa version delta-12m et son Z-score sur la distribution de la population au temps t.
2. Pour les features catégorielles d'identité (NAF, forme juridique), ajouter un booléen `<feature>_changed_in_12m`.
3. Inclure ces features dérivées dans le jeu features V2.5 (rebuild incremental, ne casse pas la couche 2).
4. **Bonus** : ré-entraîner la couche 2 (Isolation Forest) sur ce jeu enrichi → score plus interprétable car les rows flaggées le sont souvent à cause des deltas (donc directement explicables).
5. Aussi, dans l'API V2, exposer les top-3 features les plus déviantes par rapport au profil historique de l'entreprise (Z-score le plus extrême).

**Code à écrire.** `app/tools/v2/build_delta_features.py` (extension du builder Phase 2).

**Notebook Colab.** `collabs/v2/v2_phase_6_delta_features.ipynb`.

**Délivrable.**
- Jeu features V2.5 : `data-lake/features/company_year_features_v2_5/` avec ~+15 colonnes Δ.
- Couche 2 ré-entraînée sur V2.5, comparée à V2 (gain attendu en lift).

**Critère de validation.** Lift top-5 % de la couche 2 sur V2.5 features ≥ lift sur V2 features. Sinon les deltas n'apportent rien, on garde V2.

**Temps prévu.** 1 semaine.

---

## Phase 7 — Validation externe (géographique + sectorielle)

**Objectif.** Vérifier que les performances tiennent **hors de la distribution d'entraînement**, à la fois pour la couche 1 (probabilités forward) et la couche 2 (anomalie). Deux holdouts :

- **Géographique** : entraîner sur Île-de-France + Sud (départements 75, 77, 78, 91, 92, 93, 94, 95, 13, 31, 33, 34, 06, 83 — ~40 % de la population SIRENE) et tester sur les départements restants.
- **Sectoriel** : retirer la section NAF la plus performante en V1 Phase F de l'entraînement et tester dessus.

**Pourquoi.** Aucune garantie que les performances tiennent sur une vraie population non-vue. Un jury peut le demander. C'est aussi un signal de robustesse pour le déploiement : si V2 over-fit sur une géographie, le déployer sur d'autres régions perdrait son utilité.

**Travail.**

1. Dériver le département depuis le SIRET (premier établissement) ou le code postal. Ajouter une colonne `departement` aux features V2.
2. Construire les découpages géographique et sectoriel.
3. **Couche 1** : ré-entraîner les 5 HGB sur chaque découpage, mesurer AP / AUC sur le test out-of-distribution.
4. **Couche 2** : ré-entraîner l'Isolation Forest sur chaque découpage, mesurer le lift par label sur le test out-of-distribution.
5. Comparer aux métriques in-distribution.

**Code à écrire.** `app/tools/v2/holdout_splits.py` (fonctions de découpage géographique et sectoriel).

**Notebook Colab.** `collabs/v2/v2_phase_7_external_validation.ipynb`.

**Critère de validation.** Pour chaque modèle (couche 1) et le détecteur d'anomalie (couche 2), AP / lift out-of-distribution ≥ AP / lift in-distribution − 5 pp / × 0.8. Sinon, le modèle est en sur-apprentissage par segment et il faut documenter cette limite.

**Temps prévu.** 1 semaine.

---

## Phase 8 — Couche 4 : explicabilité SHAP

**Objectif.** Pour toute alerte affichée à l'action-taker, fournir le **top-3 des features qui ont contribué le plus à l'alerte**. Couvre les couches 1 (5 HGB) et 2 (Isolation Forest, via TreeSHAP également supporté).

**Pourquoi.** Sans explicabilité, l'action-taker doit faire confiance aveuglément à un score. Avec SHAP, l'alerte devient justifiée : « risque élevé car (1) résultat net négatif 2 années consécutives, (2) événements légaux ×4 vs an dernier, (3) NAF a changé vers un secteur plus risqué ». C'est ce qui transforme V2 d'un score en un *outil d'aide à la décision*.

**Travail.**

1. **TreeSHAP pour couche 1**. Pour chacun des 5 HGB, intégrer `shap.TreeExplainer` au moment de l'inférence. Stocker les top-3 features positifs et top-3 négatifs par prédiction.
2. **TreeSHAP pour couche 2**. Isolation Forest est aussi un ensemble d'arbres → TreeSHAP fonctionne. Donne « quelles features rendent cette entreprise atypique ? ».
3. **Calibration légère**. En parallèle SHAP : vérifier Brier et ECE des couches 1 sans `class_weight` (cf. décision Phase 4). Si ECE > 0.02 pour un modèle, fitter `CalibratedClassifierCV(method='isotonic', cv=5)`. Phase 8 absorbe l'ancienne « phase calibration » roadmap V2 initial.

**Notebook Colab.** `collabs/v2/v2_phase_8_explainability.ipynb`.

**Délivrable.**
- Fonction `compute_explanation(model, X)` réutilisable côté backend.
- Persistence : pour chaque prédiction servie, top-3 SHAP values mis en cache.
- Si re-calibration nécessaire : modèle calibré qui remplace le brut dans `ml-artifacts/v2/per_label/<label>/model.joblib`.

**Critère de validation.**
- Explication SHAP calculée en < 50 ms par prédiction par modèle (sinon, optimiser ou pré-calculer).
- ECE ≤ 0.02 pour chaque modèle couche 1 (avec ou sans calibrateur).

**Temps prévu.** 1 semaine.

---

## Phase 9 — Intégration backend V2 (API + frontend)

**Objectif.** Servir le système V2 multi-couches via une nouvelle API `/api/v2/companies/{siren}/risk`. V1 reste accessible sur `/api/v1/predictions/{siren}` pendant la transition.

**Schéma de sortie envisagé.**

```json
{
  "siren": "123456789",
  "as_of_date": "2026-05-25",
  "composite_tier": "red",
  "layer_1_forward_probabilities": {
    "continuity_risk":     { "probability": 0.27, "tier": "amber", "horizon_months": 12 },
    "legal_distress_risk": { "probability": 0.18, "tier": "amber", "horizon_months": 12 },
    "radiation_risk":      { "probability": 0.04, "tier": "green", "horizon_months": 12 },
    "financial_weakness_risk": { "probability": 0.31, "tier": "red", "horizon_months": 12 }
  },
  "layer_2_anomaly": {
    "score":      0.78,
    "percentile": 95.4,
    "tier":       "red"
  },
  "layer_3_recent_changes": [
    { "feature": "legal_events_count_12m", "from": 0, "to": 4, "z_score": 3.8, "direction": "increase" },
    { "feature": "revenue_growth_1y",      "from": 0.05, "to": -0.42, "z_score": -2.9, "direction": "decrease" },
    { "feature": "activity_code",          "from": "47.24Z", "to": "56.30Z", "z_score": null, "direction": "changed" }
  ],
  "layer_4_top_drivers": [
    { "feature": "legal_distress_events_count_12m", "shap_value": 0.082, "impact": "positive" },
    { "feature": "has_negative_result_history",     "shap_value": 0.053, "impact": "positive" },
    { "feature": "legal_category_code",             "shap_value": -0.012, "impact": "negative" }
  ],
  "dormancy_flag": false
}
```

**Travail.**

1. `app/ml/v2/loader_v2.py` : singleton `MLRegistryV2` qui charge les 5 HGB + Isolation Forest + SHAP explainers au startup.
2. `app/schemas/company_risk_v2.py` : pydantic schemas pour le payload ci-dessus.
3. `app/services/v2_risk_service.py` : orchestration des 4 couches pour un siren donné (read features V2, run inference, build response).
4. `app/api/v2/endpoints/risk.py` : `GET /api/v2/companies/{siren}/risk`.
5. Frontend Angular : nouvel écran « V2 Risk Detail » qui affiche les 4 couches. À coordonner avec le développeur front.

**Notebook Colab.** Optionnel — `v2_phase_9_integration_smoke.ipynb` simule l'API V2 sur des SIRENs réels et vérifie la cohérence des sorties.

**Délivrable.** Service FastAPI V2 fonctionnel + tests pytest sur ≥ 5 SIRENs représentatifs (un dormant, un sain, un en pré-distress, un en distress avéré, un avec changement abrupt récent).

**Temps prévu.** 1-2 semaines.

---

## Phase 10 — Rapport V2 + comparaison V1/V2

**Objectif.** Rédiger le rapport académique V2, structuré pour pouvoir être lu seul ou en complément du rapport V1.

**Plan envisagé.**

1. **Préambule.** Décision de refonte V1 → V2 : ré-intégration des features INSEE période-aware + décomposition par label + pivot multi-couches.
2. **Sources de données et features.** Référencer V1 pour ce qui est inchangé. Détailler Phase 1 (identité périodique + broadcast creation_date) et Phase 2 (build features V2, anti-fuite).
3. **Couche 1 — probabilités forward.** Phase 4 résultats + interprétation (gate `legal_distress` manqué, `filing_anomaly` tautologique).
4. **Couche 2 — détection d'anomalie.** Phase 5 méthodologie + validation enrichissement.
5. **Couche 3 — détection de changement.** Phase 6.
6. **Couche 4 — explicabilité.** Phase 8.
7. **Robustesse (Phase 7).** Out-of-distribution géographique et sectorielle.
8. **Intégration produit (Phase 9).** Schéma API + UX action-taker.
9. **Discussion.** Limites de V2, choix non pris, pistes V2.5.
10. **Annexe.** Journal des décisions (`v2_design_decisions.md`).

**Délivrable.** `docs/v2/v2_rapport_final_fr.md`.

**Temps prévu.** 1-2 semaines (rédaction + relecture).

---

## Récapitulatif des dépendances

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 (Couche 1 ✅)
                                       ↓
                                  Phase 5 (Couche 2)
                                       ↓
                                  Phase 6 (Couche 3)
                                       ↓
                                  Phase 7 (validation OOD, parallèle possible)
                                       ↓
                                  Phase 8 (Couche 4 + calibration)
                                       ↓
                                  Phase 9 (API + frontend) → Phase 10 (rapport)
```

## Critère global d'acceptation V2 (refondu)

V2 est considérée comme un succès académique et opérationnel si :

1. **Couche 1** (Phase 4) : AP composite ≥ V1 calibré (≥ 0,299). ✅ atteint (0,306).
2. **Couche 2** (Phase 5) : pour chaque label de la couche 1, lift top-5 % anomaly ≥ 3 (i.e. le score d'anomalie a une utilité indépendante du label).
3. **Couche 3** (Phase 6) : l'inclusion des Δ-features augmente le lift de la couche 2 sur au moins 2 labels.
4. **Couche 4** (Phase 8) : explication SHAP calculée en < 50 ms par prédiction par modèle ; ECE ≤ 0,02 par couche 1.
5. **Robustesse OOD** (Phase 7) : pour la couche 1 et la couche 2, perte ≤ 5 pp / ×0,8 sur le test géographique.
6. **Produit** (Phase 9) : API V2 + écran frontend opérationnels, smoke-tests sur 5 SIRENs représentatifs passent.
7. **Rapport** (Phase 10) : rédigé et défendable, intégrant les choix architecturaux et leurs justifications.

Si l'un de ces critères échoue, le rapport V2 documente l'échec et ses causes — ce qui reste un résultat académique défendable.
