import argparse
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "platform_validation.json"


def get_json(url: str, username: str | None = None, password: str | None = None):
    request = Request(url)
    if username and password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def prometheus_value(base_url: str, query: str) -> float | None:
    from urllib.parse import urlencode

    response = get_json(f"{base_url}/api/v1/query?{urlencode({'query': query})}")
    results = response["data"]["result"]
    return float(results[0]["value"][1]) if results else None


def postgres_counts() -> dict:
    connection_string = (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '55432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )
    queries = {
        "raw_event_count": "select count(*) from raw.mqtt_sensor_event",
        "fact_event_count": "select count(*) from analytics.fct_sensor_reading",
        "quality_mart_row_count": "select count(*) from analytics.mart_quality_daily",
    }
    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            counts = {}
            for name, query in queries.items():
                cursor.execute(query)
                counts[name] = cursor.fetchone()[0]
    return counts


def collect() -> dict:
    prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3002")
    targets = get_json(f"{prometheus_url}/api/v1/targets")["data"]["activeTargets"]
    target_health = {
        target["labels"].get("job", "unknown"): target["health"] for target in targets
    }
    dashboard = get_json(
        f"{grafana_url}/api/dashboards/uid/pharma-coldchain-pipeline",
        os.getenv("GRAFANA_USER", "admin"),
        os.getenv("GRAFANA_PASSWORD", "pharma_admin_local_only"),
    )
    metrics = {
        "mqtt_received_total": prometheus_value(
            prometheus_url, "sum(pipeline_mqtt_messages_received_total)"
        ),
        "kafka_published_total": prometheus_value(
            prometheus_url, "sum(pipeline_kafka_messages_published_total)"
        ),
        "postgres_inserted_total": prometheus_value(
            prometheus_url, "sum(pipeline_postgres_rows_inserted_total)"
        ),
        "consumer_lag_max": prometheus_value(
            prometheus_url, "max(pipeline_kafka_consumer_lag)"
        ),
    }
    required_targets = {
        "prometheus",
        "mqtt-kafka-bridge",
        "kafka-postgres-consumer",
    }
    checks = {
        "all_required_targets_up": all(
            target_health.get(name) == "up" for name in required_targets
        ),
        "consumer_lag_under_100": (
            metrics["consumer_lag_max"] is not None
            and metrics["consumer_lag_max"] < 100
        ),
        "dashboard_provisioned": dashboard["dashboard"]["uid"]
        == "pharma-coldchain-pipeline",
    }
    return {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "postgres": postgres_counts(),
        "prometheus_targets": target_health,
        "pipeline_metrics": metrics,
        "grafana_dashboard": {
            "uid": dashboard["dashboard"]["uid"],
            "title": dashboard["dashboard"]["title"],
            "version": dashboard["dashboard"]["version"],
            "url": dashboard["meta"]["url"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte les preuves de santé de la plateforme.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASSED" else 1)


if __name__ == "__main__":
    main()
