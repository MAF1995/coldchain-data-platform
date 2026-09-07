# Plateforme data - Chaîne du froid pharmaceutique

Ce projet sert de support technique aux blocs de certification : collecte, analyse, conduite du projet et industrialisation d'une plateforme data.

Sujet retenu :

> Pipeline data pour la supervision de la chaîne du froid pharmaceutique.

## Livrables de certification

| Bloc | Source | Rendu PDF |
| --- | --- | --- |
| I | `docs/bloc1_dossier_v1.md` | `dist/bloc1_FALIGANT.pdf` |
| II | `docs/bloc2_dossier_v1.md` | `dist/bloc2_FALIGANT_corrige.pdf` |
| III | `docs/bloc3_dossier_v1.md` | `dist/bloc3_FALIGANT.pdf` |
| IV | `docs/bloc4_support_v1.md` | `dist/bloc4_support_FALIGANT.pdf` |

Le bloc III est un dossier écrit de 19 pages, couverture et annexe comprises. Le bloc IV est un support de présentation de 31 diapositives en format paysage.

## Lancement local avec `.venv`

Depuis le dossier projet :

```powershell
cd C:\Users\MAF\Desktop\certification_data_eng\pharma_coldchain_project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python .\src\replay_sample_events.py
```

Le script `replay_sample_events.py` rejoue les messages capteurs d'exemple et affiche le statut température (`OK`, `TOO_HOT`, `TOO_COLD`). C'est suffisant pour produire une première capture terminal.

Les composants lourds sont exécutés avec Docker. Le venv reste consacré aux scripts, aux tests et aux analyses légères.

## Stack industrialisée

| Profil | Services | Objectif |
| --- | --- | --- |
| `streaming` | Mosquitto, Kafka, bridge, consommateur | Ingestion temps réel découplée et idempotente |
| `orchestration` | Airflow et dbt | Orchestration, transformations et barrière qualité |
| `distributed` | Spark master et deux workers | Agrégation distribuée et sortie Parquet |
| `observability` | Prometheus et Grafana | Métriques, alertes et supervision |

Flux temps réel et supervision :

```powershell
docker compose -f compose.yml -f compose.infrastructure.yml `
  --profile streaming --profile observability up -d --build
```

Interfaces :

- Grafana : `http://localhost:3002/d/pharma-coldchain-pipeline/chaine-du-froid-supervision-du-pipeline`
- Prometheus : `http://localhost:9090`
- Airflow : `http://localhost:8088`
- Spark : `http://localhost:8090`

Les procédures détaillées se trouvent dans `docs/bloc4_runbook_technique.md`. Le plan de validation est conservé dans `docs/bloc4_cahier_recette.md`.

## Socle analytique du bloc II

Le bloc II utilise un environnement séparé pour l'analyse, les tests
statistiques et les modèles dbt :

```powershell
cd C:\Users\MAF\Desktop\certification_data_eng\pharma_coldchain_project
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements-analytics.txt
.\scripts\run_bloc2_foundation.ps1
```

Cette commande :

- démarre PostgreSQL sur le port local `55432` ;
- charge les événements SQLite de façon idempotente ;
- construit les modèles `clean` et `analytics` avec dbt ;
- exécute les tests dbt ;
- crée et exécute le notebook `notebooks/bloc2_qualite_donnees.ipynb`.

Le dictionnaire des indicateurs est conservé dans
`analytics/kpi_definitions.yml`. Le pipeline analytique est représenté dans
`assets/diagrams/07_bloc2_pipeline_analytique.mmd`.

Pour ouvrir le notebook dans JupyterLab :

```powershell
.\.venv\Scripts\python.exe -m jupyter lab
```

## Écoute MQTT sur brokers réels

L'écoute réelle est volontairement limitée à des topics de projet autorisés :

- `pharma/production/site-042/#`
- `pharma/coldchain/site-042/#`

Elle ne fait pas de collecte large sur `#` et ne récupère pas de données industrielles tierces non autorisées.

Lancer 2h d'écoute sur deux brokers publics réels :

```powershell
.\scripts\start_real_mqtt_capture.ps1 -DurationSeconds 7200
```

Consulter l'état de la base brute :

```powershell
python .\src\mqtt_capture_status.py
```

Arrêter l'écoute :

```powershell
.\scripts\stop_real_mqtt_capture.ps1
```

La base brute est créée ici :

- `data/raw/mqtt_raw.db`

Les logs sont ici :

- `logs/mqtt_listener_mosquitto.log`
- `logs/mqtt_listener_hivemq.log`

## Charte visuelle

Palette médicale/pharma à 5 couleurs :

| Rôle | Couleur | Hex |
| --- | --- | --- |
| Vert aquamarin principal | Aqua | `#43C6B6` |
| Vert menthe | Mint | `#9EE7D2` |
| Fond clinique très clair | Seafoam | `#E8F8F4` |
| Bleu ciel | Sky | `#8FD3F4` |
| Bleu médical accent | Sky deep | `#2F9FD0` |

Typographie visée : Garamond light, avec fallback `EB Garamond`, `Cormorant Garamond`, Georgia.

Style PDF :

- `assets/style/pharma_pdf.css`

## Où placer les captures d'écran

Toutes les captures vont dans :

- `assets/screenshots/`

Convention de nommage recommandée :

| Fichier | À capturer | Où l'insérer dans le dossier |
| --- | --- | --- |
| `bloc4/01_grafana_pipeline_monitoring.png` | Continuité MQTT, Kafka et PostgreSQL | Bloc IV, méthode temps réel |
| `bloc4/02_prometheus_targets.png` | État des cibles de supervision | Bloc IV, supervision |
| `bloc4/03_prometheus_alerts.png` | Règles d'alerte chargées | Bloc IV, supervision |
| `bloc4/04_spark_cluster_execution.png` | Workers et application Spark terminée | Bloc IV, calcul distribué |
| `bloc4/05_airflow_dag_execution.png` | DAG et tâches réussies | Bloc IV, orchestration |

Ces cinq preuves sont capturées nativement en `1920 × 1080`.

Si on n'a pas encore d'outil lancé, on peut mettre des captures de :

- terminal avec script d'ingestion ;
- résultat SQL ;
- schéma Mermaid exporté ;
- maquette de dashboard.

## Dossiers utiles

| Dossier | Rôle |
| --- | --- |
| `docs/` | Dossier écrit principal |
| `assets/diagrams/` | Diagrammes Mermaid séparés |
| `assets/screenshots/` | Captures d'écran à intégrer |
| `assets/style/` | CSS et charte visuelle |
| `data/sample/` | Données d'exemple |
| `src/` | Scripts Python |
| `sql/` | Schéma et requêtes SQL |
| `dbt/` | Exemple de modèle dbt |
| `airflow/` | Exemple de DAG Airflow |
