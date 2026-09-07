# Preuve de pilotage : GitHub Projects

Le tableau de pilotage est créé dans GitHub Projects, en visibilité privée. Il constitue la preuve de suivi du bloc III : les jalons, le responsable, la date d'échéance et le statut sont visibles sur une seule vue.

## I. Création

Après l'authentification GitHub, exécuter depuis la racine du projet :

```powershell
.\scripts\bootstrap_github_project.ps1 -OpenInBrowser
```

Le script crée ou réutilise le projet **Pilotage - plateforme data chaîne du froid**, le rend privé, puis ajoute les champs suivants :

| Champ | Finalité |
| --- | --- |
| Jalon | Rattacher la tâche au bloc ou à la soutenance. |
| Statut de preuve | Distinguer le travail terminé, en cours et à faire. |
| Responsable | Identifier le pilote de la tâche. |
| Échéance | Rendre le suivi temporel vérifiable. |

## II. Capture à conserver

Dans GitHub Projects, sélectionner la vue **Table** et afficher les quatre champs ci-dessus. La capture doit montrer au minimum `PIL-06`, `PIL-07` et `PIL-08`, afin de rendre visible l'enchaînement entre une preuve terminée, la CI/CD en cours et la recette finale planifiée.

Cette capture est à insérer dans le bloc III, après la section consacrée au suivi d'avancement.
