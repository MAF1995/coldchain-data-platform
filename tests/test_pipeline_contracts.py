import json

import pytest

from pipeline_contracts import (
    message_hash,
    normalized_event,
    source_event_id,
    validate_envelope,
)


@pytest.fixture
def valid_envelope():
    return {
        "raw_hash": "a" * 64,
        "received_at": "2026-08-24T12:00:01+00:00",
        "broker_alias": "mqtt-edge-042",
        "mqtt_topic": "pharma/production/site-042/sensor/SENSOR_06",
        "mqtt_qos": 1,
        "mqtt_retained": False,
        "payload": {
            "timestamp": "2026-08-24T12:00:00+00:00",
            "site_id": "042",
            "zone": "Quai expédition froid",
            "room_id": "QF-002",
            "machine_id": "SENSOR_06",
            "machine_type": "sensor",
            "temperature_c": 5.2,
            "state": "RUNNING",
        },
    }


def test_message_hash_is_stable_and_topic_sensitive():
    payload = b'{"temperature_c":5.2}'
    first = message_hash("site-042/sensor", payload)
    second = message_hash("site-042/sensor", payload)

    assert first == second
    assert len(first) == 64
    assert first != message_hash("site-042/hvac", payload)


def test_source_event_id_is_negative_and_unique_by_partition_offset():
    identifiers = {
        source_event_id(partition, offset)
        for partition in range(3)
        for offset in range(4)
    }

    assert len(identifiers) == 12
    assert all(identifier < 0 for identifier in identifiers)


@pytest.mark.parametrize("partition,offset", [(-1, 0), (0, -1)])
def test_source_event_id_rejects_invalid_coordinates(partition, offset):
    with pytest.raises(ValueError):
        source_event_id(partition, offset)


def test_validate_envelope_accepts_complete_contract(valid_envelope):
    validate_envelope(valid_envelope)


@pytest.mark.parametrize(
    "invalid_envelope",
    [
        {},
        {"raw_hash": "x", "received_at": "now", "mqtt_topic": "t", "payload": []},
        {
            "raw_hash": "x",
            "received_at": "now",
            "mqtt_topic": "t",
            "payload": {"timestamp": "now", "machine_id": "SENSOR_06"},
        },
    ],
)
def test_validate_envelope_rejects_incomplete_contract(invalid_envelope):
    with pytest.raises(ValueError):
        validate_envelope(invalid_envelope)


def test_normalized_event_preserves_traceability(valid_envelope):
    event = normalized_event(valid_envelope, partition=2, offset=17)

    assert event["source_event_id"] == -3_000_000_000_018
    assert event["machine_id"] == "SENSOR_06"
    assert event["site_id"] == "042"
    assert event["room_id"] == "QF-002"
    assert event["temperature_c"] == 5.2
    assert json.loads(event["payload_json"])["zone"] == "Quai expédition froid"
