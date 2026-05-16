# V2 — Feuille de route détaillée

Dix phases, exécutées séquentiellement. Chaque phase produit des artefacts vérifiables avant de débloquer la suivante. Le temps cumulé prévu est de 15 à 25 heures de travail effectif, hors temps de calcul des notebooks Colab.

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

## Phase 5 — Tuning des seuils par étiquette

**Objectif.** Pour chacun des 5 modèles, calculer les courbes seuil → précision/rappel sur le test 2023 et identifier les seuils opérationnels (amber, red).

**Pourquoi.** Sans `class_weight='balanced'`, les probabilités brutes sont déjà bien échelonnées (à valider). Le seuil de décision n'est plus un paramètre théorique à 0,5 mais un paramètre opérationnel choisi sur la base d'une courbe précision/rappel. Si la calibration est déjà correcte, on peut sauter le calibrateur séparé.

**Travail.**

1. Pour chaque modèle, lancer un balayage de seuils dense (0.001 à 0.99 par pas log).
2. Identifier :
   - Le seuil F1-optimum (amber).
   - Le seuil de précision ≥ 50 % (red).
3. Vérifier que les probabilités brutes ne sont pas grossièrement décalées (mean predicted ≈ mean observed à ±20 %). Si oui, **pas besoin de calibrateur** (à valider en Phase 8).

**Notebook Colab.** `collabs/v2/v2_phase_5_threshold_tuning.ipynb`.

**Délivrable.** Fichier `ml-artifacts/v2/per_label_thresholds.json` :
```json
{
  "legal_distress_risk": { "amber": 0.X, "red": 0.Y },
  "radiation_risk":      { "amber": 0.X, "red": 0.Y },
  "financial_weakness_risk": { "amber": 0.X, "red": 0.Y },
  "filing_anomaly_risk": { "amber": 0.X, "red": 0.Y },
  "continuity_risk":     { "amber": 0.X, "red": 0.Y }
}
```

**Critère de validation.** Pour chaque label, un seuil amber existe avec F1 ≥ 0.25 et un seuil red existe avec précision ≥ 0.45.

**Temps prévu.** 1-2 h.

---

## Phase 6 — Bootstrap confidence intervals

**Objectif.** Pour chaque modèle et chaque métrique principale (AP, AUC, F1), calculer un intervalle de confiance bootstrap à 95 %.

**Pourquoi.** Reporter `AP = 0.30` est moins défendable que `AP = 0.30 [0.28, 0.32]`. Un jury de soutenance peut demander « est-ce significativement supérieur à V1 ? » — la réponse rigoureuse nécessite des CIs.

**Travail.**

1. Pour chaque modèle, depuis le test set 2023, tirer B = 1000 échantillons bootstrap (avec remise).
2. Calculer AP, AUC, F1 sur chaque échantillon.
3. Prendre les quantiles 2,5 % et 97,5 %.
4. Reporter au format `metric [low, high]`.

**Code à écrire.** `app/tools/v2/bootstrap_metrics.py` (utilitaire réutilisable).

**Notebook Colab.** `collabs/v2/v2_phase_6_bootstrap_ci.ipynb`.

**Délivrable.** Table CIs dans `v2_phase_log.md`. Une comparaison V1 vs V2 avec CIs permettant de trancher si le gain est significatif.

**Critère de validation.** Borne inférieure de l'AP V2 sur `legal_distress_risk` ≥ borne supérieure de l'AP V1 sur la cible composite. Sinon, le gain V2 n'est pas significatif et il faut investiguer.

**Temps prévu.** 1 h.

---

## Phase 7 — Validation externe

**Objectif.** Vérifier que les performances tiennent **hors de la distribution d'entraînement**. Deux holdouts :

- **Géographique** : entraîner sur Île-de-France + Sud (départements 75, 77, 78, 91, 92, 93, 94, 95, 13, 31, 33, 34, 06, 83 — soit ~40 % de la population SIRENE) et tester sur les départements restants.
- **Sectoriel** : retirer la section NAF 5 (hébergement-restauration, la plus performante en V1 Phase F) de l'entraînement et tester dessus.

**Pourquoi.** En V1, toute l'évaluation se fait sur un échantillon hash-déterministe de la même population. Aucune garantie que les performances tiennent sur une vraie population non-vue. Un jury peut le demander.

**Travail.**

1. Dériver le département depuis le SIRET (premier établissement) ou le code postal de la dénomination INSEE. Ajouter une colonne `departement` aux features V2.
2. Construire les deux découpages, entraîner les 5 modèles sur chaque, mesurer AP / AUC sur le test out-of-distribution.
3. Comparer aux métriques in-distribution.

**Code à écrire.** `app/tools/v2/holdout_splits.py` (fonctions de découpage géographique et sectoriel).

**Notebook Colab.** `collabs/v2/v2_phase_7_external_validation.ipynb`.

