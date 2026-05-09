# Analyse Complète Du Rapport Final Colab Et Plan D'Amélioration

Ce document est un fichier de travail destiné à être donné à un autre modèle IA ou à un assistant de développement afin d'améliorer le projet.

Il contient :

1. Ce qui a été bien amélioré dans la nouvelle version.
2. Ce qui reste faible ou manquant.
3. Les actions concrètes à faire.
4. Des conseils techniques.
5. Une prompt complète à donner à un modèle IA pour corriger/améliorer le projet.

---

# 1. Avis Général

La nouvelle version du rapport est beaucoup plus forte que la première édition.

Elle améliore plusieurs faiblesses importantes :

```text
- Le pipeline n'est plus seulement théorique.
- Le notebook Colab final exécute la chaîne de bout en bout.
- Le stockage local rapide `/content/pfe_work` est ajouté pour éviter la lenteur de Google Drive.
- Le traitement BODACC historique est mieux expliqué.
- Les archives BODACC imbriquées sont prises en charge.
- INPI est inclus avec les comptes annuels et les formalités.
- Les features et labels sont mieux documentés.
- Un modèle baseline est entraîné.
- Un audit est généré.
- La cible globale `continuity_risk_12m_label` est clarifiée.
- Les labels secondaires sont mieux distingués.
- Les données financières manquantes sont mieux traitées.
```

Cependant, plusieurs faiblesses importantes restent à corriger avant de considérer le modèle comme réellement défendable.

Le problème principal n'est pas encore le choix du modèle.  
Le problème principal est :

```text
Est-ce que les labels, les features historiques et les contrôles anti-leakage sont réellement corrects ?
```

---

# 2. Ce Qui A Été Bien Amélioré

## 2.1 Le Pipeline Est Maintenant Plus Concret

Avant, le projet pouvait sembler surtout conceptuel.  
Maintenant, le rapport montre que le pipeline Colab final exécute :

```text
téléchargement -> raw -> clean -> features -> train -> audit
```

La commande finale inclut :

```bash
python collabs/full_pipeline.py \
  --drive-root "$DRIVE_ROOT" \
  --work-dir "$WORK_DIR" \
  --repo-dir "$BACKEND_DIR" \
  --insee \
  --bilan \
  --inpi \
  --bodacc \
  --bodacc-mode historical \
  --bodacc-families PCL RCS-B \
  --bodacc-start-year 2008 \
  --bodacc-end-year 2025 \
  --start-year 2017 \
  --end-year 2025 \
  --train \
  --audit
```

Cela rend le travail beaucoup plus défendable.

---

## 2.2 Le Problème BODACC Historique Est Mieux Traité

La nouvelle version explique que BODACC n'a pas une structure unique.

Exemples :

```text
2017/
2018/
2019/
2020/
2021/
2022.tar.gz
2023.tar.gz
2024.tar.gz
2025.tar.gz
BODACC_2008.tar
...
BODACC_2016.tar
```

Elle explique aussi que certaines archives contiennent d'autres archives :

```text
BODACC_2016.tar
  BILAN_BXC20160001.taz
    BILAN_BXC20160001.xml
```

Le pipeline ouvre maintenant les archives annuelles, détecte les `.taz` internes et lit les XML.

C'est une amélioration majeure, car BODACC est l'une des sources les plus importantes pour les procédures collectives, radiations et événements légaux.

---

## 2.3 INPI Est Mieux Intégré

Le rapport indique que le run final active :

```text
--inpi
```

et inclut :

```text
comptes_annuels
formalites
```

C'est important car :

```text
- les comptes annuels aident à mesurer la régularité de dépôt ;
- les formalités peuvent signaler des cessations, radiations ou fermetures ;
- INPI complète BODACC, qui ne couvre pas exactement la même logique métier.
```

---

## 2.4 La Cible De Prédiction Est Mieux Clarifiée

La nouvelle version explique que :

```text
continuity_risk_12m_label
```

