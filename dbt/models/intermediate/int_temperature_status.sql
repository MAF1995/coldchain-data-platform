with events as (
    select *
    from {{ ref('stg_sensor_events') }}
),

rules as (
    select
        machine_type,
        measurement_context,
        threshold_min_c,
        threshold_max_c,
        temperature_rule_eligible,
        expected_interval_seconds
    from {{ ref('measurement_rules') }}
)

select
    events.*,
    rules.measurement_context,
    rules.threshold_min_c,
    rules.threshold_max_c,
    coalesce(rules.temperature_rule_eligible, false) as temperature_rule_eligible,
    rules.expected_interval_seconds,
    case
        when not coalesce(rules.temperature_rule_eligible, false)
            then 'NOT_APPLICABLE'
        when events.temperature_c < rules.threshold_min_c
            then 'TOO_COLD'
        when events.temperature_c > rules.threshold_max_c
            then 'TOO_HOT'
        else 'OK'
    end as temperature_status,
    case
        when not coalesce(rules.temperature_rule_eligible, false)
            then null
        when events.temperature_c < rules.threshold_min_c
            then rules.threshold_min_c - events.temperature_c
        when events.temperature_c > rules.threshold_max_c
            then events.temperature_c - rules.threshold_max_c
        else 0
    end as temperature_deviation_c
from events
left join rules using (machine_type)

