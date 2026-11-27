import json

import pytest

from dawnfix_core import state as st
from tests.conftest import NOW


def test_missing_file_is_empty(tmp_path):
    assert st.load(tmp_path / "s.json") == st.empty()


def test_round_trip(tmp_path):
    s = st.empty()
    st.record(s, "a" * 16, 3, NOW)
    st.save(tmp_path / "s.json", s)
    assert st.load(tmp_path / "s.json") == s


def test_bad_files(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{nope")
    with pytest.raises(st.StateError):
        st.load(p)
    p.write_text(json.dumps({"version": 99, "fingerprints": {}}))
    with pytest.raises(st.StateError):
        st.load(p)


def test_new_known_spike():
    s = st.empty()
    fp = "b" * 16
    assert st.classify(s, fp, 5, 3.0, 10) == ("new", None)
    for _ in range(4):
        st.record(s, fp, 5, NOW)
    assert st.classify(s, fp, 6, 3.0, 10) == ("known", 5.0)
    assert st.classify(s, fp, 14, 3.0, 10) == ("known", 5.0)  # under 3x
    assert st.classify(s, fp, 15, 3.0, 10) == ("spike", 5.0)


def test_spike_needs_min_count():
    s = st.empty()
    st.record(s, "c" * 16, 1, NOW)
    assert st.classify(s, "c" * 16, 5, 3.0, 10)[0] == "known"
    assert st.classify(s, "c" * 16, 10, 3.0, 10)[0] == "spike"


def test_record_keeps_first_seen():
    s = st.empty()
    e = st.record(s, "d" * 16, 1, NOW)
    first = e["first_seen"]
    e = st.record(s, "d" * 16, 2, NOW.replace(hour=11))
    assert e["first_seen"] == first and e["last_seen"] == "2026-10-27T11:00:00Z"
    assert (e["total"], e["ticks"]) == (3, 2)
