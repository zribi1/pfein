# Rapport Académique Du Pipeline Colab Final

## Objectif

Ce rapport présente la version finale du pipeline Google Colab utilisé pour
préparer les données de machine learning du projet. Il reprend la logique du
rapport Colab initial, mais ajoute les améliorations réalisées lors de la phase
finale : exécution complète sans échantillonnage de test, stockage persistant
dans Google Drive, utilisation d'un répertoire de travail local pour accélérer
les traitements, prise en charge des archives BODACC annuelles, génération d'un
audit automatisé et entraînement d'un premier modèle baseline.

L'objectif du pipeline est de transformer des sources publiques et
institutionnelles hétérogènes en tables Parquet exploitables pour l'analyse et
la prédiction du risque de continuité d'activité des entreprises.

## Constats Principaux

Les constats suivants résument les résultats les plus importants de la phase
finale. Ils distinguent les acquis techniques, les preuves observées et les
limites qui doivent rester visibles dans le rapport académique.

| Constat | Preuve Observée | Impact Sur Le Projet |
|---|---|---|
| Le pipeline Colab est exécutable de bout en bout | Le notebook final orchestre téléchargement, export, clean build, features, entraînement et audit | La préparation des données devient reproductible hors machine locale |
| Google Drive seul ralentit les traitements lourds | Les téléchargements, exports Parquet et lectures d'archives sont sensibles aux entrées/sorties Drive | Ajout de `/content/pfe_work` comme espace local rapide, avec synchronisation vers Drive |
| Le flux BODACC historique a une structure mixte | Certaines années sont des dossiers, d'autres des fichiers `BODACC_YYYY.tar` ou `YYYY.tar.gz` | Le downloader ne doit pas supposer une structure unique par famille |
| Certaines archives BODACC sont imbriquées | Exemple : archive annuelle contenant des `.taz`, eux-mêmes contenant les XML | L'exporteur doit ouvrir récursivement les archives pour ne pas perdre des événements |
| Le data lake passe la porte d'audit | Les tables features/labels sont présentes et les contrôles de doublons et de SIREN passent | Le projet peut entraîner un modèle baseline défendable comme validation technique |
| Le modèle baseline est entraînable | 900 000 lignes, ROC AUC `0,97602`, average precision `0,06182` | La chaîne ML fonctionne, mais les métriques doivent être interprétées avec prudence |
| Le label positif est rare | Les taux positifs `continuity_risk_12m_label` sont inférieurs à 0,21 % dans le run baseline | L'accuracy est peu informative ; il faut privilégier average precision, PR-AUC, rappel et top-k |
| Le run final inclut les sources INPI attendues | La commande finale active `--inpi` et télécharge les catégories `comptes_annuels` et `formalites` | Les features et labels peuvent être reconstruits avec les signaux de formalités |

## Contexte

Les traitements de préparation des données sont trop volumineux pour être
exécutés confortablement dans un environnement local classique. Google Colab a
donc été retenu comme environnement d'exécution temporaire, tandis que Google
Drive sert de stockage durable.

Le pipeline final repose sur deux emplacements complémentaires :

| Emplacement | Rôle |
|---|---|
| `/content/pfein` | Copie temporaire du code source dans Colab |
| `/content/pfe_work` | Répertoire local rapide pour les téléchargements, exports et traitements intermédiaires |
| `/content/drive/MyDrive/PFE ML Data/pfe_data` | Stockage durable des archives sources, du data lake, des rapports et des artefacts ML |

Cette organisation réduit le coût d'entrée/sortie de Google Drive pendant les
opérations lourdes, tout en conservant les résultats importants dans un espace
persistant.

## Améliorations Apportées

Les améliorations principales par rapport au pipeline initial sont les
suivantes :