n'est pas une faillite stricte.

C'est un label global qui peut inclure :

```text
- fermeture administrative ;
- radiation ;
- procédure collective ;
- liquidation ;
- redressement ;
- sauvegarde ;
- signal INPI de cessation/radiation.
```

Et les labels secondaires permettent de distinguer :

```text
legal_distress_risk_12m_label
radiation_risk_12m_label
financial_weakness_risk_12m_label
filing_anomaly_risk_12m_label
```

C'est beaucoup plus défendable.

---

## 2.5 Les Données Financières Manquantes Sont Mieux Gérées

La nouvelle version ajoute des variables importantes :

```text
has_financial_data
financial_years_available
latest_financial_year
years_since_last_financial_statement
has_confidential_financials
```

C'est une bonne réponse à la faiblesse suivante :

```text
Une donnée financière manquante ne veut pas forcément dire que l'entreprise est en mauvaise santé.
```

Elle peut être absente parce que :

```text
- l'entreprise n'est pas obligée de publier ;
- les comptes sont confidentiels ;
- la donnée est retardée ;
- la source est incomplète ;
- l'extraction n'a pas trouvé la donnée.
```

---

## 2.6 Un Modèle Baseline Est Maintenant Présent

Le rapport donne des résultats concrets :

```text
900 000 lignes company-year
Accuracy = 0,99397
ROC AUC = 0,97602
Average precision = 0,06182
```

C'est utile pour montrer que la chaîne ML fonctionne.

Cependant, ces métriques ne doivent pas encore être présentées comme résultat final, car les labels positifs sont extrêmement rares.

---

# 3. Ce Qui Reste Faible Ou Manquant

## 3.1 Les Labels Positifs Sont Trop Rares Et Suspects

### Problème

Le rapport indique cette distribution :

```text
2017 : 119 positifs
2018 : 204 positifs
2019 : 72 positifs
2020 : 56 positifs
2021-2025 : 0 positif
```

sur :

```text
900 000 lignes company-year
```

C'est le plus gros signal d'alerte.

### Pourquoi C'est Grave

Si les années 2021 à 2025 ont zéro positif, cela peut signifier :

```text
1. Les archives BODACC ou INPI futures ne sont pas bien utilisées pour les labels.
2. Les dates d'événements sont mal parsées.
3. Les fenêtres futures de 12 mois ne sont pas bien construites.
4. Le mapping des événements à risque est incomplet.
5. Le sample de 100 000 entreprises ne contient pas assez d'événements.
6. La logique du label est trop stricte.
7. Les sources 2021-2025 ne sont pas réellement présentes dans le clean.
8. Les événements sont présents mais non reconnus comme liquidation/radiation/cessation.
```

### Ce Qu'il Faut Faire

Créer un audit dédié aux labels :

```text
reports/label_audit.md
```

Cet audit doit contenir :

```text
- nombre de labels positifs par année ;
- nombre de labels positifs par source ;
- nombre de labels positifs par famille d'événements ;
- nombre d'événements futurs disponibles avant transformation en label ;
- taux positif par année ;
- exemples de lignes positives ;
- exemples d'événements utilisés pour construire les labels ;
- vérification des fenêtres de 12 mois.
```

### Tableau À Ajouter

```markdown
| prediction_year | BODACC positives | INPI positives | INSEE positives | financial positives | total positives |
|---|---:|---:|---:|---:|---:|
| 2017 | ... | ... | ... | ... | ... |
| 2018 | ... | ... | ... | ... | ... |
| 2019 | ... | ... | ... | ... | ... |
| 2020 | ... | ... | ... | ... | ... |
| 2021 | ... | ... | ... | ... | ... |
| 2022 | ... | ... | ... | ... | ... |
| 2023 | ... | ... | ... | ... | ... |
| 2024 | ... | ... | ... | ... | ... |
| 2025 | ... | ... | ... | ... | ... |
```

### Tableau Par Type D'Événement

