import json
from pathlib import Path


PRODUCT_THRESHOLDS = {
    "LOT-INS-2026-0018": {"product_code": "INSULINE-X", "temp_min_c": 2.0, "temp_max_c": 8.0},
    "LOT-VAC-2026-0041": {"product_code": "VACCIN-A", "temp_min_c": 2.0, "temp_max_c": 8.0},
}


def classify_temperature(event: dict, thresholds: dict) -> str:
    temp = float(event["temperature_c"])
    min_c = float(thresholds["temp_min_c"])
    max_c = float(thresholds["temp_max_c"])

    if temp < min_c:
        return "TOO_COLD"
    if temp > max_c:
        return "TOO_HOT"
    return "OK"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sample_file = project_root / "data" / "sample" / "sensor_events.jsonl"

    print("Replay des mesures capteurs - chaîne du froid pharma")
    print(f"Source: {sample_file}")
    print("-" * 72)

    for line in sample_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        thresholds = PRODUCT_THRESHOLDS[event["batch_id"]]
        status = classify_temperature(event, thresholds)
        print(
            f"{event['timestamp']} | {event['batch_id']} | "
            f"{event['sensor_id']} | {event['temperature_c']}°C | {status}"
        )


if __name__ == "__main__":
    main()
