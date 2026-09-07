import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, functions as F, types as T


INPUT_PATH = "/opt/spark/data/raw/sensor_events.jsonl"
OUTPUT_PATH = "/opt/spark/data/curated/quality_daily_parquet"
EVIDENCE_PATH = Path("/opt/spark/data/evidence/spark_last_run.json")


SCHEMA = T.StructType(
    [
        T.StructField("timestamp", T.StringType(), False),
        T.StructField("site_id", T.StringType(), True),
        T.StructField("machine_id", T.StringType(), False),
        T.StructField("machine_type", T.StringType(), False),
        T.StructField("zone", T.StringType(), True),
        T.StructField("room_id", T.StringType(), True),
        T.StructField("batch_id", T.StringType(), True),
        T.StructField("temperature_c", T.DoubleType(), True),
        T.StructField("humidity_pct", T.DoubleType(), True),
        T.StructField("state", T.StringType(), True),
        T.StructField("alarm_code", T.StringType(), True),
    ]
)


def main() -> None:
    spark = (
        SparkSession.builder.appName("pharma-cold-chain-distributed-metrics")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = spark.read.schema(SCHEMA).json(INPUT_PATH).repartition(4, "machine_id")
    typed = raw.withColumn("event_time", F.to_timestamp("timestamp"))
    eligible = typed.filter(
        F.col("machine_type").isin("hvac_cold_room", "sensor")
        & F.col("temperature_c").isNotNull()
    )
    qualified = (
        eligible.withColumn("threshold_min_c", F.lit(2.0))
        .withColumn("threshold_max_c", F.lit(8.0))
        .withColumn(
            "temperature_status",
            F.when(F.col("temperature_c") < 2.0, F.lit("TOO_COLD"))
            .when(F.col("temperature_c") > 8.0, F.lit("TOO_HOT"))
            .otherwise(F.lit("OK")),
        )
        .withColumn(
            "temperature_deviation_c",
            F.when(F.col("temperature_c") < 2.0, 2.0 - F.col("temperature_c"))
            .when(F.col("temperature_c") > 8.0, F.col("temperature_c") - 8.0)
            .otherwise(F.lit(0.0)),
        )
    )

    daily = (
        qualified.withColumn("observation_date", F.to_date("event_time"))
        .groupBy("observation_date", "site_id", "zone", "room_id")
        .agg(
            F.count("*").alias("eligible_reading_count"),
            F.sum(F.when(F.col("temperature_status") == "OK", 1).otherwise(0)).alias(
                "compliant_reading_count"
            ),
            F.sum(
                F.when(F.col("temperature_status") == "TOO_COLD", 1).otherwise(0)
            ).alias("too_cold_reading_count"),
            F.sum(
                F.when(F.col("temperature_status") == "TOO_HOT", 1).otherwise(0)
            ).alias("too_hot_reading_count"),
            F.round(F.avg("temperature_c"), 3).alias("average_temperature_c"),
            F.round(F.max("temperature_deviation_c"), 3).alias("maximum_deviation_c"),
        )
        .withColumn(
            "temperature_compliance_rate_pct",
            F.round(
                F.col("compliant_reading_count")
                / F.col("eligible_reading_count")
                * 100,
                2,
            ),
        )
        .orderBy("observation_date", "room_id")
    )

    daily.write.mode("overwrite").partitionBy("observation_date").parquet(OUTPUT_PATH)
    rows = [row.asDict(recursive=True) for row in daily.collect()]
    evidence = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "spark_version": spark.version,
        "spark_master": spark.sparkContext.master,
        "default_parallelism": spark.sparkContext.defaultParallelism,
        "raw_event_count": raw.count(),
        "eligible_event_count": qualified.count(),
        "output_row_count": len(rows),
        "output_path": OUTPUT_PATH,
        "status": "PASSED",
        "sample": rows[:5],
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    daily.show(50, truncate=False)
    print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
    spark.stop()


if __name__ == "__main__":
    main()