```markdown
| Event family | Source | Count used as label |
|---|---|---:|
| liquidation | BODACC | ... |
| redressement | BODACC | ... |
| sauvegarde | BODACC | ... |
| radiation | BODACC / INPI | ... |
| cessation formalité | INPI | ... |
| fermeture administrative | INSEE | ... |
| negative equity next year | financials | ... |
| negative result next year | financials | ... |
```

---

## 3.2 ROC AUC Très Haut Mais Average Precision Très Faible

### Problème

Le rapport donne :

```text
ROC AUC = 0,97602
Average precision = 0,06182
```

Cela signifie que le modèle semble bien classer les entreprises globalement, mais la précision opérationnelle sur les vrais positifs reste faible.

### Pourquoi C'est Important

Quand les positifs sont très rares, le ROC AUC peut être élevé même si les alertes ne sont pas très utiles en pratique.

La métrique la plus importante devient :

```text
PR-AUC / Average Precision
Precision
Recall
Top-k capture
```

### Ce Qu'il Faut Faire

Ajouter une évaluation top-k.

Exemple :

```markdown
| Top risk group | Companies | True positives captured | Precision | Recall |
|---|---:|---:|---:|---:|
| Top 1% | ... | ... | ... | ... |
| Top 5% | ... | ... | ... | ... |
| Top 10% | ... | ... | ... | ... |
```

Question métier importante :

```text
Parmi les 5 % d'entreprises les plus risquées, combien d'événements réels sont capturés ?
```

Cela sera beaucoup plus utile pour un outil d'intelligence entreprise qu'une simple accuracy.

---

## 3.3 Les Tests Anti-Leakage Sont Encore À Prouver

### Problème

Le rapport explique bien la règle :

```text
features: event_date <= prediction_date
labels: prediction_date < event_date <= prediction_date + 12 mois
```

Mais cette règle est encore surtout déclarative.

Il faut maintenant une preuve automatique.

### Pourquoi C'est Grave

Une fuite temporelle peut rendre tout le modèle invalide.

Exemples de fuites possibles :

```text
- utiliser une date de radiation future comme feature ;
- utiliser le statut administratif actuel pour une année passée ;
- compter des événements BODACC futurs dans les features ;
- calculer `days_since_last_event` depuis aujourd'hui au lieu de `prediction_date` ;
- inclure `first_future_legal_event_date` dans les features ;
- inclure des colonnes de label dans X_train.
```

### Ce Qu'il Faut Faire

Créer un audit :

```text
reports/leakage_audit.md
```

Avec un tableau PASS/FAIL :

```markdown
| Leakage check | Result | Details |
|---|---|---|
| Future events excluded from features | PASS/FAIL | max feature event date <= prediction_date |
| Label events strictly after prediction date | PASS/FAIL | min label event date > prediction_date |
| Target columns excluded from X_train | PASS/FAIL | no label columns in features |
| `first_future_legal_event_date` excluded | PASS/FAIL | audit-only column |
| `siren` excluded from model features | PASS/FAIL | no memorization |
| Financial years after prediction year excluded | PASS/FAIL | financial year <= prediction_year |
| Current-only snapshot fields marked unsafe | PASS/FAIL | verified feature safety |
```

### Exemple De Tests À Implémenter

```python
FORBIDDEN_FEATURE_COLUMNS = [
    "continuity_risk_12m_label",
    "legal_distress_risk_12m_label",
    "radiation_risk_12m_label",
    "financial_weakness_risk_12m_label",
    "filing_anomaly_risk_12m_label",
    "first_future_legal_event_date",
    "future_event_date",
    "date_radiation",
    "date_cessation",
]

def check_forbidden_columns(feature_columns):
    forbidden_found = sorted(set(feature_columns) & set(FORBIDDEN_FEATURE_COLUMNS))
    assert not forbidden_found, f"Forbidden leakage columns found: {forbidden_found}"


def check_feature_dates(feature_events):
    violations = feature_events[feature_events["event_date"] > feature_events["prediction_date"]]
    assert len(violations) == 0, "Some future events are used as features"


def check_label_dates(label_events):
    violations = label_events[label_events["event_date"] <= label_events["prediction_date"]]
    assert len(violations) == 0, "Some past/current events are used as future labels"
```

