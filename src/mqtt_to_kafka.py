import json
import logging
import os
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from confluent_kafka import Producer
from prometheus_client import Counter, Gauge, start_http_server

from pipeline_contracts import message_hash


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("mqtt_to_kafka")

MESSAGES_RECEIVED = Counter(
    "pipeline_mqtt_messages_received_total",
    "Messages reçus depuis MQTT.",
)
MESSAGES_PUBLISHED = Counter(
    "pipeline_kafka_messages_published_total",
    "Messages confirmés par Kafka.",
)
MESSAGES_REJECTED = Counter(
    "pipeline_bridge_messages_rejected_total",
    "Messages refusés avant publication Kafka.",
    ["reason"],
)
DELIVERY_ERRORS = Counter(
    "pipeline_kafka_delivery_errors_total",
    "Erreurs de livraison du producteur Kafka.",
)
LAST_EVENT = Gauge(
    "pipeline_last_event_timestamp_seconds",
    "Horodatage Unix du dernier événement MQTT valide.",
    ["component"],
)

REQUIRED_FIELDS = {"timestamp", "machine_id", "machine_type"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    mqtt_host = os.getenv("MQTT_HOST", "localhost")
    mqtt_port = int(os.getenv("MQTT_PORT", "1884"))
    mqtt_topic = os.getenv("MQTT_TOPIC", "pharma/production/site-042/#")
    broker_alias = os.getenv("MQTT_BROKER_ALIAS", "mqtt-edge-042")
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    kafka_topic = os.getenv("KAFKA_RAW_TOPIC", "pharma.sensor.raw.v1")
    metrics_port = int(os.getenv("METRICS_PORT", "9108"))

    running = True
    producer = Producer(
        {
            "bootstrap.servers": kafka_servers,
            "client.id": "mqtt-kafka-bridge-042",
            "enable.idempotence": True,
            "acks": "all",
            "compression.type": "zstd",
        }
    )

    def stop(*_args) -> None:
        nonlocal running
        running = False

    def delivery_report(error, _message) -> None:
        if error:
            DELIVERY_ERRORS.inc()
            LOGGER.error("Échec de livraison Kafka: %s", error)
            return
        MESSAGES_PUBLISHED.inc()

    def on_connect(client, _userdata, _flags, reason_code, _properties=None) -> None:
        if reason_code != 0:
            LOGGER.error("Connexion MQTT refusée: reason=%s", reason_code)
            return
        client.subscribe(mqtt_topic, qos=1)
        LOGGER.info("Écoute MQTT active: %s:%s topic=%s", mqtt_host, mqtt_port, mqtt_topic)

    def on_message(_client, _userdata, message) -> None:
        MESSAGES_RECEIVED.inc()
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            MESSAGES_REJECTED.labels(reason="invalid_json").inc()
            return

        if not isinstance(payload, dict) or not REQUIRED_FIELDS.issubset(payload):
            MESSAGES_REJECTED.labels(reason="missing_required_field").inc()
            return

        envelope = {
            "schema_version": 1,
            "received_at": utc_now(),
            "broker_alias": broker_alias,
            "mqtt_topic": message.topic,
            "mqtt_qos": message.qos,
            "mqtt_retained": bool(message.retain),
            "raw_hash": message_hash(message.topic, message.payload),
            "payload": payload,
        }
        producer.produce(
            kafka_topic,
            key=str(payload["machine_id"]).encode("utf-8"),
            value=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
            on_delivery=delivery_report,
        )
        producer.poll(0)
        LAST_EVENT.labels(component="mqtt_kafka_bridge").set_to_current_time()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    start_http_server(metrics_port)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_host, mqtt_port, keepalive=60)
    client.loop_start()
    LOGGER.info("Passerelle démarrée: Kafka=%s topic=%s", kafka_servers, kafka_topic)

    try:
        while running:
            producer.poll(0.2)
            time.sleep(0.2)
    finally:
        client.loop_stop()
        client.disconnect()
        remaining = producer.flush(10)
        LOGGER.info("Passerelle arrêtée: messages Kafka non livrés=%s", remaining)


if __name__ == "__main__":
    main()
