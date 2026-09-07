from src.collect_open_meteo import build_record
from src.load_open_meteo_to_postgres import to_row


def test_open_meteo_record_is_traceable_and_loadable():
    payload = {
        "latitude": 45.70482,
        "longitude": 4.88772,
        "current": {
            "time": "2026-09-07T12:00",
            "temperature_2m": 20.5,
            "relative_humidity_2m": 55,
            "weather_code": 1,
            "wind_speed_10m": 8.4,
        },
    }

    record = build_record(
        payload,
        source_url="https://api.open-meteo.com/v1/forecast?latitude=45.70482",
        site_id="042",
        latitude=45.70482,
        longitude=4.88772,
        fetched_at="2026-09-07T12:00:00+00:00",
    )
    row = to_row(record)

    assert len(record["payload_hash"]) == 64
    assert row["site_id"] == "042"
    assert row["temperature_c"] == 20.5
    assert row["relative_humidity_pct"] == 55