---

## 3.4 La Validité Historique Des Features N'Est Pas Encore Totalement Prouvée

### Problème

Le rapport utilise des features comme :

```text
administrative_status_at_cutoff
legal_category_code
employee_size_bracket
company_age_years
```

Certaines sont sûres, mais d'autres peuvent être dangereuses si elles viennent d'un snapshot actuel.

### Pourquoi C'est Important

Le modèle company-year doit utiliser uniquement ce qui était connu à l'année de prédiction.

Exemple :

```text
Pour prediction_year = 2021,
on ne doit pas utiliser un statut administratif observé en 2026.
```

### Ce Qu'il Faut Faire

Créer une table de sécurité des features :

```text
reports/feature_safety_audit.md
```

### Tableau À Ajouter

```markdown
| Feature | Source | Historical validity | Status | Action |
|---|---|---|---|---|
| company_age_years | INSEE | safe if based on creation date | OK | keep |
| administrative_status_at_cutoff | INSEE | dangerous if from current snapshot only | VERIFY | confirm historical source or exclude |
| legal_category_code | INSEE | may change over time | VERIFY | use only if historical or mark snapshot |
| employee_size_bracket | INSEE | may be current only | VERIFY | check vintage/source date |
| legal_events_count_12m | BODACC | safe if event_date filtered | OK | keep |
| latest_revenue | financials | safe if fiscal year <= prediction_year | OK | keep |
| latest_financial_year | financials | safe if <= prediction_year | OK | keep |
| days_since_last_legal_event | BODACC | safe if computed from prediction_date | OK | keep |
```

### Catégories À Utiliser

```text
safe_historical
safe_event_based
safe_derived_from_historical_date
unsafe_current_snapshot
excluded
needs_verification
```

---

## 3.5 La Stratégie MongoDB Serving Reste Trop Abstraite

### Problème

Le rapport parle de :

```text
company_features
latest snapshot
features latest-company
```

Mais il ne montre pas encore clairement les collections MongoDB finales.

### Pourquoi C'est Important

Le projet n'est pas seulement un notebook ML.  
Il doit aussi servir des données au frontend.

Si MongoDB est mal organisé, le projet peut devenir difficile à maintenir.

### Ce Qu'il Faut Faire

Ajouter une section :

```text
Stratégie De Serving MongoDB
```

Avec les collections :

```text
companies
company_profiles
company_predictions
company_events_summary
pipeline_runs
model_versions
source_freshness
```

### Exemple De Document MongoDB

```json
{
  "siren": "123456789",
  "company_name": "Example SAS",
  "identity": {
    "activity_code": "6201Z",
    "legal_category_code": "5710",
    "employee_size_bracket": "10-19",
    "company_age_years": 8
  },
  "latest_prediction": {
    "score": 0.72,
    "risk_level": "High",
    "prediction_date": "2025-12-31",
    "model_version": "baseline_lr_v1"
  },
  "risk_breakdown": {
    "global_continuity": 0.72,
    "legal": 0.61,
    "financial": 0.44,
    "registry": 0.55,
    "administrative": 0.30
  },
  "main_factors": [
    "recent legal-risk event",
    "late account filing",
    "negative equity history"
  ],
  "source_freshness": {
    "insee": "2026-05-09",
    "inpi": "2026-05-09",
    "bodacc": "2026-05-09",
    "financials": "2025-12-31"
  },
  "pipeline_run_id": "run_2026_05_09",
  "created_at": "2026-05-09T22:00:00Z"
}
```

---

## 3.6 La Calibration Est Mentionnée Mais Pas Encore Réalisée

### Problème