| Élément | Situation initiale | Version finale |
|---|---|---|
| Notebook Colab | Notebook de travail avec cellules de test | Notebook final dédié : `collabs/01_pipeline_donnees_execution_complete.ipynb` |
| Taille d'exécution | Utilisation possible de `--max-files` et `--max-companies` | Exécution finale sans limite de test |
| Stockage Colab | Écriture directe fréquente sur Google Drive | Travail local dans `/content/pfe_work`, puis synchronisation vers Drive |
| BODACC historique | Traitement surtout orienté archives par famille | Prise en charge des dossiers annuels et des bundles `.tar` / `.tar.gz` |
| Archives imbriquées | Cas non couvert complètement | Support des archives annuelles contenant des `.taz`, eux-mêmes contenant du XML |
| Audit | Commande séparée | Option `--audit` intégrée au pipeline |
| Modèle | Entraînement différé | Premier modèle baseline entraîné et documenté |

## Validation Du Partage Drive

Le notebook final commence par une vérification explicite du dossier Drive
partagé. Après le montage de Google Drive, l'utilisateur vérifie que le dossier
attendu est visible :

```text
/content/drive/MyDrive/PFE ML Data/pfe_data
```

La cellule de contrôle valide la présence des dossiers suivants :

```text
data-lake
ml-artifacts
reports
source-archives
```

Si ces dossiers sont présents, le notebook affiche un message de succès. Si le
dossier est absent ou incomplet, l'utilisateur doit ouvrir le dossier partagé
dans Google Drive, ajouter un raccourci dans son espace `My Drive`, ou modifier
la variable `DRIVE_ROOT`.

Cette étape est importante car le notebook peut être partagé indépendamment du
dossier Drive. Sans accès au dossier de données, le code peut être visible mais
les archives, rapports et artefacts ne le sont pas.

## Architecture De Stockage

Le pipeline final distingue trois niveaux de stockage :

| Niveau | Chemin | Description |
|---|---|---|
| Code temporaire | `/content/pfein` | Dépôt Git cloné ou mis à jour dans Colab |
| Travail rapide | `/content/pfe_work` | Téléchargements actifs, exports Parquet, tables propres et features pendant l'exécution |
| Stockage durable | `DRIVE_ROOT` | Copie persistante des sources, sorties et rapports |

Le répertoire local est plus rapide pour :

- les gros téléchargements ;
- la lecture d'archives tar ;
- l'extraction d'archives imbriquées ;
- l'écriture de fichiers Parquet ;
- les traitements DuckDB.

Les résultats terminés sont ensuite synchronisés vers Google Drive. Cela évite
de perdre les sorties importantes lorsque le runtime Colab s'arrête.

## Sources De Données

Le pipeline final mobilise les sources suivantes :

| Source | Fournisseur | Rôle |
|---|---|---|
| INSEE Sirene | INSEE / data.gouv.fr | Identité des entreprises, statut administratif, activité, catégorie juridique |
| Données financières | data.gouv.fr | Indicateurs financiers annuels et signaux comptables |
| INPI / RNE | INPI | Comptes annuels et formalités lorsque les identifiants sont disponibles |
| BODACC | DILA | Événements légaux, radiations et procédures collectives |

Les identifiants INPI ne sont pas stockés dans le notebook. L'utilisateur doit
les renseigner manuellement dans une cellule dédiée, sans les committer dans le
dépôt Git.

## Traitement BODACC Historique

Une amélioration importante concerne le flux BODACC historique. Le dossier
officiel de la DILA ne présente pas une structure unique :

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

Les années `2017` à `2021` peuvent être exposées sous forme de dossiers
contenant des archives par famille. D'autres années sont exposées sous forme de
bundles annuels. Le pipeline final prend en charge ces deux formes.

Le cas des archives imbriquées est également traité. Par exemple :

```text
BODACC_2016.tar
  BILAN_BXC20160001.taz
    BILAN_BXC20160001.xml

2025.tar.gz
  2025/
    BILAN_BXC20250001.taz
      BILAN_BXC20250001.xml
```

L'exporteur BODACC ouvre maintenant les archives annuelles, détecte les `.taz`
internes, puis lit les fichiers XML qu'ils contiennent. Le champ
`archive_member_name` conserve le chemin imbriqué, ce qui maintient la
traçabilité entre la ligne Parquet et l'archive d'origine.

## Commande Finale

La cellule principale du notebook final exécute le pipeline complet :

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

Cette commande lance :

