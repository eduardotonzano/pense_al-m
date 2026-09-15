import json

import pytest

from debenture_search.config import CollectionConfig, load_collection_config


def valid_data():
    return {
        "asset_codes": [" petr27 ", "PETR27", "cepea1"],
        "request_timeout_seconds": 20,
        "request_interval_seconds": 0,
        "max_items": 20,
        "max_attempts": 1,
        "stale_run_minutes": 60,
    }


def test_normalizes_and_deduplicates_codes():
    config = CollectionConfig.from_dict(valid_data())
    assert config.asset_codes == ("PETR27", "CEPEA1")


def test_loads_json_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_data()), encoding="utf-8")
    config = load_collection_config(path)
    assert config.request_timeout_seconds == 20
    assert config.request_interval_seconds == 0


def test_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError, match="nao encontrado"):
        load_collection_config(tmp_path / "missing.json")


def test_rejects_invalid_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON invalido"):
        load_collection_config(path)


def test_rejects_empty_codes():
    data = valid_data()
    data["asset_codes"] = []
    with pytest.raises(ValueError, match="nao possui codigos"):
        CollectionConfig.from_dict(data)


def test_rejects_limit_excess():
    data = valid_data()
    data["asset_codes"] = ["A1", "A2", "A3"]
    data["max_items"] = 2
    with pytest.raises(ValueError, match="excede max_items"):
        CollectionConfig.from_dict(data)


def test_rejects_unbounded_attempts():
    data = valid_data()
    data["max_attempts"] = 4
    with pytest.raises(ValueError, match="entre 1 e 3"):
        CollectionConfig.from_dict(data)