Le rapport mentionne la calibration comme future évaluation, mais ne donne pas encore de résultat.

### Pourquoi C'est Important

Pour un score de risque, la probabilité doit avoir un sens.

Si le modèle dit :

```text
risque = 80 %
```

cela devrait vouloir dire approximativement :

```text
Parmi les entreprises similaires, environ 80 % ont eu un événement de risque.
```

Mais beaucoup de modèles ML ne sont pas naturellement calibrés.

### Ce Qu'il Faut Faire

Ajouter :

```text
Brier score
calibration curve
reliability table
```

### Tableau De Calibration À Ajouter

```markdown
| Predicted risk bucket | Number of companies | Average predicted risk | Observed event rate |
|---|---:|---:|---:|
| 0-1% | ... | ... | ... |
| 1-5% | ... | ... | ... |
| 5-10% | ... | ... | ... |
| 10-25% | ... | ... | ... |
| 25%+ | ... | ... | ... |
```

### Méthodes Possibles

```text
Platt scaling
Isotonic calibration
CalibratedClassifierCV
```

---

## 3.7 L'Explainability Est Encore Trop Conceptuelle

### Problème

Le rapport explique les features et les labels, mais ne montre pas encore un exemple complet d'explication de prédiction.

### Pourquoi C'est Important

Le frontend ne doit pas seulement afficher :

```text
risk_score = 0.81
```

Il doit expliquer pourquoi.

Mais il ne faut pas que l'explication soit inventée par un LLM.

Elle doit venir de :

```text
model features + source evidence
```

### Ce Qu'il Faut Faire

Ajouter une section :

```text
Exemple D'Explication De Prédiction
```

### Exemple À Ajouter

```text
Entreprise : Example SAS
SIREN : 123456789

Score de continuité : 78 %
Niveau : Élevé

Facteurs principaux :
1. 2 événements BODACC à risque dans les 12 derniers mois
2. Dernier dépôt de comptes ancien
3. Capitaux propres négatifs dans le dernier bilan disponible

Preuves :
- BODACC PCL, date : 2025-03-12
- INPI compte annuel, closing_date : 2022-12-31
- Données financières, année : 2023, capitaux propres négatifs

Action recommandée :
Vérifier les annonces légales récentes et demander des documents financiers actualisés.
```

---

## 3.8 Le Label De Faiblesse Financière Est Encore Trop Simple

### Problème

Le rapport définit :

```text
financial_weakness_risk_12m_label
```

avec :

```text
résultat net négatif ou capitaux propres négatifs l'année suivante
```

C'est mieux qu'avant, mais encore un peu faible.

### Pourquoi C'est Important

Un résultat net négatif isolé n'est pas toujours une faiblesse grave.  
Certaines entreprises peuvent avoir une mauvaise année et rester solides.

### Amélioration Recommandée

Définir le label financier avec plusieurs signaux :

```text
financial_weakness_risk_12m_label = 1 si au moins un des critères suivants est vrai :

- capitaux propres négatifs ;
- résultat net négatif répété ;
- forte baisse du chiffre d'affaires ;
- ratio dette / actifs très élevé ;
- marge nette fortement dégradée ;
- baisse importante des capitaux propres.
```

Il faut aussi rappeler que ce label est :

```text
un label dérivé financier
```

et non :

```text
un événement officiel comme une liquidation ou radiation.
```

---

## 3.9 Clarifier Si L'Audit Est Baseline Ou Full Run

### Problème

Le rapport dit que le pipeline final est exécuté sans limite de test.

Mais plus loin, il indique :

```text
audit exécuté sur un échantillon plafonné à 100 000 entreprises
```

Cela peut créer une confusion.

### Ce Qu'il Faut Faire

Séparer clairement :

```text
Run baseline d'audit :
- limité à 100 000 entreprises
- utilisé pour validation technique

Run final attendu :
- sans limite --max-companies
- utilisé pour métriques finales
```

### Formulation Recommandée