1. le téléchargement ou la réutilisation des sources ;
2. l'export des données brutes vers le data lake ;
3. la construction des tables propres ;
4. la génération des features et labels ;
5. l'entraînement du modèle baseline ;
6. la génération du rapport d'audit.

## Structure Du Data Lake

Le data lake est organisé en couches :

| Couche | Rôle |
|---|---|
| `source-archives` | Conservation des fichiers sources originaux |
| `data-lake/raw` | Données converties en Parquet avec transformation minimale |
| `data-lake/clean` | Tables normalisées avec schéma stable |
| `data-lake/features` | Tables prêtes pour le machine learning |
| `ml-artifacts` | Modèle entraîné et métadonnées |
| `reports` | Audits et journaux de validation |

Cette séparation facilite la reproductibilité : une table finale peut être
reliée aux fichiers sources qui ont permis de la produire.

## Dictionnaire Des Données ML

Cette section décrit les tables utilisées pour le machine learning, les champs
générés, leur provenance et leur rôle. Elle permet à une personne qui reprend
le projet de comprendre rapidement comment passer des sources brutes aux
features et aux labels.

### Tables Produites

| Table | Chemin | Granularité | Rôle |
|---|---|---|---|
| `company_year_features` | `data-lake/features/company_year_features` | Une ligne par `(siren, prediction_year)` | Table principale d'entraînement |
| `risk_labels` | `data-lake/features/risk_labels` | Une ligne par `(siren, prediction_year)` | Labels futurs à horizon 12 mois |
| `company_features` | `data-lake/features/company_features` | Une ligne par `siren` | Snapshot le plus récent pour scoring ou publication |

La table `company_year_features` est temporelle. Une même entreprise peut donc
apparaître plusieurs fois, une fois par année de prédiction. Cette structure
permet d'apprendre à partir de l'historique sans mélanger le passé et le futur.

### Sources Et Tables Propres

| Source | Table Propre | Champs Sources Utilisés | Usage ML |
|---|---|---|---|
| INSEE Sirene | `clean/company_identity` | `siren`, nom, activité, catégorie juridique, effectif, statut, dates de création et fermeture | Identité, âge, statut administratif, labels de fermeture |
| BODACC | `clean/legal_events` | `event_date`, flags de risque, radiation, liquidation, redressement, sauvegarde | Historique légal, procédures collectives, radiations, labels futurs |
| INPI formalités | `clean/formalities_events` | `event_date`, `event_type`, texte de formalité | Activité déclarative, cessation, radiation, fermeture |
| INPI comptes annuels | `clean/annual_accounts` | `filing_date`, `closing_date` | Historique de dépôts, récence des comptes, anomalies de dépôt |
| Données financières | `clean/financials` | chiffre d'affaires, résultat net, capitaux propres, dettes, actifs, ratios | Santé financière, tendances, disponibilité des comptes |

### Clés Temporelles

| Champ | Table | Description |
|---|---|---|
| `siren` | Features et labels | Identifiant entreprise à 9 chiffres |
| `prediction_year` | Features et labels | Année d'observation |
| `prediction_date` | Features et labels | Date de coupure, fixée au 31 décembre de `prediction_year` |

Pour une ligne `prediction_year = 2023`, les features doivent utiliser les
données disponibles jusqu'au `2023-12-31`. Les labels utilisent les événements
qui arrivent après cette date, dans la fenêtre future.

### Features D'Identité INSEE

| Feature | Source | Description | Rôle |
|---|---|---|---|
| `company_name` | INSEE | Nom de l'entreprise | Affichage, audit, explication |
| `activity_code` | INSEE | Code d'activité principale | Secteur économique |
| `legal_category_code` | INSEE | Catégorie juridique | Forme juridique |
| `employee_size_bracket` | INSEE | Tranche d'effectif | Taille de l'entreprise |
| `administrative_status_at_cutoff` | INSEE | Statut administratif à la date de prédiction | Signal d'activité ou d'inactivité |
| `company_age_years` | INSEE | Âge de l'entreprise à la date de prédiction | Maturité et ancienneté |

