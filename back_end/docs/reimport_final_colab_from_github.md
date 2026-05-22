# Reimporter Le Notebook Colab Final Depuis GitHub

Ce guide explique comment ouvrir de nouveau le notebook final depuis GitHub
dans Google Colab, avec la dernière version du projet.

## Notebook A Ouvrir

Le notebook final se trouve ici dans le dépôt :

```text
collabs/01_pipeline_donnees_execution_complete.ipynb
```

Le dépôt GitHub est :

```text
https://github.com/zribi1/pfein
```

## Methode Recommandee Depuis Colab

1. Ouvrir Google Colab :

```text
https://colab.research.google.com
```

2. Cliquer sur :

```text
File > Open notebook
```

3. Choisir l'onglet :

```text
GitHub
```

4. Coller le dépôt :

```text
https://github.com/zribi1/pfein
```

5. Si Colab demande le chemin du notebook, choisir :

```text
collabs/01_pipeline_donnees_execution_complete.ipynb
```

6. Ouvrir le notebook.

## Important Pour Garder La Derniere Version

Si le notebook est déjà ouvert dans Colab, il peut garder une ancienne copie.
Pour être sûr d'utiliser la dernière version :

1. Fermer l'ancien onglet Colab.
2. Rouvrir le notebook depuis l'onglet GitHub.
3. Vérifier que la commande finale contient bien :

```bash
--inpi-retries 6 \
--continue-on-error
```

4. Vérifier que le notebook contient aussi les sections :

```text
Pipeline Status Check
INPI Integrity Checks
ML Readiness Audits
```

Si ces sections sont présentes, c'est la version finale récente.

## Connexion Au Dossier Drive Partage

Le notebook ne contient pas les données. Les données sont dans Google Drive.
Avant d'exécuter le pipeline, vérifier que le dossier partagé est accessible à
cet emplacement :

```text
/content/drive/MyDrive/PFE ML Data/pfe_data
```

Si le dossier n'est pas visible :

1. Ouvrir Google Drive.
2. Ouvrir le dossier partagé par le propriétaire.
3. Ajouter un raccourci vers ce dossier dans `My Drive`.
4. Revenir dans Colab.
5. Rerun la cellule de montage Drive.
6. Rerun la cellule `Check Shared Drive Folder`.

Le dossier attendu doit contenir ou recevoir :

```text
data-lake
ml-artifacts
reports
source-archives
```

## Apres Import

Executer les cellules dans cet ordre :

1. `Mount Drive`
2. `Check Shared Drive Folder`
3. `Clone Or Update Repository`
4. `Configure Paths`
5. `Install Dependencies`
6. `INPI Credentials`, seulement si le run inclut INPI
7. `Final Full Data Pipeline`
8. `Pipeline Status Check`
9. `INPI Integrity Checks`
10. `ML Readiness Audits`

## Si Le Pipeline Echoue

Ne pas supprimer les fichiers Drive. Le pipeline sait reprendre les fichiers
déjà téléchargés.

Apres une erreur, lancer la cellule :

```text
Pipeline Status Check
```

Elle lit :

```text
DRIVE_ROOT/reports/pipeline_status.md
DRIVE_ROOT/reports/pipeline_status.json
```

Ces fichiers indiquent :

- les étapes réussies ;
- les étapes échouées ;
- les étapes ignorées ;
- l'erreur exacte ;
- la commande à relancer.

Pour reprendre le projet après une mise à jour Git :

```bash
%cd $BACKEND_DIR
!git pull
```

Puis relancer la cellule du pipeline ou seulement l'étape concernée.

