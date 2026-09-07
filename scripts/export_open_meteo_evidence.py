"""Produit une preuve visuelle depuis le JSON Open-Meteo réellement conservé."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "open_meteo"
OUTPUT_PATH = PROJECT_ROOT / "assets" / "evidence" / "open_meteo_collection_snapshot.svg"


def postgres_dsn() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '55432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )


def latest_record() -> tuple[Path, dict]:
    files = sorted(RAW_DIRECTORY.glob("open_meteo_*.json"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"Aucun fichier Open-Meteo disponible dans {RAW_DIRECTORY}")
    path = files[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def load_status(payload_hash: str) -> dict | None:
    query = """
        SELECT site_id, fetched_at, observed_at, temperature_c, relative_humidity_pct, loaded_at
        FROM raw.open_meteo_snapshot
        WHERE payload_hash = %s
    """
    with psycopg.connect(postgres_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (payload_hash,))
            row = cursor.fetchone()
    if row is None:
        return None
    keys = ("site_id", "fetched_at", "observed_at", "temperature_c", "relative_humidity_pct", "loaded_at")
    return dict(zip(keys, row, strict=True))


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def iso(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def build_svg(record_path: Path, record: dict, row: dict | None) -> str:
    current = record["payload"].get("current", {})
    payload_hash = record["payload_hash"]
    status = "Ligne retrouvée et chargement tracé" if row else "Ligne non retrouvée"
    status_color = "#1E9B79" if row else "#C34A4A"
    observed_at = current.get("time", "n/a")
    temperature = current.get("temperature_2m", "n/a")
    humidity = current.get("relative_humidity_2m", "n/a")
    weather_code = current.get("weather_code", "n/a")
    wind_speed = current.get("wind_speed_10m", "n/a")
    json_lines = [
        '{',
        '  "source": "Open-Meteo Forecast API",',
        f'  "site_id": "{record["site_id"]}",',
        f'  "fetched_at": "{record["fetched_at"]}",',
        f'  "payload_hash": "{payload_hash[:24]}...",',
        '  "payload": {',
        f'    "time": "{observed_at}",',
        f'    "temperature_2m": {temperature},',
        f'    "relative_humidity_2m": {humidity}',
        '  }',
        '}',
    ]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        '<rect width="1920" height="1080" fill="#F5FAFA"/>',
        '<rect x="55" y="48" width="1810" height="128" rx="10" fill="#123047"/>',
        '<text x="98" y="104" font-family="Georgia, serif" font-size="38" fill="#FFFFFF">Export de preuve - collecte API Open-Meteo</text>',
        '<text x="98" y="144" font-family="Arial, sans-serif" font-size="21" fill="#BFEFE4">Source HTTP externe, JSON brut conservé, chargement PostgreSQL traçable</text>',
        '<rect x="55" y="215" width="870" height="700" rx="10" fill="#FFFFFF" stroke="#C8DDDD"/>',
        '<text x="95" y="270" font-family="Georgia, serif" font-size="30" fill="#123047">Fichier brut conservé</text>',
        f'<text x="95" y="315" font-family="Arial, sans-serif" font-size="20" fill="#172B3A">{esc(record_path.name)}</text>',
        '<rect x="95" y="350" width="790" height="410" rx="8" fill="#123047"/>',
    ]
    for index, line in enumerate(json_lines):
        lines.append(
            f'<text x="125" y="{405 + index * 35}" font-family="Consolas, monospace" font-size="20" fill="#DDF3E9">{esc(line)}</text>'
        )
    lines.extend(
        [
            '<text x="95" y="815" font-family="Arial, sans-serif" font-size="19" fill="#52717C">Point de contexte : site 042. Les coordonnées ne sont pas exposées dans le rendu.</text>',
            '<rect x="970" y="215" width="895" height="700" rx="10" fill="#FFFFFF" stroke="#C8DDDD"/>',
            '<text x="1010" y="270" font-family="Georgia, serif" font-size="30" fill="#123047">Chargement et lecture observée</text>',
            f'<rect x="1010" y="305" width="615" height="52" rx="26" fill="{status_color}"/>',
            f'<text x="1040" y="339" font-family="Arial, sans-serif" font-size="21" fill="#FFFFFF">{esc(status)}</text>',
            '<text x="1010" y="420" font-family="Arial, sans-serif" font-size="23" fill="#52717C">Table cible</text>',
            '<text x="1010" y="455" font-family="Consolas, monospace" font-size="25" fill="#172B3A">raw.open_meteo_snapshot</text>',
            '<text x="1010" y="525" font-family="Arial, sans-serif" font-size="23" fill="#52717C">Observation reçue</text>',
            f'<text x="1010" y="566" font-family="Arial, sans-serif" font-size="27" fill="#172B3A">{esc(observed_at)} UTC</text>',
            '<text x="1010" y="640" font-family="Arial, sans-serif" font-size="23" fill="#52717C">Température / humidité</text>',
            f'<text x="1010" y="681" font-family="Georgia, serif" font-size="36" fill="#2F9FD0">{esc(temperature)} °C  |  {esc(humidity)} %</text>',
            f'<text x="1010" y="740" font-family="Arial, sans-serif" font-size="21" fill="#172B3A">Code météo : {esc(weather_code)} | Vent : {esc(wind_speed)} km/h</text>',
            '<text x="1010" y="815" font-family="Arial, sans-serif" font-size="20" fill="#52717C">Empreinte SHA-256 pour l’idempotence</text>',
            f'<text x="1010" y="850" font-family="Consolas, monospace" font-size="17" fill="#172B3A">{esc(payload_hash)}</text>',
        ]
    )
    if row:
        lines.append(
            f'<text x="1010" y="890" font-family="Arial, sans-serif" font-size="17" fill="#52717C">Chargé le {esc(iso(row["loaded_at"]))}</text>'
        )
    lines.extend(
        [
            '<text x="55" y="1040" font-family="Arial, sans-serif" font-size="17" fill="#52717C">Export généré depuis le fichier JSON brut et PostgreSQL. Il ne reproduit pas une interface tierce.</text>',
            '</svg>',
        ]
    )
    return "\n".join(lines)


def main() -> None:
    record_path, record = latest_record()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_svg(record_path, record, load_status(record["payload_hash"])), encoding="utf-8")
    print(f"Preuve Open-Meteo générée : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