Ces champs décrivent le profil stable de l'entreprise. Ils servent aussi à
éviter qu'un modèle ne compare directement des entreprises trop différentes
sans tenir compte de leur secteur, taille ou âge.

### Features BODACC

| Feature | Source | Fenêtre | Description |
|---|---|---|---|
| `legal_events_count_all` | BODACC | Jusqu'à `prediction_date` | Nombre total d'événements légaux connus |
| `legal_events_count_12m` | BODACC | 12 mois avant `prediction_date` | Intensité récente de l'activité légale |
| `legal_risk_events_count_all` | BODACC | Jusqu'à `prediction_date` | Nombre d'événements marqués comme risqués |
| `legal_risk_events_count_12m` | BODACC | 12 mois avant `prediction_date` | Risque légal récent |
| `legal_distress_events_count_all` | BODACC | Jusqu'à `prediction_date` | Historique de liquidation, redressement, sauvegarde ou procédure collective |
| `radiation_events_count_all` | BODACC | Jusqu'à `prediction_date` | Historique de radiations |
| `days_since_last_legal_event` | BODACC | Jusqu'à `prediction_date` | Récence du dernier événement légal |

Les événements BODACC sont utilisés à la fois comme historique et comme source
de labels. La séparation temporelle est donc essentielle : avant la date de
prédiction, ils deviennent des features ; après la date de prédiction, ils
peuvent devenir des labels.

### Features INPI Formalités

| Feature | Source | Fenêtre | Description |
|---|---|---|---|
| `formalities_count_all` | INPI formalités | Jusqu'à `prediction_date` | Nombre total de formalités connues |
| `formalities_count_12m` | INPI formalités | 12 mois avant `prediction_date` | Activité déclarative récente |
| `cessation_formalities_count_all` | INPI formalités | Jusqu'à `prediction_date` | Formalités dont le texte évoque cessation, radiation ou fermeture |

Ces features ajoutent une vision déclarative issue du registre. Elles
complètent le BODACC, qui est plus centré sur les annonces légales publiées.

### Features De Dépôt Des Comptes

| Feature | Source | Fenêtre | Description |
|---|---|---|---|
| `annual_accounts_count_all` | INPI comptes annuels | Jusqu'à `prediction_date` | Nombre total de dépôts de comptes |
| `annual_accounts_count_24m` | INPI comptes annuels | 24 mois avant `prediction_date` | Régularité récente des dépôts |
| `days_since_last_account_filing` | INPI comptes annuels | Jusqu'à `prediction_date` | Récence du dernier dépôt |
| `latest_account_closing_year` | INPI comptes annuels | Jusqu'à `prediction_date` | Dernière année de clôture connue |

Ces champs ne disent pas directement qu'une entreprise est saine ou risquée.
Ils indiquent plutôt la régularité de publication et la fraîcheur de
l'information comptable.

### Features Financières

| Feature | Source | Description | Interprétation |
|---|---|---|---|
| `latest_revenue` | Données financières | Dernier chiffre d'affaires connu | Taille économique récente |
| `latest_net_result` | Données financières | Dernier résultat net connu | Profitabilité récente |
| `latest_equity` | Données financières | Derniers capitaux propres connus | Solidité financière |
| `latest_debt` | Données financières | Dernière dette connue | Endettement |
| `latest_total_assets` | Données financières | Dernier total d'actifs connu | Taille bilancielle |
| `latest_net_margin` | Données financières | Marge nette récente | Rentabilité relative |
| `latest_debt_to_assets` | Données financières | Dette rapportée aux actifs | Levier financier |
| `latest_equity_ratio` | Données financières | Capitaux propres rapportés aux actifs | Structure financière |
| `latest_debt_to_equity` | Données financières | Dette rapportée aux capitaux propres | Levier sur fonds propres |
| `has_negative_result_history` | Données financières | Résultat négatif observé historiquement | Signal de fragilité passée |
| `has_negative_equity_history` | Données financières | Capitaux propres négatifs observés historiquement | Signal de fragilité structurelle |
| `revenue_growth_1y` | Données financières | Évolution du chiffre d'affaires sur un an | Tendance d'activité |
| `net_result_change_1y` | Données financières | Variation du résultat net sur un an | Tendance de profitabilité |

