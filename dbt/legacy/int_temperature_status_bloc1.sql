-- Version conservée comme trace du modèle présenté dans le bloc I.
-- Le modèle exécutable du bloc II se trouve dans models/intermediate.
SELECT
    e.event_time,
    e.sensor_id,
    e.batch_id,
    b.product_code,
    e.temperature_c,
    p.temp_min_c,
    p.temp_max_c,
    CASE
        WHEN e.temperature_c < p.temp_min_c THEN 'TOO_COLD'
        WHEN e.temperature_c > p.temp_max_c THEN 'TOO_HOT'
        ELSE 'OK'
    END AS temperature_status
FROM {{ ref('stg_sensor_event') }} e
JOIN {{ ref('stg_batch') }} b ON b.batch_id = e.batch_id
JOIN {{ ref('stg_product') }} p ON p.product_code = b.product_code