```text
Les résultats présentés dans cette section correspondent à un run baseline plafonné à 100 000 entreprises.
Ce run valide le fonctionnement technique de bout en bout.
Les métriques finales devront être recalculées après le run complet sans limitation.
```

---

# 4. Priorités D'Amélioration

## Priorité 1 — Auditer Les Labels

C'est la priorité absolue.

À faire :

```text
1. Compter les événements futurs par année.
2. Compter les événements futurs par source.
3. Compter les événements futurs par type.
4. Vérifier le parsing de `event_date`.
5. Vérifier le mapping liquidation/redressement/sauvegarde/radiation/cessation.
6. Vérifier les fenêtres futures de 12 mois.
7. Comprendre pourquoi 2021-2025 ont 0 positif.
```

Livrable attendu :

```text
reports/label_audit.md
```

---

## Priorité 2 — Ajouter Les Tests Anti-Leakage

À faire :

```text
1. Vérifier que les features n'utilisent jamais d'événements futurs.
2. Vérifier que les labels utilisent seulement des événements après prediction_date.
3. Vérifier que les colonnes de labels sont exclues de X_train.
4. Vérifier que `first_future_legal_event_date` est exclue.
5. Vérifier que `siren` est exclu.
6. Vérifier que les données financières futures sont exclues.
```

Livrable attendu :

```text
reports/leakage_audit.md
```

---

## Priorité 3 — Auditer La Validité Historique Des Features

À faire :

```text
1. Lister toutes les features.
2. Identifier leur source.
3. Dire si elles sont historiques, event-based, dérivées ou current snapshot.
4. Exclure ou marquer les features dangereuses.
```

Livrable attendu :

```text
reports/feature_safety_audit.md
```

---

## Priorité 4 — Ajouter L'Évaluation Top-K

À faire :

```text
1. Trier les entreprises par score de risque décroissant.
2. Calculer les vrais positifs capturés dans le top 1 %, 5 %, 10 %.
3. Calculer precision et recall pour chaque groupe.
```

Livrable attendu :

```text
reports/top_k_evaluation.md
```

---

## Priorité 5 — Ajouter La Calibration

À faire :

```text
1. Calculer le Brier score.
2. Générer une reliability table.
3. Créer une courbe de calibration.
4. Tester CalibratedClassifierCV si nécessaire.
```

Livrable attendu :

```text
reports/calibration_report.md
```

---

## Priorité 6 — Définir Les Documents MongoDB De Serving

À faire :

```text
1. Définir les collections finales.
2. Définir un document de profil entreprise.
3. Définir un document de prédiction.
4. Ajouter source_freshness.
5. Ajouter model_version et pipeline_run_id.
```

Livrable attendu :

```text
docs/mongodb_serving_design.md
```

---

## Priorité 7 — Ajouter Un Exemple D'Explication

À faire :

```text
1. Prendre une entreprise avec score élevé.
2. Lister les top facteurs.
3. Relier chaque facteur à une source.
4. Générer une explication lisible.
5. Ajouter une action recommandée prudente.
```

Livrable attendu :

```text
reports/prediction_explanation_examples.md
```

---

# 5. Prompt À Donner À Un Modèle IA Pour Améliorer Le Projet

Tu peux donner le prompt suivant à ton modèle IA ou à ton assistant de code.

---

## Prompt Complète