Les features financières sont enrichies par des indicateurs de disponibilité
afin de ne pas confondre absence de données et mauvaise performance.

### Features De Disponibilité Et Fraîcheur Financière

| Feature | Source | Description |
|---|---|---|
| `has_financial_data` | Données financières | Indique si au moins une année financière existe |
| `financial_years_available` | Données financières | Nombre d'années financières disponibles |
| `latest_financial_year` | Données financières | Dernière année financière connue |
| `years_since_last_financial_statement` | Données financières | Nombre d'années depuis la dernière donnée financière |
| `has_confidential_financials` | Données financières | Présence d'un marqueur de confidentialité |

Ces champs répondent à une faiblesse méthodologique importante : une donnée
manquante peut être normale. Le modèle doit savoir qu'une information est
absente, sans supposer automatiquement qu'il s'agit d'un signal de risque.

### Labels De Risque

| Label | Sources | Fenêtre Future | Définition |
|---|---|---|---|
| `continuity_risk_12m_label` | INSEE, BODACC, INPI formalités | 12 mois après `prediction_date` | Label principal : fermeture administrative, procédure collective, radiation ou signal INPI de cessation/radiation |
| `legal_distress_risk_12m_label` | BODACC | 12 mois après `prediction_date` | Liquidation, redressement, sauvegarde ou procédure collective future |
| `radiation_risk_12m_label` | BODACC, INPI formalités | 12 mois après `prediction_date` | Radiation BODACC ou formalité INPI de cessation/radiation/fermeture |
| `financial_weakness_risk_12m_label` | Données financières | Année financière suivante | Résultat net négatif ou capitaux propres négatifs l'année suivante |
| `filing_anomaly_risk_12m_label` | INPI comptes annuels | 18 mois après `prediction_date` | Entreprise ayant un historique récent de dépôt mais aucun dépôt futur attendu |
| `first_future_legal_event_date` | BODACC | 12 mois après `prediction_date` | Première date d'événement légal futur, conservée pour audit et non comme feature d'entraînement |

Le label principal est volontairement large. Pour éviter l'ambiguïté, les
labels secondaires permettent de distinguer la nature du risque : juridique,
radiation, financier ou anomalie de dépôt.

### Colonnes Exclues De L'Entraînement

Certaines colonnes sont utiles pour l'audit ou la jointure, mais ne doivent pas
être utilisées directement comme features de modèle.

| Colonne | Raison D'Exclusion |
|---|---|
| `siren` | Identifiant technique, risque de mémorisation |
| `prediction_date` | Clé temporelle, pas un signal métier direct |
| `first_future_legal_event_date` | Information future liée au label |
| `continuity_risk_12m_label` | Target principal |
| `legal_distress_risk_12m_label` | Label secondaire |
| `radiation_risk_12m_label` | Label secondaire |
| `financial_weakness_risk_12m_label` | Label secondaire |
| `filing_anomaly_risk_12m_label` | Label secondaire |

Cette exclusion protège le modèle contre la fuite de données et contre
l'utilisation de colonnes qui contiennent directement la réponse.

## Résultat De L'Audit Baseline

Un audit exécuté le `2026-05-09` sur un échantillon plafonné à `100 000`
entreprises a confirmé que le pipeline fonctionnait de bout en bout.

| Élément | Valeur |
|---|---:|
| Jeux disponibles | Jeux requis présents dans le run final |
| Lignes profilées | 311 473 153 |
| `company_year_features` | 900 000 lignes |
| `risk_labels` | 900 000 lignes |
| `company_features` | 100 000 lignes |
| Décision d'audit | Prêt pour un entraînement baseline |

Les principales tables propres étaient disponibles :

| Table | Lignes |
|---|---:|
| `clean_company_identity` | 29 572 772 |
| `clean_legal_events` | 4 071 295 |
| `clean_annual_accounts` | 6 287 057 |
| `clean_financials` | 6 368 964 |

