import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "raw" / "mqtt_raw.db"
DEFAULT_PROFILE = PROJECT_ROOT / "config" / "machine_signal_profile.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def raw_hash(topic: str, payload: bytes) -> str:
    h = hashlib.sha256()
    h.update(topic.encode("utf-8"))
    h.update(b"\0")
    h.update(payload)
    return h.hexdigest()


def load_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_mqtt_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_utc TEXT NOT NULL,
            broker TEXT NOT NULL,
            topic TEXT NOT NULL,
            qos INTEGER NOT NULL,
            retained INTEGER NOT NULL,
            payload_text TEXT NOT NULL,
            payload_json TEXT,
            raw_hash TEXT NOT NULL UNIQUE,
            classification TEXT NOT NULL,
            matched_keywords TEXT NOT NULL,
            machine_id TEXT,
            supplier TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS capture_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            broker TEXT NOT NULL,
            topics TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def parse_payload(payload: bytes) -> tuple[str, dict | None]:
    text = payload.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
        return text, parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return text, None


def classify(topic: str, payload_text: str, payload_json: dict | None, profile: dict) -> tuple[str, list[str], str | None, str | None]:
    haystack = f"{topic} {payload_text}".lower()
    matched = []

    for key in profile["machine_keywords"] + profile["signal_fields"]:
        if key.lower() in haystack:
            matched.append(key)

    supplier = None
    for vendor in profile["known_suppliers"]:
        if vendor.lower() in haystack:
            supplier = vendor
            matched.append(vendor)
            break

    machine_id = None
    if payload_json:
        machine_id = payload_json.get("machine_id") or payload_json.get("asset_id")

    if payload_json and any(field in payload_json for field in profile["signal_fields"]):
        return "production_machine_signal", sorted(set(matched)), machine_id, supplier

    if matched:
        return "possible_production_signal", sorted(set(matched)), machine_id, supplier

    return "unclassified", [], machine_id, supplier


def is_allowed_topic(topic: str, allowed_prefixes: list[str]) -> bool:
    return any(topic.startswith(prefix) for prefix in allowed_prefixes)


def insert_event(conn: sqlite3.Connection, event: dict) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO raw_mqtt_events (
                received_at_utc, broker, topic, qos, retained, payload_text, payload_json,
                raw_hash, classification, matched_keywords, machine_id, supplier
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["received_at_utc"],
                event["broker"],
                event["topic"],
                event["qos"],
                int(event["retained"]),
                event["payload_text"],
                event["payload_json"],
                event["raw_hash"],
                event["classification"],
                event["matched_keywords"],
                event["machine_id"],
                event["supplier"],
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def format_received_summary(payload_json: dict | None, fallback_machine_id: str | None, fallback_supplier: str | None) -> str:
    if not payload_json:
        return "payload non JSON"

    machine_id = payload_json.get("machine_id") or payload_json.get("asset_id") or fallback_machine_id or "n/a"
    supplier = payload_json.get("supplier") or fallback_supplier or "n/a"
    return (
        f"site={payload_json.get('site_id', 'n/a')} | {machine_id} | {payload_json.get('machine_type', 'n/a')} | {supplier} | "
        f"room={payload_json.get('room_id', 'n/a')} | zone={payload_json.get('zone', 'n/a')} | "
        f"lat={payload_json.get('latitude', 'n/a')} lon={payload_json.get('longitude', 'n/a')} | "
        f"lot={payload_json.get('batch_id', 'n/a')} | état={payload_json.get('state', 'n/a')} | "
        f"temp={payload_json.get('temperature_c', 'n/a')}°C | "
        f"alarme={payload_json.get('alarm_code') or 'aucune'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture MQTT brute vers SQLite.")
    parser.add_argument("--broker", default="test.mosquitto.org")
    parser.add_argument("--broker-alias", default="mqtt-recette-01")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--duration-seconds", type=int, default=7200)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--topic",
        action="append",
        default=None,
        help="Topic MQTT à écouter. Répéter l'option pour plusieurs topics.",
    )
    args = parser.parse_args()
    if not args.topic:
        args.topic = ["pharma/production/site-042/#", "pharma/coldchain/site-042/#"]
    display_broker = args.broker_alias or args.broker

    profile = load_profile(args.profile)
    conn = init_db(args.db)
    started_at = utc_now()
    run_id = conn.execute(
        "INSERT INTO capture_runs (started_at_utc, broker, topics, duration_seconds, status) VALUES (?, ?, ?, ?, ?)",
        (started_at, display_broker, json.dumps(args.topic), args.duration_seconds, "running"),
    ).lastrowid
    conn.commit()

    allowed_prefixes = profile["allowed_topic_prefixes"]
    deadline = time.monotonic() + args.duration_seconds
    counters = {"stored": 0, "duplicates": 0, "ignored": 0}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"[{utc_now()}] connecté à {display_broker}:{args.port} reason={reason_code}", flush=True)
        for topic in args.topic:
            client.subscribe(topic, qos=1)
            print(f"[{utc_now()}] écoute topic: {topic}", flush=True)

    def on_message(client, userdata, msg):
        if not is_allowed_topic(msg.topic, allowed_prefixes):
            counters["ignored"] += 1
            return

        payload_text, payload_json = parse_payload(msg.payload)
        classification, matched, machine_id, supplier = classify(msg.topic, payload_text, payload_json, profile)
        event = {
            "received_at_utc": utc_now(),
            "broker": display_broker,
            "topic": msg.topic,
            "qos": msg.qos,
            "retained": msg.retain,
            "payload_text": payload_text,
            "payload_json": json.dumps(payload_json, ensure_ascii=False) if payload_json else None,
            "raw_hash": raw_hash(msg.topic, msg.payload),
            "classification": classification,
            "matched_keywords": json.dumps(matched, ensure_ascii=False),
            "machine_id": machine_id,
            "supplier": supplier,
        }
        if insert_event(conn, event):
            counters["stored"] += 1
            print(f"[{event['received_at_utc']}] stored {classification} {msg.topic}", flush=True)
            print(f"  {format_received_summary(payload_json, machine_id, supplier)}", flush=True)
        else:
            counters["duplicates"] += 1

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()

    try:
        while time.monotonic() < deadline:
            time.sleep(2)
    finally:
        client.loop_stop()
        client.disconnect()
        conn.execute(
            "UPDATE capture_runs SET ended_at_utc = ?, status = ? WHERE id = ?",
            (utc_now(), f"finished stored={counters['stored']} duplicates={counters['duplicates']} ignored={counters['ignored']}", run_id),
        )
        conn.commit()
        print(f"[{utc_now()}] capture terminée: {counters}", flush=True)
        conn.close()


if __name__ == "__main__":
    main()
