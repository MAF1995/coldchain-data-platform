# Runbook technique de la plateforme data pharmaceutique

## I. Objet et périmètre

Ce runbook décrit l'exploitation du pipeline de supervision de la chaîne du froid. Le périmètre couvre l'entrée MQTT, la mise en tampon Kafka, la persistance PostgreSQL, les transformations dbt, l'orchestration Airflow, le calcul distribué Spark et l'observabilité Prometheus/Grafana.

Les services sont regroupés par profils Docker afin de tenir compte des ressources disponibles sur le poste de validation. Cette séparation ne modifie pas l'architecture cible : elle permet d'exécuter chaque scénario de manière reproductible, sans charger simultanément des composants qui ne sont pas nécessaires au test en cours.

## II. Cartographie des services

| Service | Rôle | Port de validation | Contrôle principal |
| --- | --- | ---: | --- |
| Mosquitto | Broker MQTT de proximité | `1884` | Connexion et réception sur le topic autorisé |
| Kafka | Tampon durable et découplage | `29092` | Topics, partitions et retard du groupe |
| PostgreSQL | Stockage brut et analytique | `55432` | Comptages, contraintes et modèles dbt |
| Airflow | Orchestration des traitements | `8088` | État du DAG et des tâches |
| Spark | Calcul distribué | `8090` | Workers, exécuteurs et application terminée |
| Prometheus | Collecte des métriques et règles | `9090` | Targets et Rules |
| Grafana | Tableau de bord de supervision | `3002` | Dashboard Data Engineering |

## III. Procédures de démarrage

### a. Flux temps réel et observabilité

```powershell
docker compose -f compose.yml -f compose.infrastructure.yml `
  --profile streaming --profile observability up -d --build
```

Pour injecter une séquence de mesures :

```powershell
.\.venv\Scripts\python.exe .\src\publish_machine_signals.py `
  --broker localhost --port 1884 --duration-seconds 90 --interval-seconds 1 `
  --topic-prefix pharma/production/site-042
```

### b. Orchestration Airflow

```powershell
docker compose -f compose.yml -f compose.infrastructure.yml `
  --profile orchestration up -d --build airflow
```

Le DAG `pharma_cold_chain_daily` vérifie la source brute, charge le référentiel, construit les modèles, exécute les tests dbt, applique la barrière qualité et écrit une preuve JSON.

### c. Calcul distribué Spark

```powershell
.\.venv\Scripts\python.exe .\scripts\export_raw_for_spark.py
docker compose -f compose.yml -f compose.infrastructure.yml `
  --profile distributed up -d spark-master spark-worker-1 spark-worker-2
docker compose -f compose.yml -f compose.infrastructure.yml `
  --profile distributed up --force-recreate --no-deps spark-submit
```

Le résultat est stocké en Parquet dans `data/lake/curated/quality_daily_parquet`. La preuve d'exécution se trouve dans `data/lake/evidence/spark_last_run.json`.

## IV. Contrôles d'exploitation

### a. Santé générale

```powershell
docker compose -f compose.yml -f compose.infrastructure.yml `
  --profile streaming --profile observability ps
.\.venv\Scripts\python.exe .\scripts\collect_platform_evidence.py
```

Le statut est acceptable lorsque les cibles Prometheus sont `up`, que le retard Kafka reste inférieur à 100 messages et que le dashboard Grafana est disponible.

### b. Retard Kafka

```powershell
docker exec pharma-kafka /opt/kafka/bin/kafka-consumer-groups.sh `
  --bootstrap-server kafka:9092 --group pharma-postgres-raw-v1 --describe
```

Un retard ponctuel peut apparaître pendant un redémarrage. S'il continue d'augmenter, il faut vérifier le consommateur, la connectivité PostgreSQL et les erreurs d'écriture avant toute relance.

### c. Qualité analytique

```powershell
dbt test --project-dir .\dbt --profiles-dir .\dbt
dbt source freshness --project-dir .\dbt --profiles-dir .\dbt
```

Une transformation n'est pas considérée comme publiable si la fraîcheur de la source ou un test bloquant échoue.

## V. Traitement des incidents

### a. Détection et qualification

L'incident est d'abord identifié par l'alerte, son horodatage, le composant concerné et la dernière donnée saine. La qualification distingue l'arrêt de collecte, le retard de consommation, le rejet de contrat, l'échec PostgreSQL et l'échec de transformation.

### b. Confinement

Les messages invalides sont placés dans `pharma.sensor.dlq.v1`. Les offsets valides ne doivent pas être réinitialisés tant que la cause n'est pas comprise. Une interruption de la publication analytique est préférable à la diffusion d'indicateurs incohérents.

### c. Reprise et vérification

Après correction, le consommateur est relancé avec le même groupe. L'idempotence repose sur `raw_hash` côté PostgreSQL et sur la clé technique issue de la partition et de l'offset. La reprise est validée par le retour du retard à zéro, l'absence de nouvelles erreurs et la réussite des tests dbt.

### d. Retour d'expérience

Le compte rendu conserve la chronologie, l'impact métier, la cause, la correction, les contrôles effectués et l'action préventive. Les captures seules ne suffisent pas : les journaux et fichiers de preuve horodatés sont attachés au ticket d'incident.

## VI. Sécurité et passage en production

Les mots de passe présents dans l'environnement conteneurisé sont réservés à la validation. Un déploiement industriel exige un gestionnaire de secrets, TLS sur MQTT et Kafka, SASL ou mTLS pour les identités techniques, RBAC sur les outils, chiffrement des volumes, sauvegardes testées et journalisation des accès. Les ports d'administration ne sont pas exposés publiquement.
