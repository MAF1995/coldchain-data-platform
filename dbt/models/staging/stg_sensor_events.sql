with source as (
    select *
    from {{ source('raw', 'mqtt_sensor_event') }}
)

select
    source_event_id,
    raw_hash,
    event_time,
    received_at,
    loaded_at,
    topic,
    broker_alias,
    machine_id,
    machine_type,
    supplier,
    site_id,
    zone,
    room_id,
    batch_id,
    temperature_c,
    humidity_pct,
    pressure_bar,
    vibration_mm_s,
    motor_current_a,
    rpm,
    cycle_count,
    upper(state) as state,
    nullif(upper(alarm_code), '') as alarm_code,
    extract(epoch from (received_at - event_time)) as ingestion_delay_seconds
from source
where event_time is not null
  and machine_id is not null

