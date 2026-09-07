select
    batch_id,
    min(excursion_started_at) as first_excursion_at,
    max(excursion_ended_at) as last_excursion_at,
    count(*) as excursion_count,
    sum(observed_duration_minutes) as observed_excursion_duration_minutes,
    sum(excursion_degree_minutes) as excursion_degree_minutes,
    max(maximum_deviation_c) as maximum_deviation_c,
    true as has_confirmed_excursion
from {{ ref('fct_temperature_excursion') }}
where batch_id is not null
  and is_confirmed
group by batch_id