```text
Tu es un expert senior en data engineering, machine learning temporel, MLOps et audit de modèles prédictifs.

Je travaille sur un projet PFE qui construit une plateforme d'intelligence entreprise et de prédiction du risque de continuité d'activité des entreprises françaises.

Le projet utilise plusieurs sources :
- INSEE Sirene pour l'identité, statut administratif, activité, catégorie juridique, établissements.
- INPI / RNE pour les formalités et les comptes annuels.
- BODACC / DILA pour les événements légaux, radiations, procédures collectives, liquidations, redressements, sauvegardes.
- Données financières data.gouv.fr au format Parquet pour chiffre d'affaires, résultat net, capitaux propres, dettes, actifs et ratios.

L'architecture actuelle est :
source archives -> data-lake/raw -> data-lake/clean -> data-lake/features -> ml-artifacts -> MongoDB serving -> FastAPI/frontend.

Le pipeline Colab final exécute :
- téléchargement / réutilisation des sources ;
- export raw Parquet ;
- clean build ;
- features company-year ;
- labels futurs 12 mois ;
- entraînement baseline ;
- audit.

La commande principale ressemble à :

python collabs/full_pipeline.py \
  --drive-root "$DRIVE_ROOT" \
  --work-dir "$WORK_DIR" \
  --repo-dir "$BACKEND_DIR" \
  --insee \
  --bilan \
  --inpi \
  --bodacc \
  --bodacc-mode historical \
  --bodacc-families PCL RCS-B \
  --bodacc-start-year 2008 \
  --bodacc-end-year 2025 \
  --start-year 2017 \
  --end-year 2025 \
  --train \
  --audit

Le modèle baseline actuel est une régression logistique avec pondération des classes.
Un run baseline donne :
- 900 000 lignes company-year ;
- Accuracy = 0,99397 ;
- ROC AUC = 0,97602 ;
- Average precision = 0,06182.

La distribution des labels positifs est suspecte :
- 2017 : 119 positifs ;
- 2018 : 204 positifs ;
- 2019 : 72 positifs ;
- 2020 : 56 positifs ;
- 2021-2025 : 0 positif.

Je veux que tu améliores le projet en priorité sur la validité des données et non seulement sur le choix du modèle.

Ta mission :

1. Ajouter un audit complet des labels dans `reports/label_audit.md`.
   Il doit compter les labels positifs par année, source et famille d'événements.
   Il doit expliquer pourquoi 2021-2025 ont 0 positif.
   Il doit vérifier le parsing des dates, la disponibilité des sources, et le mapping des événements à risque.

2. Ajouter un audit anti-leakage dans `reports/leakage_audit.md`.
   Il doit vérifier :
   - aucune feature ne vient après `prediction_date` ;
   - aucun label ne vient avant ou à `prediction_date` ;
   - les colonnes de labels ne sont pas dans X_train ;
   - `first_future_legal_event_date` est exclue de l'entraînement ;
   - `siren` est exclu des features ;
   - les données financières utilisées comme features ont `financial_year <= prediction_year`.

3. Ajouter un audit de validité historique des features dans `reports/feature_safety_audit.md`.
   Pour chaque feature, classer :
   - safe_historical ;
   - safe_event_based ;
   - safe_derived_from_historical_date ;
   - unsafe_current_snapshot ;
   - excluded ;
   - needs_verification.
   Attention aux champs INSEE comme `administrative_status_at_cutoff`, `legal_category_code`, `employee_size_bracket`.
   Vérifier qu'ils sont valides à la date de prédiction et non pris depuis un snapshot actuel.

4. Ajouter une évaluation top-k dans `reports/top_k_evaluation.md`.
   Calculer :
   - top 1 % ;
   - top 5 % ;
   - top 10 %.
   Pour chaque groupe, donner :
   - nombre d'entreprises ;
   - vrais positifs capturés ;
   - precision ;
   - recall.

5. Ajouter une calibration dans `reports/calibration_report.md`.
   Inclure :
   - Brier score ;
   - table de calibration par buckets ;
   - courbe de calibration si possible ;
   - recommandation sur Platt scaling, isotonic calibration ou CalibratedClassifierCV.

6. Améliorer la définition de `financial_weakness_risk_12m_label`.
   Ne pas se limiter à résultat net négatif ou capitaux propres négatifs.
   Proposer une définition plus robuste incluant :
   - capitaux propres négatifs ;
   - résultat net négatif répété ;
   - forte baisse du chiffre d'affaires ;
   - ratio dette / actifs très élevé ;
   - marge nette fortement dégradée ;
   - baisse importante des capitaux propres.
   Garder ce label séparé des labels légaux officiels.

7. Ajouter une section ou un document `docs/mongodb_serving_design.md`.
   Définir les collections :
   - companies ;
   - company_profiles ;
   - company_predictions ;
   - company_events_summary ;
   - pipeline_runs ;
   - model_versions ;
   - source_freshness.
   Donner un exemple de document MongoDB final pour le frontend avec :
   - siren ;
   - identité ;
   - latest_prediction ;
   - risk_breakdown ;
   - main_factors ;
   - source_freshness ;
   - model_version ;
   - pipeline_run_id.

8. Ajouter un document `reports/prediction_explanation_examples.md`.
   Il doit montrer comment transformer une prédiction en explication utilisateur.
   L'explication doit venir des features et des preuves source, pas être inventée.
   Exemple :
   - score ;
   - niveau ;
   - top facteurs ;
   - preuves BODACC/INPI/financials ;
   - action recommandée prudente.

9. Clarifier dans le rapport la différence entre :
   - run baseline limité à 100 000 entreprises ;
   - run final complet sans limite.
   Ne pas présenter les métriques baseline comme des métriques finales.

10. Ne pas entraîner un modèle plus complexe avant d'avoir corrigé :
   - les labels ;
   - le leakage ;
   - la validité historique des features.
   Ensuite seulement comparer Logistic Regression, LightGBM, XGBoost, CatBoost et modèles calibrés.

Génère les modifications sous forme de code ou de fichiers Markdown selon ce qui existe dans le projet.
Explique aussi les hypothèses et les limites restantes.
```

