# Audit des critères éliminatoires

État des preuves disponibles dans le projet au 7 septembre 2026. Cet audit ne remplace pas la décision du jury : il vérifie simplement ce qui est effectivement démontré par les dossiers, le code, les captures et les fichiers de configuration.

> Dans la feuille **Fiche récapitulative**, `C2.1.2` est le seul critère coloré en vert (`FFC5E0B3`). Les autres critères marqués **Éliminatoire : OUI** sont colorés en orange. Ils sont tous inclus ci-dessous pour éviter une lecture trop restrictive de la mise en forme.

## Priorité immédiate

| Compétence | État | Conclusion |
| --- | --- | --- |
| C2.1.2 | Couvert | Les axes d'analyse, la sélection des données et les métriques sont explicitement définis dans le bloc II. |

## État par bloc

| Bloc | Compétence éliminatoire | État | Éléments de preuve actuels | Reste à sécuriser |
| --- | --- | --- | --- | --- |
| I | C1.1.2 - collecte via API, bases disponibles, crawling/scraping si pertinent | **Couvert** | Collecte Open-Meteo exécutée le 7 septembre 2026, JSON brut conservé avec URL, horodatage et SHA-256, puis chargement idempotent dans `raw.open_meteo_snapshot`. Le dossier explique aussi pourquoi le scraping réglementaire n'est pas retenu. | Conserver une capture de l'exécution, du payload brut et de la requête PostgreSQL. |
| I | C1.2.2 - construire une base adaptée | **Couvert** | PostgreSQL, schémas `raw`, `clean`, `analytics`, contraintes d'unicité et modèles dbt. | Conserver la capture des schémas PostgreSQL et des tables. |
| I | C1.3.2 - transformer les données | **Couvert** | Python, SQL/dbt et Spark : normalisation, qualification thermique, agrégats et Parquet. | Aucune lacune bloquante identifiée. |
| I | C1.3.3 - développer un ETL automatisé | **Couvert** | MQTT vers Kafka puis PostgreSQL, Airflow, dbt et scripts de relance. | Conserver les preuves d'exécution de bout en bout. |
| II | C2.1.2 - axes d'analyse et métriques | **Couvert** | Cinq axes d'analyse, dictionnaire de KPI, règles de calcul et périmètre de décision. | Critère vert : il est convenablement traité. |
| II | C2.1.3 - requêtes et calculs | **Couvert** | Notebook reproductible, requêtes SQL, dbt et dashboard Metabase. | Conserver le notebook et les captures du dashboard. |
| II | C2.2.1 - représentation adaptée | **Couvert** | Visualisations Metabase, graphiques du notebook et tableaux d'investigation. | Vérifier que les légendes et conclusions restent lisibles dans le PDF. |
| III | C3.1.2 - charge, ressources, budget | **Couvert** | Charge par rôle, taux journalier, budget de référence, réserve de risque et analyse qualité-coût-délai. | Présenter les chiffres comme une estimation de projet, non comme une dépense réellement engagée. |
| III | C3.2.1 - planifier l'exécution | **Couvert** | Méthode Kanban, Gantt, chemin critique, RACI et dispositions d'accessibilité. | Aucune lacune bloquante identifiée. |
| III | C3.2.2 - suivre l'avancement | **Partiel** | Tableau de bord projet, jalons, seuils, valeurs observées et modèle de compte rendu sont décrits dans le dossier. | Ajouter la preuve d'un outil effectivement utilisé : capture Kanban ou équivalent, jalons, responsables, dates et compte rendu associé. |
| IV | C4.2.1 - concevoir l'entrepôt | **Couvert** | Architecture en zones `raw`, `clean`, `analytics`, modèles dbt, règles de qualité et accès documentés. | Conserver le diagramme de lineage dbt et les captures PostgreSQL. |
| IV | C4.2.2 - mettre en place des pipelines data | **Couvert** | Pipeline temps réel MQTT/Kafka/PostgreSQL, orchestration Airflow et traitement Spark. | Les GIFs Grafana, Airflow et Spark constituent de bonnes preuves visuelles. |
| IV | C4.2.3 - automatiser intégration et déploiement par CI/CD | **Partiel** | Workflow GitHub Actions versionné : tests Python, validation de configuration, dbt, artefacts et build d'image. | Exécuter le workflow sur un dépôt contrôlé, puis conserver l'URL du run, l'artefact dbt et le digest d'image. |

