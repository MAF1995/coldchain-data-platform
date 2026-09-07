import argparse
import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


MACHINES = [
    {
        "machine_id": "LYO_01",
        "machine_type": "lyophilizer",
        "supplier": "GEA",
        "zone": "Bâtiment A - lyophilisation",
        "room_id": "A-120",
        "latitude": 45.70482,
        "longitude": 4.88805,
    },
    {
        "machine_id": "FILL_02",
        "machine_type": "filling_line",
        "supplier": "Syntegon",
        "zone": "Bâtiment A - remplissage aseptique",
        "room_id": "A-135",
        "latitude": 45.70455,
        "longitude": 4.88842,
    },
    {
        "machine_id": "AUTO_03",
        "machine_type": "autoclave",
        "supplier": "Getinge",
        "zone": "Bâtiment B - stérilisation",
        "room_id": "B-020",
        "latitude": 45.70420,
        "longitude": 4.88764,
    },
    {
        "machine_id": "HVAC_CR_04",
        "machine_type": "hvac_cold_room",
        "supplier": "Siemens",
        "zone": "Chambre froide qualifiée",
        "room_id": "CF-008",
        "latitude": 45.70493,
        "longitude": 4.88731,
    },
    {
        "machine_id": "COMP_05",
        "machine_type": "compressor",
        "supplier": "ABB",
        "zone": "Local utilités",
        "room_id": "U-014",
        "latitude": 45.70396,
        "longitude": 4.88710,
    },
    {
        "machine_id": "SENSOR_06",
        "machine_type": "sensor",
        "supplier": "Endress+Hauser",
        "zone": "Quai expédition froid",
        "room_id": "QF-002",
        "latitude": 45.70518,
        "longitude": 4.88772,
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_payload(machine: dict) -> dict:
    temp_base = 5.0 if machine["machine_type"] in {"hvac_cold_room", "sensor"} else 21.0
    state = random.choices(["RUNNING", "IDLE", "ALARM"], weights=[0.78, 0.18, 0.04], k=1)[0]
    temp = temp_base + random.uniform(-1.5, 1.8)
    if state == "ALARM" and machine["machine_type"] in {"hvac_cold_room", "sensor"}:
        temp += random.choice([4.5, -4.0])

    return {
        "timestamp": utc_now(),
        "site_id": "042",
        "site_label": "042",
        "machine_id": machine["machine_id"],
        "machine_type": machine["machine_type"],
        "supplier": machine["supplier"],
        "zone": machine["zone"],
        "room_id": machine["room_id"],
        "latitude": machine["latitude"],
        "longitude": machine["longitude"],
        "batch_id": random.choice(["LOT-INS-2026-0018", "LOT-VAC-2026-0041", "LOT-REA-2026-0007"]),
        "temperature_c": round(temp, 2),
        "humidity_pct": round(random.uniform(42, 68), 1),
        "pressure_bar": round(random.uniform(1.0, 2.8), 2),
        "vibration_mm_s": round(random.uniform(0.2, 4.5), 2),
        "motor_current_a": round(random.uniform(1.0, 12.0), 2),
        "rpm": random.randint(0, 1450),
        "cycle_count": random.randint(1000, 45000),
        "state": state,
        "alarm_code": "TEMP_EXCURSION" if state == "ALARM" else None,
    }


def format_payload_summary(payload: dict) -> str:
    return (
        f"site={payload['site_id']} | {payload['machine_id']} | {payload['machine_type']} | {payload['supplier']} | "
        f"room={payload['room_id']} | zone={payload['zone']} | "
        f"lat={payload['latitude']:.5f} lon={payload['longitude']:.5f} | "
        f"lot={payload['batch_id']} | état={payload['state']} | "
        f"temp={payload['temperature_c']}°C | humidité={payload['humidity_pct']}%"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publie des signaux machines pharma anonymisés.")
    parser.add_argument("--broker", default="test.mosquitto.org")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--duration-seconds", type=int, default=7200)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--topic-prefix", default="pharma/production/site-042")
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()
    deadline = time.monotonic() + args.duration_seconds
    count = 0
    try:
        while time.monotonic() < deadline:
            machine = random.choice(MACHINES)
            payload = build_payload(machine)
            topic = f"{args.topic_prefix}/{machine['machine_type']}/{machine['machine_id']}"
            client.publish(topic, json.dumps(payload), qos=1)
            count += 1
            print(f"[{utc_now()}] published {topic}", flush=True)
            print(f"  {format_payload_summary(payload)}", flush=True)
            time.sleep(args.interval_seconds)
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"[{utc_now()}] publication terminée: {count} messages", flush=True)


if __name__ == "__main__":
    main()