**Délivrable.** Tableau dans `v2_phase_log.md` :

| Modèle | AP in-distribution | AP géo-holdout | AP sectoriel-holdout |
|---|---:|---:|---:|
| legal_distress | ? | ? | ? |
| ... |

**Critère de validation.** Pour chaque modèle, AP out-of-distribution ≥ AP in-distribution − 5 pp. Sinon, le modèle est en sur-apprentissage par segment et il faut documenter cette limite.

**Temps prévu.** 3-4 h.

---

## Phase 8 — Calibration via CalibratedClassifierCV

**Objectif.** Si la Phase 5 a montré que les probabilités brutes sont déjà bien calibrées (sans `class_weight='balanced'`), cette phase devient un simple check. Sinon, on applique `CalibratedClassifierCV(method='isotonic', cv=5)` sur chacun des 5 modèles.

**Pourquoi.** En V1, on a utilisé un découpage trois-temps (train/calib/test) qui a coûté une année d'entraînement. `CalibratedClassifierCV` ne demande pas de hold-out séparé ; il fait la calibration par K-fold sur l'ensemble d'entraînement.

**Travail.**

1. Pour chaque modèle, calculer Brier et ECE sur le test 2023.
2. Si ECE > 0.02, fitter `CalibratedClassifierCV(base_estimator=hgb, method='isotonic', cv=5)` sur l'ensemble d'entraînement et re-mesurer.
3. Comparer les deux variantes et choisir celle avec le meilleur Brier.

**Notebook Colab.** `collabs/v2/v2_phase_8_calibration.ipynb`.

**Délivrable.** Pour chaque label, un seul artefact `joblib` (soit le modèle brut, soit le modèle calibré, selon ce qui passe le test).

**Critère de validation.** ECE final ≤ 0.02 pour chaque modèle.

**Temps prévu.** 1-2 h.

---

## Phase 9 — Intégration backend V2

**Objectif.** Servir les 5 modèles V2 via une nouvelle API `/api/v2/predictions/{siren}`. V1 reste accessible sur `/api/v1/predictions/{siren}` pendant la transition.

**Travail.**

1. Créer `app/ml/v2/loader_v2.py` (singleton `MLRegistryV2`) qui charge les 5 modèles + leurs seuils.
2. Créer `app/schemas/company_prediction_v2.py` avec un schéma incluant `risk_per_label: dict[str, {prob: float, tier: Literal[...]}]`.
3. Créer `app/api/v2/endpoints/predictions.py` exposant `/api/v2/predictions/{siren}`.
4. Mettre à jour le frontend Angular pour afficher les 4-5 risques séparés (à coordonner avec le développeur front).

**Notebook Colab.** Optionnel — `v2_phase_9_integration_test.ipynb` simule l'API V2 en local sur des SIRENs réels et vérifie la cohérence des sorties.

**Délivrable.** Service FastAPI V2 fonctionnel + tests automatisés (pytest) sur 5 SIRENs représentatifs.

**Temps prévu.** 4-6 h.

---

## Phase 10 — Rapport V2 + comparaison V1/V2

**Objectif.** Rédiger le rapport académique V2, structuré pour pouvoir être lu seul ou en complément du rapport V1.

**Contenu.**
- Préambule expliquant la décision de refonte.
- Reprise des sections architecture / sources / features (référencer V1 pour les parties inchangées).
- Détail des phases 1 à 9 V2.
- **Tableau de comparaison V1 vs V2** avec bootstrap CIs.
- Conclusion : V2 est-elle effectivement supérieure ? Sur quels axes ?
- Annexe : journal des décisions (`v2_design_decisions.md`).

**Délivrable.** `docs/v2/v2_rapport_final_fr.md`.

**Temps prévu.** 6-8 h.

---

## Récapitulatif des dépendances

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
                                       ↓
                                  Phase 7 (parallel with 5-6)
                                       ↓
                                  Phase 8 → Phase 9 → Phase 10
```

Phases parallélisables : 5 et 7 peuvent tourner en parallèle sur des Colab distincts une fois la Phase 4 terminée.

## Critère global d'acceptation V2

V2 est considérée comme un succès académique et opérationnel si :

1. AP de `legal_distress_risk` ≥ 0.40 sur 2023 test, avec borne inférieure de l'IC bootstrap ≥ 0.35.
2. ECE de tous les modèles ≤ 0.02 sans calibrateur séparé (ou avec, si nécessaire).
3. AP out-of-distribution (géo) ≥ AP in-distribution − 3 pp pour le modèle de référence.
4. Service `/api/v2/predictions/{siren}` opérationnel, smoke-tests passent.
5. Rapport V2 rédigé et défendable.

Si l'un de ces critères échoue, le rapport V2 documente l'échec et ses causes — ce qui reste un résultat académique défendable.
