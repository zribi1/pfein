# V2 — Décisions de conception et leur justification

Ce document accompagne le rapport V2 et le mémoire de soutenance. Il regroupe sept décisions structurantes de la V2, chacune motivée par une observation issue de la V1 et défendue par un argument académique. Le mémoire peut citer ces paragraphes mot pour mot dans la section « Limites » ou dans une discussion comparative.

---

## D1 — Identité INSEE période-aware (vs. snapshot exclu)

**Décision V1.** La table `clean/company_identity` est construite via DuckDB `row_number() OVER (PARTITION BY siren ORDER BY source_updated_at DESC) = 1` qui garde une seule ligne par SIREN, la plus récente. Cela contamine temporellement les features d'identité (Run 1 V1 : AUC 0.87 illégitime). La correction V1 a consisté à **exclure** ces quatre variables de l'entrée modèle.

**Décision V2.** Reconstruire l'identité depuis `data-lake/raw/insee/bulk/stock_unite_legale_historique/` qui contient un row par `(siren, date_debut_periode, date_fin_periode)`. Jointure avec les features sur la condition `period_start <= prediction_date < period_end`.

**Justification.** L'identité historique d'une entreprise est une variable explicative parfaitement légitime à condition d'être servie à la bonne date. L'analyse SHAP V1 (Phase D) montre que ces variables auraient été les drivers #1, #3 et #4 du modèle. Estimation prudente du gain : +5 à +10 pp d'AP.

**Risque.** Si certaines SIRENs n'ont pas d'historique périodique (cas marginaux), la jointure produit du NaN. Le HGB gère naturellement ces NaN, donc le risque est faible et borné par le taux de couverture (à mesurer en Phase 2).

---

## D2 — Pas de `class_weight='balanced'`

**Décision V1.** Tous les classifieurs sont entraînés avec `class_weight='balanced'`. C'est la valeur par défaut "raisonnable" pour le déséquilibre de classes (taux de positifs 3-4 %).

**Décision V2.** Entraîner sans `class_weight`, donc avec la perte log-likelihood naturelle.

**Justification.** Trois raisons :

1. **Calibration native.** `class_weight='balanced'` déplace la sortie `predict_proba` vers la classe minoritaire. En V1 cela a produit une probabilité moyenne de 35 % pour un taux observé de 4 %, soit une sur-confiance d'un facteur 8 (Phase E V1 : ECE = 0.305). On a dû corriger via un calibrateur isotonique séparé. Sans `class_weight`, les probabilités brutes sont déjà du bon ordre.

2. **Le classement n'a pas besoin de pondération.** Les arbres de décision boostés gèrent le déséquilibre via la structure de l'arbre lui-même (split sur impureté) et la perte log-likelihood (qui amplifie les erreurs sur la classe minoritaire en logarithme). La pondération explicite est une optimisation pour le seuil 0.5 par défaut, pas pour le classement.

3. **Simplicité opérationnelle.** Pas de calibrateur séparé à charger en production. Le `MLRegistry` V2 ne sert qu'un seul artefact `.joblib` par label. La logique de calcul du tier est une simple comparaison à un seuil.

**Risque.** Si la calibration sans `class_weight` reste mauvaise (ECE > 0.02), on rajoute `CalibratedClassifierCV` en Phase 8. On a une boucle de secours.

---

## D3 — Modèles par étiquette (vs. cible composite)

**Décision V1.** Un seul modèle entraîné sur `continuity_risk_12m_label` qui est l'union (OR) de quatre signaux : cessation INSEE, radiation BODACC, procédure collective BODACC, formalité INPI cessation.

**Décision V2.** Quatre modèles HGB, un par étiquette : `legal_distress_risk_12m_label`, `radiation_risk_12m_label`, `financial_weakness_risk_12m_label`, `filing_anomaly_risk_12m_label`. Le modèle sur la cible composite est conservé comme modèle de référence et de comparaison V1/V2.

**Justification.** Les quatre événements ont des dynamiques prédictives très différentes :