Le run final inclut également les formalités INPI afin de compléter les signaux
de cessation, de radiation et d'activité déclarative. Les chiffres exacts du
nouvel audit doivent être conservés dans `reports/data_lake_audit.md` après
l'exécution complète.

## Entraînement Du Modèle Baseline

Un premier modèle baseline a été entraîné sur `900 000` lignes
company-year. Il s'agit d'un modèle de régression logistique avec pondération
des classes, destiné à vérifier la chaîne de bout en bout et non à constituer le
résultat final définitif.

| Métrique | Valeur |
|---|---:|
| Accuracy | 0,99397 |
| ROC AUC | 0,97602 |
| Average precision | 0,06182 |

L'accuracy est élevée, mais elle doit être interprétée avec prudence car le
label positif est rare. Dans ce contexte, l'average precision est plus
informative que l'accuracy.

La distribution des labels montre une forte rareté du signal de continuité :

| Année | Positifs `continuity_risk_12m_label` | Taux |
|---|---:|---:|
| 2017 | 119 | 0,00119 |
| 2018 | 204 | 0,00204 |
| 2019 | 72 | 0,00072 |
| 2020 | 56 | 0,00056 |
| 2021-2025 | 0 | 0,00000 |

Ce résultat montre que le modèle baseline est techniquement entraînable, mais
que les données historiques de labels doivent encore être renforcées pour une
évaluation finale robuste.

## Interprétation Académique

Le pipeline final répond à plusieurs exigences méthodologiques :

| Exigence | Réponse Du Pipeline |
|---|---|
| Reproductibilité | Les commandes Colab sont centralisées dans un notebook final |
| Traçabilité | Les archives sources sont conservées dans `source-archives` |
| Séparation des couches | Raw, clean, features, artefacts et rapports sont séparés |
| Validation | Un audit automatisé vérifie disponibilité, doublons, SIREN et labels |
| Passage à l'échelle | Le travail local `/content/pfe_work` réduit la dépendance aux écritures Drive |
| Extensibilité | Les sources INPI, BODACC, INSEE et financières sont intégrées dans le même workflow |

La principale contribution récente est donc moins le modèle lui-même que la
stabilisation du pipeline complet permettant de produire un jeu d'entraînement
défendable.

## Réponse Aux Faiblesses Identifiées

Le rapport de faiblesses du projet avait identifié plusieurs points qui
pouvaient être attaqués lors d'une soutenance : projet ambitieux mais pas
encore totalement prouvé, cible trop large, risque de fuite temporelle,
couverture incomplète des sources, métriques ML insuffisantes et stratégie de
serving à clarifier. La version finale du pipeline répond à une partie de ces
faiblesses et permet de mieux formuler celles qui restent ouvertes.

| Faiblesse Identifiée | Réponse Apportée Dans La Version Finale | Statut |
|---|---|---|
| Le projet semblait surtout conceptuel | Un notebook final exécute la chaîne complète : sources, raw, clean, features, modèle et audit | Amélioré |
| Les résultats ML n'étaient pas montrés | Un modèle baseline a été entraîné et ses métriques sont documentées | Amélioré, mais non final |
| La couverture BODACC historique était fragile | Le pipeline gère les dossiers annuels, les bundles `.tar` / `.tar.gz` et les archives imbriquées | Amélioré |
| Les formalités INPI étaient absentes du run précédent | Le run final active INPI et inclut `comptes_annuels` et `formalites` | Amélioré |
| Google Drive ralentissait les gros traitements | Ajout d'un répertoire local `/content/pfe_work` puis synchronisation vers Drive | Amélioré |
| La cible `continuity_risk` pouvait paraître vague | Le rapport distingue la cible globale et les labels secondaires | Clarifié |
| L'accuracy pouvait être trompeuse | Le rapport insiste sur l'average precision, PR-AUC, rappel et top-k | Clarifié |
| La fuite temporelle était expliquée mais pas assez prouvée | Le pipeline utilise des dates de coupure par année et sépare features historiques et labels futurs | À renforcer par tests automatiques dédiés |
| La fraîcheur des sources n'était pas assez visible | Les manifests, audits et rapports Drive conservent les traces d'exécution | À enrichir avec champs de fraîcheur par source |
| Le serving MongoDB restait abstrait | Les artefacts ML et les features latest-company sont produits | À compléter par documents de serving stabilisés |

