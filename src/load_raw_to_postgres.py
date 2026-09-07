import argparse
import json
import os
import sqlite3
from pathlib import Path

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "raw" / "mqtt_raw.db"


CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.mqtt_sensor_event (
    raw_hash TEXT PRIMARY KEY,
    source_event_id BIGINT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    broker_alias TEXT NOT NULL,
    topic TEXT NOT NULL,
    qos SMALLINT NOT NULL,
    retained BOOLEAN NOT NULL,
    classification TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    machine_type TEXT NOT NULL,
    supplier TEXT,
    site_id TEXT,
    zone TEXT,
    room_id TEXT,
    batch_id TEXT,
    temperature_c NUMERIC(7, 3),
    humidity_pct NUMERIC(7, 3),
    pressure_bar NUMERIC(9, 3),
    vibration_mm_s NUMERIC(9, 3),
    motor_current_a NUMERIC(9, 3),
    rpm INTEGER,
    cycle_count BIGINT,
    state TEXT,
    alarm_code TEXT,
    payload_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mqtt_sensor_event_time
    ON raw.mqtt_sensor_event (event_time);
CREATE INDEX IF NOT EXISTS idx_mqtt_sensor_event_machine_time
    ON raw.mqtt_sensor_event (machine_id, event_time);
CREATE INDEX IF NOT EXISTS idx_mqtt_sensor_event_zone_time
    ON raw.mqtt_sensor_event (zone, event_time);

-- Le couple partition/offset peut recommencer après recréation d'un topic.
-- L'empreinte du message reste donc la seule clé d'idempotence globale.
ALTER TABLE raw.mqtt_sensor_event
    DROP CONSTRAINT IF EXISTS mqtt_sensor_event_source_event_id_key;
"""


INSERT_SQL = """
INSERT INTO raw.mqtt_sensor_event (
    raw_hash,
    source_event_id,
    event_time,
    received_at,
    broker_alias,
    topic,
    qos,
    retained,
    classification,
    machine_id,
    machine_type,
    supplier,
    site_id,
    zone,
    room_id,
    batch_id,
    temperature_c,
    humidity_pct,
    pressure_bar,
    vibration_mm_s,
    motor_current_a,
    rpm,
    cycle_count,
    state,
    alarm_code,
    payload_json
)
VALUES (
    %(raw_hash)s,
    %(source_event_id)s,
    %(event_time)s,
    %(received_at)s,
    %(broker_alias)s,
    %(topic)s,
    %(qos)s,
    %(retained)s,
    %(classification)s,
    %(machine_id)s,
    %(machine_type)s,
    %(supplier)s,
    %(site_id)s,
    %(zone)s,
    %(room_id)s,
    %(batch_id)s,
    %(temperature_c)s,
    %(humidity_pct)s,
    %(pressure_bar)s,
    %(vibration_mm_s)s,
    %(motor_current_a)s,
    %(rpm)s,
    %(cycle_count)s,
    %(state)s,
    %(alarm_code)s,
    %(payload_json)s::jsonb
)
ON CONFLICT (raw_hash) DO NOTHING;
"""


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Charge les événements MQTT SQLite dans PostgreSQL."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Chemin vers la base SQLite brute.",
    )
    return parser.parse_args()


def postgres_connection_string():
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '55432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )


def source_rows(source_path):
    connection = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield from connection.execute(
            """
            SELECT
                id,
                received_at_utc,
                broker,
                topic,
                qos,
                retained,
                payload_json,
                raw_hash,
                classification,
                machine_id,
                supplier
            FROM raw_mqtt_events
            ORDER BY id
            """
        )
    finally:
        connection.close()


def normalized_event(row):
    payload = json.loads(row["payload_json"] or "{}")
    machine_id = payload.get("machine_id") or row["machine_id"]
    machine_type = payload.get("machine_type")
    event_time = payload.get("timestamp") or row["received_at_utc"]

    if not machine_id or not machine_type:
        return None

    return {
        "raw_hash": row["raw_hash"],
        "source_event_id": row["id"],
        "event_time": event_time,
        "received_at": row["received_at_utc"],
        "broker_alias": row["broker"],
        "topic": row["topic"],
        "qos": row["qos"],
        "retained": bool(row["retained"]),
        "classification": row["classification"],
        "machine_id": machine_id,
        "machine_type": machine_type,
        "supplier": payload.get("supplier") or row["supplier"],
        "site_id": payload.get("site_id"),
        "zone": payload.get("zone"),
        "room_id": payload.get("room_id"),
        "batch_id": payload.get("batch_id"),
        "temperature_c": payload.get("temperature_c"),
        "humidity_pct": payload.get("humidity_pct"),
        "pressure_bar": payload.get("pressure_bar"),
        "vibration_mm_s": payload.get("vibration_mm_s"),
        "motor_current_a": payload.get("motor_current_a"),
        "rpm": payload.get("rpm"),
        "cycle_count": payload.get("cycle_count"),
        "state": payload.get("state"),
        "alarm_code": payload.get("alarm_code"),
        "payload_json": json.dumps(payload, ensure_ascii=False),
    }


def main():
    arguments = parse_arguments()
    source_path = arguments.source.resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {source_path}")

    inserted = 0
    ignored = 0

    with psycopg.connect(postgres_connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            for row in source_rows(source_path):
                event = normalized_event(row)
                if event is None:
                    ignored += 1
                    continue
                cursor.execute(INSERT_SQL, event)
                inserted += cursor.rowcount
        connection.commit()

    print(
        f"Chargement terminé : inserted={inserted}, "
        f"ignored={ignored}, source={source_path}"
    )


if __name__ == "__main__":
    main()
