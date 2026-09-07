"""Charge les réponses Open-Meteo brutes dans PostgreSQL de façon idempotente."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "open_meteo"

CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.open_meteo_snapshot (
    payload_hash TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    site_id TEXT NOT NULL,
    requested_latitude NUMERIC(9, 6) NOT NULL,
    requested_longitude NUMERIC(9, 6) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ,
    temperature_c NUMERIC(6, 3),
    relative_humidity_pct NUMERIC(6, 3),
    weather_code INTEGER,
    wind_speed_kmh NUMERIC(7, 3),
    payload_json JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_open_meteo_snapshot_site_time
    ON raw.open_meteo_snapshot (site_id, fetched_at DESC);
"""

INSERT_SQL = """
INSERT INTO raw.open_meteo_snapshot (
    payload_hash, source_name, source_url, site_id,
    requested_latitude, requested_longitude, fetched_at,
    observed_at, temperature_c, relative_humidity_pct,
    weather_code, wind_speed_kmh, payload_json
)
VALUES (
    %(payload_hash)s, %(source_name)s, %(source_url)s, %(site_id)s,
    %(requested_latitude)s, %(requested_longitude)s, %(fetched_at)s,
    %(observed_at)s, %(temperature_c)s, %(relative_humidity_pct)s,
    %(weather_code)s, %(wind_speed_kmh)s, %(payload_json)s::jsonb
)
ON CONFLICT (payload_hash) DO NOTHING;
"""


def postgres_connection_string() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '55432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )


def to_row(record: dict[str, Any]) -> dict[str, Any]:
    payload = record["payload"]
    current = payload.get("current", {})
    location = record["requested_location"]
    return {
        "payload_hash": record["payload_hash"],
        "source_name": record["source"],
        "source_url": record["source_url"],
        "site_id": record["site_id"],
        "requested_latitude": location["latitude"],
        "requested_longitude": location["longitude"],
        "fetched_at": record["fetched_at"],
        "observed_at": current.get("time"),
        "temperature_c": current.get("temperature_2m"),
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "weather_code": current.get("weather_code"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "payload_json": json.dumps(record, ensure_ascii=False),
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Charge les fichiers Open-Meteo bruts dans PostgreSQL.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    source_dir = arguments.source_dir.resolve()
    files = sorted(source_dir.glob("open_meteo_*.json"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier Open-Meteo dans {source_dir}")

    inserted = 0
    with psycopg.connect(postgres_connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            for path in files:
                record = json.loads(path.read_text(encoding="utf-8"))
                cursor.execute(INSERT_SQL, to_row(record))
                inserted += cursor.rowcount
        connection.commit()

    print(f"Chargement Open-Meteo terminé : inserted={inserted}, fichiers={len(files)}")


if __name__ == "__main__":
    main()