### Clarification De La Cible De Prédiction

La question possible d'un jury est la suivante :

```text
Prédit-on une faillite, une radiation, une inactivité ou un risque juridique ?
```

La réponse retenue est que la cible principale n'est pas la faillite au sens
strict. Elle représente un risque de continuité à horizon 12 mois. Elle agrège
plusieurs familles d'événements qui signalent qu'une entreprise peut cesser ou
fragiliser son activité.

La cible principale est :

```text
continuity_risk_12m_label
```

Elle doit être lue avec les labels secondaires :

| Label | Interprétation |
|---|---|
| `legal_distress_risk_12m_label` | Procédure collective, liquidation, redressement ou sauvegarde |
| `radiation_risk_12m_label` | Radiation ou signal de cessation |
| `financial_weakness_risk_12m_label` | Faiblesse financière observée dans la fenêtre future |
| `filing_anomaly_risk_12m_label` | Anomalie ou rupture du comportement de dépôt |

Cette séparation rend le modèle plus défendable : le score global donne une
vision synthétique, tandis que les labels secondaires permettent d'expliquer la
nature du risque.

### Données Financières Manquantes

Le rapport de faiblesses soulignait que l'absence de données financières peut
être normale. Une petite entreprise peut ne pas publier certains comptes, une
donnée peut être confidentielle, ou un dépôt peut être retardé.

Le pipeline ne doit donc pas interpréter automatiquement une valeur financière
manquante comme un signal négatif. La stratégie retenue consiste à utiliser :

| Type De Variable | Rôle |
|---|---|
| `has_financial_data` | Indique si une donnée financière existe |
| `has_confidential_financials` | Distingue les comptes confidentiels |
| `financial_years_available` | Mesure la profondeur historique disponible |
| `latest_financial_year` | Indique l'année financière la plus récente |
| `years_since_last_financial_statement` | Mesure la récence de l'information |
| `annual_accounts_count_24m` | Mesure l'activité déclarative récente |

Cette approche évite de confondre absence de publication et mauvaise santé
financière. Elle transforme la disponibilité des données en information
contrôlée plutôt qu'en hypothèse implicite.

### Contrôle De Fuite Temporelle

La validité du modèle dépend de la séparation stricte entre passé et futur.
Pour une année de prédiction donnée, la logique est :

```text
prediction_year = 2023
prediction_date = 2023-12-31

features:
événements avec event_date <= 2023-12-31

labels:
événements avec 2024-01-01 <= event_date <= 2024-12-31
```

Les événements BODACC, INPI, financiers et administratifs ne doivent donc pas
être utilisés de la même manière selon leur date. Un événement avant la date de
prédiction est une information historique. Un événement après cette date peut
servir au label, mais ne doit pas être une feature.

Exemple :

| Situation | Usage Correct |
|---|---|
| PCL BODACC avant la date de prédiction | Feature historique |
| PCL BODACC après la date de prédiction | Label futur |
| Radiation après la date de prédiction | Label futur |
| Formalité INPI future | Label ou signal futur, pas feature |

Le pipeline applique cette logique dans la génération des company-year rows. La
prochaine amélioration défensive consiste à ajouter des tests automatiques qui
vérifient explicitement :

```text
max(feature_event_date) <= prediction_date
min(label_event_date) > prediction_date
```

### Protocole D'Évaluation Du Modèle

Le premier modèle baseline est utile car il prouve que la chaîne ML fonctionne.
Cependant, les événements de continuité sont rares. L'accuracy ne suffit donc
pas.

Le protocole d'évaluation final doit inclure :

| Élément | Raison |
|---|---|
| ROC AUC | Mesure générale de classement |
| Average precision / PR-AUC | Plus adaptée aux classes rares |
| Recall | Capacité à détecter les entreprises réellement à risque |
| Precision | Fiabilité des alertes |
| Top-k risk capture | Pertinence opérationnelle des entreprises les plus risquées |
| Calibration | Vérifie si une probabilité de 80 % signifie réellement un risque proche de 80 % |
| Matrice de confusion | Rend visible le coût des faux positifs et faux négatifs |

