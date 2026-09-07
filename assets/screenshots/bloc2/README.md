# Captures prévues pour le bloc II

Les captures sont réalisées après exécution de
`scripts/run_bloc2_foundation.ps1`.

| Fichier | Contenu | Utilisation prévue |
| --- | --- | --- |
| `01_couverture_temporelle.png` | Répartition des événements par créneau actif | Justifier la limite du jeu actuel |
| `02_temperature_par_equipement.png` | Distribution des températures selon l'équipement | Montrer pourquoi une règle uniforme est incorrecte |
| `03_dbt_tests.png` | Terminal avec les tests dbt réussis | Prouver la qualité et la reproductibilité |
| `04_dbt_lineage.png` | Graphe de lignage généré par dbt Docs | Expliquer le passage de `raw` vers les tables analytiques |
| `05_requete_kpi.png` | Résultat SQL de `mart_quality_daily` | Présenter les calculs et les premiers résultats |
| `06_notebook_statistiques.png` | Hypothèses, test retenu et résultat interprété | Documenter la méthodologie statistique |
| `07_dashboard_power_bi.png` | Vue principale du dashboard qualité | Restituer les résultats au commanditaire |

Les deux premières images sont générées automatiquement par le notebook.
Les captures `03` à `05` peuvent être réalisées dès maintenant. Les captures
`06` et `07` seront produites après constitution du jeu longitudinal.