---

# 6. Prompt Courte Si Tu Veux Une Version Plus Légère

```text
Analyse mon pipeline ML temporel pour prédire le risque de continuité des entreprises.
Ne cherche pas d'abord à améliorer le modèle.
Priorité :
1. auditer les labels, surtout pourquoi 2021-2025 ont 0 positif ;
2. ajouter des tests anti-leakage ;
3. vérifier la validité historique des features ;
4. ajouter top-k evaluation ;
5. ajouter calibration ;
6. définir les documents MongoDB de serving ;
7. ajouter un exemple d'explication de prédiction basé sur les features et sources.

Le projet utilise INSEE, INPI, BODACC et données financières.
La table principale est company-year avec prediction_date au 31 décembre.
Les features doivent être <= prediction_date.
Les labels doivent être dans les 12 mois après prediction_date.
```

---

# 7. Checklist Finale

Avant de dire que le projet est prêt, il faut obtenir :

```text
[ ] Label audit complet
[ ] Explication des 0 positifs entre 2021 et 2025
[ ] Leakage audit PASS
[ ] Feature safety audit PASS
[ ] Top-k evaluation
[ ] Calibration report
[ ] Définition renforcée du label financier
[ ] MongoDB serving design
[ ] Exemple d'explication de prédiction
[ ] Clarification baseline run vs full run
[ ] Métriques recalculées après full run
```

---

# 8. Conclusion

La nouvelle version du rapport est une vraie amélioration.

Elle montre que le pipeline devient exécutable, structuré et plus défendable.

Mais le projet ne doit pas encore être jugé uniquement sur les métriques du modèle baseline.

Les points les plus importants à corriger maintenant sont :

```text
1. Les labels positifs trop rares et absents de 2021 à 2025.
2. Les tests anti-leakage automatiques.
3. La validité historique des features.
4. L'évaluation top-k.
5. La calibration du score.
6. Les documents MongoDB de serving.
7. Les explications de prédiction basées sur les sources.
```

Le prochain objectif n'est donc pas de chercher directement un modèle plus puissant.

Le prochain objectif est :

```text
rendre les données, les labels et les features incontestables.
```

Une fois cela fait, les modèles plus avancés comme LightGBM, XGBoost ou CatBoost auront beaucoup plus de sens.