Le choix du seuil de décision ne doit pas être arbitraire. Il doit dépendre du
coût métier :

| Erreur | Conséquence |
|---|---|
| Faux négatif | Une entreprise risquée n'est pas détectée |
| Faux positif | Une entreprise saine est signalée à tort |

Pour un outil d'intelligence entreprise, un classement top-k peut être plus
utile qu'une classification binaire stricte. Par exemple, on peut analyser les
5 % ou 10 % d'entreprises les plus risquées et mesurer combien d'événements
réels sont capturés dans ce groupe.

### Fraîcheur Et Traçabilité Des Sources

Les sources ne sont pas mises à jour au même rythme. L'INSEE, l'INPI, le BODACC
et les données financières ont des calendriers différents. Le pipeline conserve
donc les archives sources, les manifests et les rapports d'audit afin de
documenter l'état exact des données au moment de l'exécution.

Pour renforcer encore le projet, les futurs documents de serving devraient
exposer :

| Champ | Utilité |
|---|---|
| `last_insee_update` | Fraîcheur de l'identité administrative |
| `last_inpi_update` | Fraîcheur des formalités et comptes |
| `last_bodacc_update` | Fraîcheur des événements légaux |
| `last_financial_update` | Fraîcheur des indicateurs financiers |
| `pipeline_run_id` | Traçabilité de la génération |
| `model_version` | Version du modèle utilisé |

Cela permettrait à l'utilisateur final de comprendre si un profil est très
récent ou s'il dépend de sources plus anciennes.

### Contribution Académique Reformulée

La contribution du projet ne doit pas être présentée comme un simple site de
consultation d'entreprises. Elle doit être formulée comme :

```text
une architecture temporelle, reproductible et multi-source permettant de
transformer des données publiques françaises hétérogènes en features
company-year, labels futurs à horizon 12 mois et score de risque de continuité.
```

Cette formulation répond mieux à la critique selon laquelle le projet serait
seulement une agrégation de données. La valeur ajoutée vient de la temporalité,
de la traçabilité, de l'intégration multi-source et de la préparation à la
prédiction.

## Limites Actuelles

| Limite | Impact | Action Prévue |
|---|---|---|
| Labels positifs rares | L'accuracy peut être trompeuse | Utiliser average precision, PR-AUC, recall et top-k |
| Positifs concentrés sur 2017-2020 dans le run baseline | Validation temporelle fragile | Compléter les archives BODACC historiques et reconstruire les labels |
| Modèle baseline simple | Performance limitée | Comparer avec modèles calibrés plus robustes |
| Exécution Colab dépendante du runtime | Risque d'interruption | Synchronisation Drive et reprise par `git pull` / `--work-dir` |

## Décision

Le pipeline final peut être utilisé pour produire le dataset complet et lancer
un entraînement baseline. Le modèle obtenu doit toutefois être présenté comme un
modèle de validation technique tant que la couverture BODACC historique complète
et la distribution finale des labels ne sont pas confirmées dans le dernier
audit.

La décision académique est donc la suivante :

```text
Le pipeline est prêt pour l'exécution finale et la génération d'évidence.
Le modèle baseline est acceptable pour démontrer la faisabilité.
Les métriques finales doivent être recalculées après complétion des sources.
```

## Résumé

La version finale du pipeline Colab transforme le projet en chaîne de
préparation reproductible : montage Drive, vérification du dossier partagé,
mise à jour du dépôt, installation des dépendances, téléchargement des sources,
export Parquet, construction des tables propres, génération des features,
entraînement baseline et audit. Les améliorations récentes corrigent les deux
principaux risques opérationnels : la lenteur de Google Drive pendant les gros
traitements et la structure complexe des archives BODACC historiques.

Ce rapport peut être utilisé comme section académique pour expliquer la
méthodologie de préparation des données, la stratégie de validation et la
position du modèle baseline dans le cycle de développement.
