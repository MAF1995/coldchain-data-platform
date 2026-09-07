import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from airflow.sdk import dag, task


PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", "/opt/airflow/project"))
DBT_PROJECT = PROJECT_ROOT / "dbt"
EVIDENCE_PATH = PROJECT_ROOT / "data" / "processed" / "airflow_last_run.json"


def postgres_connection_string() -> str:
    return (
        f"host={os.getenv('PGHOST', 'postgres')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )


def run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.stdout


def dbt_command(name: str) -> str:
    return run_command(
        [
            "dbt",
            name,
            "--project-dir",
            str(DBT_PROJECT),
            "--profiles-dir",
            str(DBT_PROJECT),
            "--no-use-colors",
        ]
    )


@dag(
    dag_id="pharma_cold_chain_daily",
    description="Qualification quotidienne des signaux de chaîne du froid.",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["pharma", "cold-chain", "dbt", "quality"],
)
def cold_chain_daily():
    @task
    def check_raw_source() -> int:
        with psycopg.connect(postgres_connection_string()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM raw.mqtt_sensor_event")
                raw_count = cursor.fetchone()[0]
        if raw_count == 0:
            raise ValueError("La source raw.mqtt_sensor_event est vide")
        print(f"Source disponible: {raw_count} événements bruts")
        return raw_count

    @task
    def seed_references(_raw_count: int) -> str:
        return dbt_command("seed")

    @task
    def build_models(_seed_output: str) -> str:
        return dbt_command("run")

    @task
    def test_models(_run_output: str) -> str:
        return dbt_command("test")

    @task
    def quality_gate(_test_output: str, raw_count: int) -> dict:
        query = """
            SELECT
                (SELECT COUNT(*) FROM analytics.fct_sensor_reading) AS fact_count,
                (SELECT COUNT(*) FROM analytics.mart_quality_daily) AS mart_count,
                (SELECT COUNT(*) FROM analytics.fct_temperature_excursion) AS excursion_count
        """
        with psycopg.connect(postgres_connection_string()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                fact_count, mart_count, excursion_count = cursor.fetchone()

        if fact_count != raw_count:
            raise ValueError(
                f"Écart de complétude: raw={raw_count}, fact={fact_count}"
            )
        if mart_count == 0:
            raise ValueError("Le mart qualité est vide")

        evidence = {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "raw_event_count": raw_count,
            "fact_event_count": fact_count,
            "quality_mart_row_count": mart_count,
            "temperature_excursion_count": excursion_count,
            "quality_gate": "PASSED",
        }
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return evidence

    @task
    def publish_evidence(evidence: dict) -> str:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Preuve d'exécution écrite dans {EVIDENCE_PATH}")
        return str(EVIDENCE_PATH)

    raw_count = check_raw_source()
    seed_output = seed_references(raw_count)
    run_output = build_models(seed_output)
    test_output = test_models(run_output)
    evidence = quality_gate(test_output, raw_count)
    publish_evidence(evidence)


cold_chain_daily()
