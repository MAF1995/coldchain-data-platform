"""Collecte et conserve une réponse brute de l'API Open-Meteo.

La réponse est enveloppée avec l'horodatage, le périmètre et l'URL réellement
appelée. Le fichier devient ainsi une preuve rejouable de la collecte externe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "open_meteo"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_record(
    payload: dict[str, Any],
    *,
    source_url: str,
    site_id: str,
    latitude: float,
    longitude: float,
    fetched_at: str,
) -> dict[str, Any]:
    """Build a stable raw envelope without changing the third-party payload."""
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    return {
        "source": "Open-Meteo Forecast API",
        "source_url": source_url,
        "site_id": site_id,
        "requested_location": {"latitude": latitude, "longitude": longitude},
        "fetched_at": fetched_at,
        "payload_hash": payload_hash,
        "payload": payload,
    }


def fetch_weather(latitude: float, longitude: float, timeout_seconds: int) -> tuple[dict[str, Any], str]:
    parameters = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "timezone": "UTC",
    }
    response = requests.get(
        OPEN_METEO_URL,
        params=parameters,
        headers={"User-Agent": "coldchain-data-platform/1.0"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json(), response.url


def write_record(record: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.fromisoformat(record["fetched_at"]).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"open_meteo_{record['site_id']}_{timestamp}.json"
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collecte une observation météo Open-Meteo et conserve le JSON brut.")
    parser.add_argument("--site-id", default="042")
    parser.add_argument("--latitude", type=float, default=45.70482)
    parser.add_argument("--longitude", type=float, default=4.88772)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    payload, source_url = fetch_weather(arguments.latitude, arguments.longitude, arguments.timeout_seconds)
    record = build_record(
        payload,
        source_url=source_url,
        site_id=arguments.site_id,
        latitude=arguments.latitude,
        longitude=arguments.longitude,
        fetched_at=utc_now(),
    )
    output_path = write_record(record, arguments.output_dir)
    current = payload.get("current", {})
    print(f"Collecte Open-Meteo terminée : {output_path}")
    print(f"hash={record['payload_hash']}")
    print(
        "observation="
        f"{current.get('time', 'n/a')} | température={current.get('temperature_2m', 'n/a')} °C | "
        f"humidité={current.get('relative_humidity_2m', 'n/a')} %"
    )


if __name__ == "__main__":
    main()
