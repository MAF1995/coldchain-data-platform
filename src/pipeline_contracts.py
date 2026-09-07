import hashlib
import json


def message_hash(topic: str, payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(topic.encode("utf-8"))
    digest.update(b"\0")
    digest.update(payload)
    return digest.hexdigest()


def source_event_id(partition: int, offset: int) -> int:
    if partition < 0 or offset < 0:
        raise ValueError("partition et offset doivent être positifs")
    return -((partition + 1) * 1_000_000_000_000 + offset + 1)


def validate_envelope(envelope: dict) -> None:
    required = {"raw_hash", "received_at", "mqtt_topic", "payload"}
    if not isinstance(envelope, dict) or not required.issubset(envelope):
        raise ValueError("enveloppe Kafka incomplète")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload non objet")
    if not {"timestamp", "machine_id", "machine_type"}.issubset(payload):
        raise ValueError("champs métier obligatoires absents")


def normalized_event(envelope: dict, partition: int, offset: int) -> dict:
    validate_envelope(envelope)
    payload = envelope["payload"]
    return {
        "raw_hash": envelope["raw_hash"],
        "source_event_id": source_event_id(partition, offset),
        "event_time": payload["timestamp"],
        "received_at": envelope["received_at"],
        "broker_alias": envelope.get("broker_alias", "mqtt-edge-042"),
        "topic": envelope["mqtt_topic"],
        "qos": envelope.get("mqtt_qos", 0),
        "retained": envelope.get("mqtt_retained", False),
        "classification": "production_machine_signal",
        "machine_id": payload["machine_id"],
        "machine_type": payload["machine_type"],
        "supplier": payload.get("supplier"),
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
