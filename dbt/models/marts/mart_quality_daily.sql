select
    date_trunc('day', event_time)::date as observation_date,
    zone,
    room_id,
    count(*) filter (where temperature_rule_eligible) as eligible_reading_count,
    count(*) filter (where temperature_status = 'OK') as compliant_reading_count,
    count(*) filter (where temperature_status = 'TOO_COLD') as too_cold_reading_count,
    count(*) filter (where temperature_status = 'TOO_HOT') as too_hot_reading_count,
    round(
        100.0
        * count(*) filter (where temperature_status = 'OK')
        / nullif(count(*) filter (where temperature_rule_eligible), 0),
        2
    ) as temperature_compliance_rate_pct,
    round(avg(temperature_c) filter (where temperature_rule_eligible), 2)
        as average_temperature_c,
    round(max(temperature_deviation_c), 2) as maximum_deviation_c,
    round(avg(ingestion_delay_seconds), 3) as average_ingestion_delay_seconds
from {{ ref('int_temperature_status') }}
where temperature_rule_eligible
group by observation_date, zone, room_id

