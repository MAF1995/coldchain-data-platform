# Cahier de recette de la plateforme data

## I. Stratégie

La recette combine des tests unitaires, des tests de contrat, des contrôles d'intégration, des tests dbt et des vérifications d'exploitation. Chaque essai doit pouvoir être rejoué à partir d'une commande et produire une preuve datée.

## II. Cas de test

| ID | Contrôle | Résultat attendu | Preuve | Statut initial |
| --- | --- | --- | --- | --- |
| T01 | Validation de `compose.infrastructure.yml` | Le manifeste fusionné est valide | Sortie `docker compose config --quiet` | Réussi |
| T02 | Tests du contrat Python | Empreinte, enveloppe, idempotence et normalisation valides | Rapport `pytest` | Réussi, 9 tests |
| T03 | Parcours MQTT → Kafka → PostgreSQL | Chaque message valide atteint la table brute | Logs des deux services et métriques | Réussi |
| T04 | Reprise du consommateur | Aucun doublon après redémarrage | Contrainte `raw_hash` et compteur de doublons | Réussi |
| T05 | Barrière qualité Airflow/dbt | Toutes les tâches sont vertes et les tests passent | Interface Airflow et `airflow_last_run.json` | Réussi |
| T06 | Calcul distribué Spark | Deux workers traitent la source et écrivent le Parquet | Interface Spark et `spark_last_run.json` | Réussi |
| T07 | Collecte Prometheus | Les trois cibles attendues sont `up` | Page Targets et API | Réussi |
| T08 | Règles d'alerte | Les cinq règles sont chargées sans erreur | Sortie `promtool check rules` | Réussi |
| T09 | Dashboard Grafana | Le dashboard provisionné affiche les métriques du pipeline | Interface Grafana et API | Réussi |
| T10 | CI/CD | Tests, dbt, manifeste, image et SBOM sont automatisés | Run `workflow_dispatch` `34112884626`, artefact `dbt-target-34112884626`, image OCI au digest `sha256:d95aba66a9b56b5c3eb6dd9a5c0b3ae012aabb9b325244ad9b6a926d9d36a05d` | Réussi le 7 septembre 2026 |

## III. Seuils d'acceptation

### a. Disponibilité

Les cibles `mqtt-kafka-bridge`, `kafka-postgres-consumer` et `prometheus` doivent être joignables. Une indisponibilité de plus d'une minute ouvre une alerte critique.

### b. Fraîcheur et retard

Une absence de message MQTT valide pendant plus de deux minutes déclenche un avertissement. Le retard maximal du consommateur doit rester inférieur à 100 messages et revenir à zéro après une reprise normale.

### c. Qualité des données

Les clés techniques ne peuvent être nulles ou dupliquées. Les états machines sont limités à `RUNNING`, `IDLE` et `ALARM`. Chaque type de machine doit être rattaché au référentiel de règles de mesure.

### d. Publication analytique

La publication est autorisée si les modèles dbt se construisent, si les tests sont réussis et si la barrière Airflow indique `PASSED`. Une erreur bloque la mise à disposition des nouveaux indicateurs.

## IV. Anomalies et décision

Chaque anomalie reçoit un niveau de gravité, un composant responsable, une preuve, une décision et une date de clôture. Une dérogation ne peut pas masquer un défaut de traçabilité, de sécurité ou de cohérence des indicateurs.