- **Procédure collective** : forte prédictibilité (signaux comptables, juridiques et événementiels en amont sur 12-24 mois). AP attendu : 0.5 à 0.7.
- **Radiation administrative** : prédictibilité moyenne (souvent suivie d'événements observables, mais aussi parfois "spontanée"). AP attendu : 0.2 à 0.4.
- **Cessation INSEE volontaire** : faible prédictibilité (entreprise individuelle qui ferme par choix, peu de signaux préalables). AP attendu : 0.1 à 0.2.
- **Faiblesse financière** : prédictibilité élevée mais sur une population restreinte (les déposantes). AP attendu sur les déposantes : 0.4 à 0.6.

Agréger les quatre dilue le signal de la procédure collective dans le bruit des cessations volontaires. Quatre modèles spécialisés exposent des probabilités **interprétables** à l'utilisateur ("risque de procédure collective : 18 %, risque de radiation administrative : 42 %") au lieu d'une probabilité composite floue.

**Risque.** Quadruple le compute d'entraînement (~4× plus). Coût négligeable étant donné qu'un entraînement HGB sur 2M lignes prend 10 min.

---

## D4 — Itération à 100K rows avant 2M

**Décision V1.** Les premiers runs ont tourné sur 2M lignes (10 min par fit), ce qui a découragé la curiosité et permis l'accumulation de 7 runs LogReg avant de détecter la fuite INSEE.

**Décision V2.** Phase 3 explicite à 100K lignes pour itération rapide (< 1 min par fit) avant tout sweep à grande échelle.

**Justification.** Discipline d'ingénieur ML. Le coût d'opportunité d'un fit lent est l'absence d'exploration. À 100K lignes, on peut tester une intuition en < 5 minutes et boucler rapidement. À 2M, on hésite à essayer.

**Risque.** Aucun — le sample 100K est un sous-ensemble strict du sample 2M, les conclusions à 100K se transposent à 2M (modulo une légère perte de précision sur les métriques de tail).

---

## D5 — CalibratedClassifierCV (vs. découpage trois-temps)

**Décision V1.** Phase E utilise un découpage train (2017-2021) / calibration (2022) / test (2023). Cela coûte une année de training data ; l'AP passe de 0.30 à 0.22 sur 2023.

**Décision V2.** Si la calibration sans `class_weight` est insuffisante, utiliser `sklearn.calibration.CalibratedClassifierCV(method='isotonic', cv=5)` qui fait la calibration par K-fold cross-validation interne sur l'ensemble d'entraînement.

**Justification.** Trois raisons :

1. **Pas de perte de données.** L'année 2022 reste dans l'entraînement.
2. **Méthodologiquement plus standard.** `CalibratedClassifierCV` est l'outil de référence sklearn pour cette tâche.
3. **Moins de complications temporelles.** Avec le découpage trois-temps, on hérite des défis de la maturation d'étiquettes sur deux années au lieu d'une. CalibratedClassifierCV utilise le même train set, donc l'effet de maturation est constant.

**Risque.** `CalibratedClassifierCV` produit un ensemble de K modèles (un par fold) — légère complexité au chargement. Le surcoût mémoire est négligeable.

---

## D6 — Bootstrap confidence intervals sur les métriques

**Décision V1.** Toutes les métriques sont reportées comme des nombres ponctuels (`AP 0.299, AUC 0.877, F1 0.222`).

**Décision V2.** Bootstrap à B = 1000 échantillons sur le test set pour chaque métrique principale. Reporter au format `AP = 0.299 [0.281, 0.317]`.

**Justification.** Trois raisons :

1. **Honnêteté académique.** Un jury de soutenance peut demander « la différence entre 0.30 et 0.32 est-elle significative ? ». Sans CI, la réponse est spéculative.
2. **Comparaison V1 vs V2.** Pour défendre que V2 améliore V1, il faut montrer que la borne inférieure de V2 dépasse la borne supérieure de V1.
3. **Coût négligeable.** B = 1000 bootstrap × 5 modèles × 3 métriques = quelques minutes de compute.

**Risque.** Aucun.

---

## D7 — Validation externe géographique et sectorielle

**Décision V1.** Toute la validation est temporelle (walk-forward sur les années). Pas de validation hors-distribution géographique ou sectorielle.

**Décision V2.** Deux holdouts supplémentaires :

- **Géographique** : entraîner sur Île-de-France + Sud (~40 % de la population), tester sur les autres départements.
- **Sectoriel** : entraîner sans la section NAF 5 (hébergement-restauration), tester dessus.

**Justification.** Le hash-déterministe garantit que train et test sont des sous-ensembles aléatoires de la même population. Mais la population française n'est pas homogène : les dynamiques de défaillance varient entre départements (effet métropole/ruralité) et entre secteurs (saisonnalité hôtellerie, cycles immobiliers, etc.). Un jury peut suspecter un sur-apprentissage par segment. Les deux holdouts répondent directement à cette suspicion.

**Risque.** La performance hors-distribution peut être inférieure de plusieurs points à la performance in-distribution. C'est un résultat attendu et documentable, pas un échec. La V2 reporte les deux valeurs côte à côte.

---

## Récapitulatif comparatif

| Axe | V1 | V2 |
|---|---|---|
| Identité INSEE | exclue (anti-fuite) | période-aware (réintégrée) |
| Class weight | `balanced` | non utilisé |
| Calibration | calibrateur isotonique séparé | CalibratedClassifierCV interne (si besoin) |
| Cible | composite (OR de 4 signaux) | 4 modèles spécialisés + 1 composite référence |
| Itération | direct à 2M | 100K → 2M |
| Métriques | nombres ponctuels | bootstrap CIs |
| Validation | temporelle (walk-forward) | temporelle + géographique + sectorielle |
| Artefacts servis | 2 (modèle + calibrateur) | 4-5 (un modèle par label) |

V2 n'est ni plus simple ni plus complexe que V1. Elle est **différemment structurée** pour exposer une information plus riche à l'utilisateur final et défendre une méthodologie plus rigoureuse devant un jury.
