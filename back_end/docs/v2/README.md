# PFE ML — V2 — Refonte rétrospective

Ce dossier rassemble la documentation, les notebooks Colab et les scripts Python d'une **deuxième itération** du projet de prédiction de risque de continuité PME. La V2 corrige sept décisions rétrospectivement sous-optimales de la V1 sans tout reconstruire : les couches `raw/` et `clean/` du data lake sont réutilisées telles quelles, à l'exception d'une nouvelle table `clean/company_identity_periodic` reconstruite depuis l'historique périodique SIRENE.

## Objectif

Construire un pipeline V2 qui, sur la même problématique (prédiction du risque de cessation d'activité à horizon 12 mois sur PME françaises), produit un modèle **académiquement plus rigoureux** et **opérationnellement plus simple** que la V1. Les gains attendus sont :

- **+5 à +10 pp d'AP** grâce à la réintégration légitime (période-aware) des features d'identité INSEE.
- **Suppression du calibrateur séparé** grâce à l'abandon de `class_weight='balanced'`, ce qui simplifie le `MLRegistry` opérationnel.
- **Quatre modèles spécialisés par étiquette** (procédure collective, radiation, cessation, formalité) au lieu d'un modèle composite, pour un produit utilisateur plus interprétable.
- **Intervalles de confiance bootstrap** sur toutes les métriques reportées.
- **Validation externe** géographique et sectorielle, en plus de la validation temporelle.

## Périmètre — ce qui change, ce qui reste

**Réutilisé tel quel** (pas de nouveau téléchargement, pas de re-traitement) :
- `data-lake/raw/inpi/*`
- `data-lake/raw/bodacc/*`
- `data-lake/raw/financials/*`
- `data-lake/raw/insee/bulk/stock_unite_legale/*`
- `data-lake/raw/insee/bulk/stock_etablissement/*`
- `data-lake/clean/legal_events/`
- `data-lake/clean/annual_accounts/`
- `data-lake/clean/formalities_events/`
- `data-lake/clean/financials/`

**Nouvelle table dérivée des données existantes** :
- `data-lake/clean/company_identity_periodic/` — reconstruit depuis `data-lake/raw/insee/bulk/stock_unite_legale_historique/` avec granularité `(siren, period_start, period_end)`.

**Nouvelles tables features et labels V2** :
- `data-lake/features/company_year_features_v2/` — features V2 incluant l'identité période-aware.
- Les labels V2 sont les **mêmes** que V1 (table `risk_labels`), inchangés.

**Code isolé sous `app/tools/v2/`** (V1 reste opérationnel en parallèle).

## Documents V2

| Fichier | Rôle |
|---|---|
| `v2_roadmap.md` | **Plan complet en 10 phases** avec délivrables, critères de validation, dépendances. C'est le document à lire en premier. |
| `v2_design_decisions.md` | Justification académique de chaque décision (pourquoi V2 fait X au lieu de Y de V1). À citer dans le mémoire pour défendre les choix. |
| `v2_phase_log.md` | **Journal vivant** des résultats de chaque phase au fur et à mesure de leur exécution. À mettre à jour après chaque phase. |
| `v2_rapport_final_fr.md` | Rapport académique V2 (à rédiger après l'achèvement des phases 1 à 9). |

## Conventions de séparation V1 ↔ V2

**Principe directeur :** zéro sortie V2 ne doit jamais écrire dans un répertoire V1. Toutes les sorties V2 (modèles, figures, JSON d'audit, CSV de métriques, manifests) vivent sous un préfixe `v2/` ou un suffixe explicite. V1 reste opérationnel et inchangé pendant tout le développement V2.

### Tableau des emplacements

| Catégorie | V1 (inchangé) | V2 (nouveau) |
|---|---|---|
| **Documentation** | `docs/*.md` à la racine | `docs/v2/*.md` |
| **Scripts Python** | `app/tools/*.py` | `app/tools/v2/*.py` |
| **MLRegistry production** | `app/ml/loader.py` + `app/ml/artifacts/` | `app/ml/v2/loader_v2.py` + `app/ml/v2/artifacts/` |
| **Notebooks Colab** | `collabs/*.ipynb` | `collabs/v2/*.ipynb` |
| **Artefacts Drive** | `pfe_data/ml-artifacts/runs/<run>/` | `pfe_data/ml-artifacts/v2/runs/<run>/` |
| **Tableaux & figures phases** | `pfe_data/ml-artifacts/<phase>/` | `pfe_data/ml-artifacts/v2/<phase>/` |
| **Tuned params** | `ml-artifacts/tuned_params_*.json` | `ml-artifacts/v2/tuned_params_*.json` |
| **Index runs** | `ml-artifacts/model_run_comparison.csv` | `ml-artifacts/v2/model_run_comparison.csv` |
| **Synchronisation Git** | `docs/ouputs/ml-artifacts/` | `docs/ouputs/ml-artifacts/v2/` |

### Ce qui est partagé entre V1 et V2

| Couche | Justification |
|---|---|
| `data-lake/raw/**` | Données brutes ingérées (INPI, BODACC, INSEE, financier) — aucune raison de dupliquer. |
| `data-lake/clean/legal_events/` | Événements BODACC normalisés — identiques pour V1 et V2. |
| `data-lake/clean/annual_accounts/` | Comptes annuels INPI — identiques. |
| `data-lake/clean/formalities_events/` | Formalités INPI — identiques. |
| `data-lake/clean/financials/` | Financier data.gouv.fr — identique. |
| `data-lake/features/risk_labels/` | Étiquettes — identiques (les 5 mêmes labels). |
| Branche Git `data-extraction` | Un seul tronc Git pour les commits V1 (correctifs) et V2 (nouveau code). Pas de chevauchement de fichiers. |

### Ce qui est créé par V2 (sans toucher V1)

| Chemin nouveau | Phase qui le produit | Type |
|---|---|---|
| `data-lake/clean/company_identity_periodic/` | Phase 1 | Couche data lake (nouvelle table dérivée du raw INSEE) |
| `data-lake/features/company_year_features_v2/` | Phase 2 | Couche features (sibling du V1) |
| `ml-artifacts/v2/runs/*` | Phases 4-8 | Per-run artifacts |
| `ml-artifacts/v2/tuning_phase_b/` | Phase 4-5 | Phase-level CSVs et plots (s'il y a un tuning V2) |
| `ml-artifacts/v2/bootstrap_ci/` | Phase 6 | Tableaux d'IC et plots |
| `ml-artifacts/v2/external_validation/` | Phase 7 | Tableaux holdout géo et sectoriel |
| `ml-artifacts/v2/calibration/` | Phase 8 | Diagrammes de fiabilité par modèle |
| `ml-artifacts/v2/per_label_thresholds.json` | Phase 5 | Seuils opérationnels par label |
| `app/ml/v2/artifacts/*.joblib` | Phase 9 | Artefacts servis par l'API V2 |

## Statut courant

| Phase | Statut | Notes |
|---|---|---|
| 1. Identité INSEE période-aware | À démarrer | — |
| 2. Build features V2 | À démarrer | Dépend de la Phase 1 |
| 3. Baseline iteratif (100K) | À démarrer | Dépend de la Phase 2 |
| 4. Modèles par étiquette | À démarrer | — |
| 5. Tuning des seuils par étiquette | À démarrer | — |
| 6. Bootstrap CIs | À démarrer | — |
| 7. Validation externe | À démarrer | — |
| 8. Calibration via CalibratedClassifierCV | À démarrer | — |
| 9. Intégration backend V2 | À démarrer | — |
| 10. Rapport V2 + comparaison V1/V2 | À démarrer | — |

Voir `v2_phase_log.md` pour le détail des résultats au fur et à mesure.
