# Preuve de collecte externe : Open-Meteo

Cette procédure complète la collecte MQTT avec une API HTTP externe pertinente pour l'analyse d'une excursion thermique : la météo extérieure permet de contextualiser un retard de transport ou une dérive de température.

## I. Exécution

```powershell
.\scripts\run_open_meteo_collection.ps1
```

La commande appelle l'API Open-Meteo, écrit le JSON brut sous `data/raw/open_meteo/`, puis charge la réponse dans `raw.open_meteo_snapshot` avec une empreinte SHA-256 idempotente.

## II. Preuves à conserver

1. La sortie de la commande indiquant le fichier JSON et son empreinte.
2. Le contenu horodaté du fichier brut.
3. La requête PostgreSQL suivante :

```sql
SELECT
    site_id,
    fetched_at,
    observed_at,
    temperature_c,
    relative_humidity_pct,
    payload_hash
FROM raw.open_meteo_snapshot
ORDER BY fetched_at DESC;
```

La documentation de l'API est disponible sur [Open-Meteo](https://open-meteo.com/en/docs).
