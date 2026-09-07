with eligible_readings as (
    select
        *,
        temperature_status in ('TOO_COLD', 'TOO_HOT') as is_excursion,
        lag(temperature_status in ('TOO_COLD', 'TOO_HOT')) over (
            partition by machine_id
            order by event_time
        ) as previous_is_excursion,
        lag(event_time) over (
            partition by machine_id
            order by event_time
        ) as previous_event_time,
        lead(event_time) over (
            partition by machine_id
            order by event_time
        ) as next_event_time
    from {{ ref('int_temperature_status') }}
    where temperature_rule_eligible
),

segmented as (
    select
        *,
        case
            when is_excursion
             and (
                not coalesce(previous_is_excursion, false)
                or event_time - previous_event_time > interval '5 minutes'
             )
                then 1
            else 0
        end as new_excursion
    from eligible_readings
),

numbered as (
    select
        *,
        least(
            coalesce(
                extract(epoch from (next_event_time - event_time)),
                expected_interval_seconds
            ),
            expected_interval_seconds
        ) / 60.0 as represented_duration_minutes,
        sum(new_excursion) over (
            partition by machine_id
            order by event_time
            rows between unbounded preceding and current row
        ) as excursion_number
    from segmented
)

select
    machine_id,
    zone,
    room_id,
    batch_id,
    excursion_number,
    min(event_time) as excursion_started_at,
    max(event_time) as excursion_ended_at,
    extract(epoch from (max(event_time) - min(event_time))) / 60.0
        as observed_duration_minutes,
    count(*) as reading_count,
    (
        count(*) >= 2
        or bool_or(alarm_code = 'TEMP_EXCURSION')
    ) as is_confirmed,
    max(temperature_deviation_c) as maximum_deviation_c,
    sum(temperature_deviation_c * represented_duration_minutes)
        as excursion_degree_minutes,
    min(temperature_c) as minimum_temperature_c,
    max(temperature_c) as maximum_temperature_c
from numbered
where is_excursion
group by machine_id, zone, room_id, batch_id, excursion_number
