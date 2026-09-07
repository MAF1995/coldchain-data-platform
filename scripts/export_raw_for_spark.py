import json
import os
from pathlib import Path

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "lake" / "raw" / "sensor_events.jsonl"


def connection_string() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '55432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with psycopg.connect(connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload_json
                FROM raw.mqtt_sensor_event
                ORDER BY event_time, raw_hash
                """
            )
            with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as stream:
                for (payload,) in cursor:
                    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    count += 1
    print(f"Export Spark terminé: rows={count}, path={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
