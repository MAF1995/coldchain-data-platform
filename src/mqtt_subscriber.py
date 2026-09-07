import json
import hashlib
import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker.internal")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "pharma/production/site-042/#")


def build_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_raw_event(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False))


def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode("utf-8"))
    event = {
        "topic": msg.topic,
        "sensor_id": payload["sensor_id"],
        "batch_id": payload["batch_id"],
        "timestamp": payload["timestamp"],
        "temperature_c": float(payload["temperature_c"]),
        "humidity_pct": payload.get("humidity_pct"),
        "battery_pct": payload.get("battery_pct"),
        "raw_hash": build_hash(payload),
        "raw_payload": payload,
    }
    write_raw_event(event)


def main() -> None:
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.subscribe(TOPIC, qos=1)
    client.loop_forever()


if __name__ == "__main__":
    main()