## Preuves principales

- Bloc I : [dossier](bloc1_dossier_v1.md), [schéma SQL](../sql/schema.sql), [scripts d'ingestion](../src/).
- Bloc II : [dossier](bloc2_dossier_v1.md), [notebook](../notebooks/bloc2_qualite_donnees.ipynb), [KPI](../analytics/kpi_definitions.yml).
- Bloc III : [dossier](bloc3_dossier_v1.md), notamment les sections V, VII et VIII.
- Bloc IV : [support](bloc4_support_v1.md), [cahier de recette](bloc4_cahier_recette.md), [runbook](bloc4_runbook_technique.md), [workflow CI/CD](../.github/workflows/data-platform-ci.yml).

## Verdict

Onze critères éliminatoires sur treize sont documentés et techniquement étayés. Deux sujets ne doivent pas être présentés comme complètement réalisés :

1. **C3.2.2** : le dispositif de pilotage est décrit, mais la capture d'un outil réellement renseigné manque encore.
2. **C4.2.3** : la CI/CD est implémentée dans le dépôt, mais une exécution GitHub Actions distante et son artefact restent à produire.

Les deux actions de sécurisation restantes sont une preuve de Kanban pour le bloc III, puis un run CI/CD documenté pour le bloc IV.

## Audit de la présentation du bloc IV

La présentation est cohérente avec l'infrastructure démontrée : MQTT, Kafka, PostgreSQL, dbt, Airflow, Spark, Prometheus et Grafana sont tous présents dans le code, les manifestes ou les preuves. Les GIFs ont une vraie valeur probante et doivent être conservés.

| Diapositive | Alignement | Point d'attention | Ajustement conseillé |
| --- | --- | --- | --- |
| 7 - Flux Grafana | Partiel | Le GIF montre des compteurs cumulés supérieurs à `60`, alors que la recette finale affiche `60 = 60 = 60`. Le premier encart chiffré est d'ailleurs absent. | Utiliser une seule capture de la séquence `60 = 60 = 60`, ou titrer explicitement le GIF comme une supervision cumulée et corriger l'encart manquant. |
| 8 - Mosaïque thermique | Partiel | Les salles de procédé à environ `20 °C` côtoient les salles froides à `2-8 °C`, sans légende de référence. | Montrer les plages min/max/référence ajoutées au dashboard et préciser que seule la chaîne froide est évaluée à `2-8 °C`. |
| 9 - dbt | Couvert | Le lineage dbt est visible et rattache bien le brut au mart journalier. | Conserver cette diapositive et citer le résultat `20/20` comme résultat de la recette analytique figée. |
| 10 - Airflow | Couvert | Les deux GIFs prouvent le DAG et les tâches, mais le bandeau supérieur est très fin à distance. | Garder les GIFs, agrandir légèrement le DAG ou ajouter un arrêt sur image de la tâche `quality_gate` réussie. |
| 13 - Alertes | Couvert avec nuance | Les règles sont chargées, mais la capture ne prouve pas une alerte réellement distribuée à une astreinte. | Dire « règles testées et chargées » ; ne pas dire « chaîne d'astreinte démontrée ». |
| 15 - Incident Spark | Couvert avec nuance | La correction est décrite précisément, mais la diapositive ne montre pas le log d'échec ni la preuve de rejeu. | Ajouter en annexe une capture log avant/après ou faire ouvrir le runbook si le jury le demande. |
| 16 - Recette | Partiel | Les chiffres `527`, `20/20` et `60=60=60` proviennent de recettes différentes, non identifiées comme telles. | Ajouter les mentions « recette analytique figée : 527 » et « séquence streaming : 60 » afin d'éviter l'apparence d'une incohérence. |
| 17-18 - Roadmap et bilan | Partiel | Le bilan doit rester cohérent avec l'absence de run CI/CD distant. | Ajouter « exécution CI/CD distante et artefacts » dans le bloc « Avant production ». |

Le diaporama est un support du bloc IV : il n'a pas à répéter les blocs I à III. Pour anticiper une question transverse, prévoir trois diapositives annexes non projetées par défaut : la collecte API du bloc I, un tableau Kanban du bloc III et le run CI/CD du bloc IV après son exécution.
