# Trame orale - Bloc IV

Durée cible : 30 minutes. Ne pas lire les diapositives. Garder environ une minute trente par écran, avec un peu plus de temps sur les preuves Grafana, Airflow, Spark et l'incident.

## I. Mise en situation - diapositives 1 à 3, 4 minutes

Le sujet porte sur la supervision de la chaîne du froid d'un périmètre industriel anonymisé. Le besoin n'est pas uniquement de recevoir des températures : il faut pouvoir expliquer l'origine d'une donnée, la transformer, détecter une rupture, puis rejouer si nécessaire.

La plateforme ne décide pas de la libération d'un lot. Elle apporte une donnée technique traçable aux équipes qualité, production et data.

## II. Architecture et conteneurs - diapositives 4 à 6, 5 minutes

Présenter le flux : capteurs, MQTT, Kafka, PostgreSQL, qualité. Docker permet de lancer chaque responsabilité de manière isolée et reproductible. Ne pas détailler les commandes Docker : expliquer la responsabilité de chaque groupe de services.

Phrase de transition : « L'architecture est utile seulement si je peux prouver que la donnée arrive, que je peux la contrôler et que je sais réagir lorsqu'un maillon échoue. »

## III. Preuves de traitement - diapositives 7 à 10, 7 minutes

Grafana : 60 messages MQTT reçus, 60 événements Kafka et 60 insertions PostgreSQL. Le lag nul signifie qu'il n'y a pas de message en attente à cet instant. La latence p95 est de 738 ms. Préciser que ce n'est pas un benchmark de capacité maximale.

dbt : le brut reste conservé, les couches clean et analytics rendent les données exploitables. Les 20 tests dbt couvrent notamment l'unicité, les clés, les statuts et les relations.

Airflow : les six tâches vertes montrent une orchestration exécutable et une barrière qualité. Spark : deux workers et une application terminée démontrent le chemin distribué, sans prétendre que Spark est nécessaire pour seulement 527 lignes.

## IV. Supervision et maîtrise - diapositives 11 à 13, 4 minutes 30

Prometheus vérifie trois cibles techniques. Les cinq règles d'alerte couvrent indisponibilité, silence MQTT, lag, erreur de livraison et DLQ. Une alerte inactive signifie que les seuils ne sont pas atteints pendant la recette ; cela ne signifie pas qu'elle a déjà été testée dans toutes les conditions de panne.

Présenter ensuite les trois propriétés : intégrité, confidentialité, auditabilité.

## V. Incident et recette - diapositives 14 à 15, 4 minutes

L'incident Spark est concret : un volume créé avec les mauvais droits empêchait l'écriture des event logs. Expliquer la démarche : logs, localisation, UID, reproduction, correction. Le résultat est un rejeu réussi sans perte de donnée brute.

La recette ne repose pas sur une seule commande : 9 tests Python, 20 tests dbt, la réconciliation temps réel, Airflow, Spark et Prometheus sont vérifiés par des preuves distinctes.

## VI. Roadmap et conclusion - diapositives 16 à 18, 3 minutes 30

La prochaine étape n'est pas d'ajouter Snowflake ou un autre outil par réflexe. Elle consiste à durcir l'existant : identités, chiffrement, haute disponibilité, sauvegardes, test de charge et recette de préproduction.

Conclusion : « J'ai conçu une plateforme qui transforme un signal industriel en information vérifiable, rejouable et supervisée. Le socle est démontré ; la mise en production nécessite maintenant un durcissement et une qualification. »
