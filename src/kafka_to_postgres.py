import json
import logging
import os
import signal
import time

import psycopg
from confluent_kafka import Consumer, KafkaException, Producer, TopicPartition
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from load_raw_to_postgres import CREATE_TABLE_SQL, INSERT_SQL
from pipeline_contracts import normalized_event, validate_envelope


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("kafka_to_postgres")

CONSUMED = Counter(
    "pipeline_kafka_messages_consumed_total",
    "Messages lus depuis Kafka.",
)
INSERTED = Counter(
    "pipeline_postgres_rows_inserted_total",
    "Lignes insérées dans PostgreSQL.",
)
DUPLICATES = Counter(
    "pipeline_postgres_duplicates_total",
    "Messages déjà présents grâce à la clé idempotente.",
)
DLQ_MESSAGES = Counter(
    "pipeline_dlq_messages_total",
    "Messages envoyés dans la file de rejet.",
    ["reason"],
)
PROCESSING_ERRORS = Counter(
    "pipeline_consumer_errors_total",
    "Erreurs du consommateur Kafka/PostgreSQL.",
    ["stage"],
)
PROCESSING_SECONDS = Histogram(
    "pipeline_message_processing_seconds",
    "Durée de traitement d'un message Kafka.",
)
CONSUMER_LAG = Gauge(
    "pipeline_kafka_consumer_lag",
    "Retard estimé du groupe consommateur.",
    ["topic", "partition"],
)
LAST_EVENT = Gauge(
    "pipeline_last_event_timestamp_seconds",
    "Horodatage Unix du dernier événement consommé.",
    ["component"],
)


def postgres_connection_string() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '55432')} "
        f"dbname={os.getenv('PGDATABASE', 'pharma_analytics')} "
        f"user={os.getenv('PGUSER', 'pharma_data')} "
        f"password={os.getenv('PGPASSWORD', 'pharma_local_only')}"
    )


def connect_postgres() -> psycopg.Connection:
    for attempt in range(1, 31):
        try:
            connection = psycopg.connect(postgres_connection_string())
            with connection.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)
            connection.commit()
            return connection
        except psycopg.Error as error:
            LOGGER.warning("PostgreSQL indisponible (%s/30): %s", attempt, error)
            time.sleep(2)
    raise RuntimeError("PostgreSQL indisponible après 60 secondes")


def publish_dlq(producer: Producer, topic: str, message, reason: str) -> None:
    record = {
        "reason": reason,
        "source_topic": message.topic(),
        "source_partition": message.partition(),
        "source_offset": message.offset(),
        "value": message.value().decode("utf-8", errors="replace"),
    }
    producer.produce(topic, value=json.dumps(record, ensure_ascii=False).encode("utf-8"))
    producer.flush(5)
    DLQ_MESSAGES.labels(reason=reason).inc()


def update_lag(consumer: Consumer, message) -> None:
    partition = TopicPartition(message.topic(), message.partition())
    try:
        _low, high = consumer.get_watermark_offsets(partition, timeout=2, cached=False)
    except KafkaException as error:
        LOGGER.warning("Retard Kafka indisponible temporairement: %s", error)
        return
    lag = max(0, high - message.offset() - 1)
    CONSUMER_LAG.labels(topic=message.topic(), partition=str(message.partition())).set(lag)


def main() -> None:
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    raw_topic = os.getenv("KAFKA_RAW_TOPIC", "pharma.sensor.raw.v1")
    dlq_topic = os.getenv("KAFKA_DLQ_TOPIC", "pharma.sensor.dlq.v1")
    consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "pharma-postgres-raw-v1")
    metrics_port = int(os.getenv("METRICS_PORT", "9109"))
    running = True

    consumer = Consumer(
        {
            "bootstrap.servers": kafka_servers,
            "group.id": consumer_group,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "client.id": "postgres-raw-writer-042",
        }
    )
    dlq_producer = Producer({"bootstrap.servers": kafka_servers, "acks": "all"})
    connection = connect_postgres()

    def stop(*_args) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    start_http_server(metrics_port)
    consumer.subscribe([raw_topic])
    LOGGER.info("Consommateur démarré: topic=%s group=%s", raw_topic, consumer_group)

    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                PROCESSING_ERRORS.labels(stage="kafka_poll").inc()
                LOGGER.error("Erreur Kafka: %s", message.error())
                continue

            CONSUMED.inc()
            with PROCESSING_SECONDS.time():
                try:
                    envelope = json.loads(message.value().decode("utf-8"))
                    validate_envelope(envelope)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                    publish_dlq(dlq_producer, dlq_topic, message, "validation")
                    consumer.commit(message=message, asynchronous=False)
                    LOGGER.warning("Message rejeté: %s", error)
                    continue

                try:
                    event = normalized_event(envelope, message.partition(), message.offset())
                    with connection.cursor() as cursor:
                        cursor.execute(INSERT_SQL, event)
                        inserted = cursor.rowcount
                    connection.commit()
                    if inserted:
                        INSERTED.inc()
                    else:
                        DUPLICATES.inc()
                    consumer.commit(message=message, asynchronous=False)
                    update_lag(consumer, message)
                    LAST_EVENT.labels(component="kafka_postgres_consumer").set_to_current_time()
                    LOGGER.info(
                        "Traité topic=%s partition=%s offset=%s machine=%s inserted=%s",
                        message.topic(),
                        message.partition(),
                        message.offset(),
                        event["machine_id"],
                        inserted,
                    )
                except psycopg.Error as error:
                    connection.rollback()
                    PROCESSING_ERRORS.labels(stage="postgres").inc()
                    LOGGER.error("Écriture PostgreSQL échouée: %s", error)
                    time.sleep(2)
    finally:
        connection.close()
        consumer.close()
        dlq_producer.flush(5)
        LOGGER.info("Consommateur arrêté")


if __name__ == "__main__":
    main()
