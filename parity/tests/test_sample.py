import json
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sample import make_sample  # noqa: E402


def test_sample_is_current():
    assert make_sample.main(["--check"]) == 0


def test_sample_content():
    d = make_sample.build()
    assert "plaintext secret" in d["diff_text"] or "literal secret" in d["diff_text"]
    assert "FLAGS:" in d["inventory_text"]
    schema = json.loads((make_sample.ROOT / "schema" / "parity-ingest.schema.json").read_text())
    jsonschema.validate(d["ingest"], schema)
    assert "hunter2" not in json.dumps(d) and "PLANTED" not in json.dumps(d)
