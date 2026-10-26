import hashlib
import json
from pathlib import Path

import pytest

from credit_assets.golden_set import coverage, load_golden_set, locate, verify_item

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "config" / "golden_sets" / "informe_mensal_cra_cafe_brasil.json"

XML = """<?xml version="1.0" encoding="UTF-8"?>
<R xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <A total="10.5"><V>  Café  </V></A>
  <N xsi:nil="true"/>
  <S><I>1</I></S>
  <S><I>2</I></S>
</R>""".encode("utf-8")


def test_locate_keeps_raw_text_and_reports_line():
    found = locate(XML, "/R/A/V")
    assert found["raw_text"] == "  Café  "
    assert found["line"] == 3 and not found["xsi_nil"]


def test_locate_attribute_nil_instance_and_absence():
    assert locate(XML, "/R/A/@total")["raw_text"] == "10.5"
    assert locate(XML, "/R/N")["xsi_nil"] is True
    second = locate(XML, "/R/S/I", instance_index=1)
    assert second["raw_text"] == "2" and second["occurrences"] == 2 and second["line"] == 6
    assert locate(XML, "/R/Falta") == {"element_present": False, "occurrences": 0}


def _item(**overrides):
    item = {
        "item_id": "X-1", "xml_path": "/R/A/V", "instance_index": 0,
        "raw_file_hash": hashlib.sha256(XML).hexdigest(),
        "observed": {"element_present": True, "raw_text": "  Café  ", "line": 3, "xsi_nil": False},
    }
    item.update(overrides)
    return item


def test_verify_item_detects_value_and_hash_drift():
    assert verify_item(_item(), XML) == []
    drifted = _item(observed={"element_present": True, "raw_text": "Café", "line": 3})
    assert verify_item(drifted, XML) and "raw_text" in verify_item(drifted, XML)[0]
    assert verify_item(_item(), XML + b" ") == ["raw_file_hash diverge do arquivo"]


def test_load_rejects_approval_without_reviewer(tmp_path):
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    golden["items"][0]["human_review_status"] = "approved"
    golden["items"][0]["reviewed_by"] = None
    path = tmp_path / "g.json"
    path.write_text(json.dumps(golden), encoding="utf-8")
    with pytest.raises(ValueError, match="revisor"):
        load_golden_set(path)


def test_committed_golden_set_is_not_publishable_until_reviewed_and_complete():
    golden = load_golden_set(GOLDEN)
    report = coverage(golden)
    assert report["publishable"] is False
    assert set(report["required_case_types_missing"]) == {
        "absent", "repeated_block", "invalid"
    }
    assert all(item.get("observed") and item.get("raw_file_hash") for item in golden["items"])


def test_committed_golden_set_matches_local_raw_files_when_available():
    golden = load_golden_set(GOLDEN)
    checked = 0
    for item in golden["items"]:
        path = ROOT / item["local_file_path"]
        if not path.exists():
            continue
        assert verify_item(item, path.read_bytes()) == [], item["item_id"]
        checked += 1
    if not checked:
        pytest.skip("arquivos brutos locais ausentes (data/documents não versionado)")
