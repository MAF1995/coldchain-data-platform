import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "mqtt_raw.db"


def fmt(value: object, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def read_payload(payload_json: str | None) -> dict:
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_payload(payload_json: str | None, fallback_supplier: str | None) -> str:
    payload = read_payload(payload_json)
    if not payload:
        return "payload non JSON"

    supplier = payload.get("supplier") or fallback_supplier
    parts = [
        fmt(payload.get("batch_id") or payload.get("lot_id")),
        fmt(payload.get("machine_type")),
        fmt(supplier),
        fmt(payload.get("state")),
        fmt(payload.get("alarm_code")),
        fmt(payload.get("zone")),
        fmt(payload.get("room_id")),
        fmt(payload.get("temperature_c"), "°C"),
        fmt(payload.get("humidity_pct"), "% HR"),
        fmt(payload.get("pressure_bar"), " bar"),
        fmt(payload.get("vibration_mm_s"), " mm/s"),
        fmt(payload.get("motor_current_a"), " A"),
        fmt(payload.get("rpm"), " rpm"),
        fmt(payload.get("cycle_count"), " cycles"),
    ]
    labels = [
        "lot",
        "type",
        "fournisseur",
        "état",
        "alarme",
        "zone",
        "salle",
        "temp",
        "humidité",
        "pression",
        "vibration",
        "courant",
        "vitesse",
        "cycle",
    ]
    return " | ".join(f"{label}: {value}" for label, value in zip(labels, parts))


def cold_chain_reading(payload: dict) -> list[str]:
    readings = []
    machine_type = payload.get("machine_type")
    state = payload.get("state")
    alarm_code = payload.get("alarm_code")
    temperature = payload.get("temperature_c")
    vibration = payload.get("vibration_mm_s")

    if machine_type in {"hvac_cold_room", "sensor"} and isinstance(temperature, (int, float)):
        if 2 <= temperature <= 8:
            readings.append("lecture métier: température compatible avec une chaîne du froid 2-8°C")
        elif temperature > 8:
            readings.append("lecture métier: excursion chaude potentielle, lot à contrôler")
        else:
            readings.append("lecture métier: excursion froide potentielle, risque de gel du produit")
    elif isinstance(temperature, (int, float)):
        readings.append("lecture métier: température de procédé ou ambiance machine, hors règle 2-8°C")

    if state == "ALARM" or alarm_code:
        readings.append(f"lecture métier: alarme active ({alarm_code or 'sans code'})")
    if isinstance(vibration, (int, float)) and vibration >= 4:
        readings.append("lecture métier: vibration élevée, signal utile pour maintenance préventive")
    return readings


def print_payload_details(payload_json: str | None, raw_payload: bool = False) -> None:
    payload = read_payload(payload_json)
    if not payload:
        print("      payload: non JSON")
        return

    interesting_fields = [
        "timestamp",
        "site_id",
        "site_label",
        "zone",
        "room_id",
        "latitude",
        "longitude",
        "batch_id",
        "machine_id",
        "machine_type",
        "supplier",
        "state",
        "alarm_code",
        "temperature_c",
        "humidity_pct",
        "pressure_bar",
        "vibration_mm_s",
        "motor_current_a",
        "rpm",
        "cycle_count",
    ]
    for field in interesting_fields:
        print(f"      {field}: {payload.get(field)}")
    for reading in cold_chain_reading(payload):
        print(f"      {reading}")
    if raw_payload:
        print("      payload_json:")
        pretty = json.dumps(payload, ensure_ascii=False, indent=2)
        for line in pretty.splitlines():
            print(f"        {line}")


def payload_stats(conn: sqlite3.Connection) -> dict[str, Counter]:
    stats = {
        "states": Counter(),
        "machine_types": Counter(),
        "suppliers": Counter(),
        "alarms": Counter(),
    }
    rows = conn.execute("SELECT payload_json FROM raw_mqtt_events").fetchall()
    for (payload_json,) in rows:
        payload = read_payload(payload_json)
        if not payload:
            continue
        stats["states"].update([payload.get("state") or "n/a"])
        stats["machine_types"].update([payload.get("machine_type") or "n/a"])
        stats["suppliers"].update([payload.get("supplier") or "n/a"])
        if payload.get("alarm_code"):
            stats["alarms"].update([payload["alarm_code"]])
    return stats


def print_counter(title: str, counter: Counter, limit: int = 8) -> None:
    print(title)
    if not counter:
        print("  - aucun")
        return
    for label, count in counter.most_common(limit):
        print(f"  - {label}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Affiche l'état de la capture MQTT brute.")
    parser.add_argument("--limit", type=int, default=8, help="Nombre de derniers événements à afficher.")
    parser.add_argument("--details", action="store_true", help="Affiche le détail complet du payload JSON.")
    parser.add_argument("--raw-payload", action="store_true", help="Affiche le JSON brut indenté avec --details.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Aucune base trouvée: {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM raw_mqtt_events").fetchone()[0]
    by_class = conn.execute(
        "SELECT classification, COUNT(*) FROM raw_mqtt_events GROUP BY classification ORDER BY COUNT(*) DESC"
    ).fetchall()
    stats = payload_stats(conn)
    last_events = conn.execute(
        """
        SELECT
            received_at_utc,
            broker,
            topic,
            qos,
            retained,
            classification,
            matched_keywords,
            machine_id,
            supplier,
            payload_text,
            payload_json,
            raw_hash
        FROM raw_mqtt_events
        ORDER BY id DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    print(f"Base brute: {DB_PATH}")
    print(f"Messages stockés: {total}")
    print("Par classification:")
    for classification, count in by_class:
        print(f"  - {classification}: {count}")
    print_counter("Par état machine:", stats["states"])
    print_counter("Par type de machine:", stats["machine_types"])
    print_counter("Par fournisseur:", stats["suppliers"])
    print_counter("Alarmes détectées:", stats["alarms"])
    print("Derniers événements:")
    for (
        received_at,
        broker,
        topic,
        qos,
        retained,
        classification,
        matched_keywords,
        machine_id,
        supplier,
        payload_text,
        payload_json,
        raw_hash,
    ) in last_events:
        print(f"  - {received_at} | {topic} | {classification} | {machine_id}")
        print(f"    {summarize_payload(payload_json, supplier)}")
        if args.details:
            payload_size = len(payload_text.encode("utf-8")) if payload_text else 0
            print(f"      broker: {broker}")
            print(f"      qos: {qos}")
            print(f"      retained: {retained}")
            print(f"      payload_size_bytes: {payload_size}")
            print(f"      matched_keywords: {matched_keywords}")
            print(f"      raw_hash_sha256: {raw_hash}")
            print_payload_details(payload_json, raw_payload=args.raw_payload)
    conn.close()


if __name__ == "__main__":
    main()
