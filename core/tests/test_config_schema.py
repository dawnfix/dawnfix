"""core/schema/config.schema.json says what dawnfix_core.config accepts, for editors and for
`npx dawnfix doctor` (which validates with it, without Python). The config parser is the
authority: every config it accepts here, the schema accepts, and every config it refuses in
test_config.py, the schema refuses too, except the few checks a schema cannot express."""
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from dawnfix_core.config import ConfigError, parse
from tests.test_config import base
from tests import test_config

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "core" / "schema" / "config.schema.json").read_text())
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)

# Refused by the parser, beyond what JSON Schema can say: `dawnfix validate` catches these.
PARSER_ONLY = ("duplicate source", "bad regex")


def test_the_schema_is_valid():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("path", [ROOT / "core" / "examples" / "dawnfix.yml", ROOT / "templates" / "dawnfix.yml"],
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_the_examples_pass_both(path):
    data = yaml.safe_load(path.read_text())
    parse(data)
    assert list(VALIDATOR.iter_errors(data)) == []


CASES = [m.args[1] for m in test_config.test_errors.pytestmark if m.name == "parametrize"][0]


@pytest.mark.parametrize("data, msg", CASES, ids=[m for _, m in CASES])
def test_what_the_parser_refuses_the_schema_refuses(data, msg):
    with pytest.raises(ConfigError):
        parse(data)
    if any(p in msg for p in PARSER_ONLY):
        pytest.skip("a check JSON Schema cannot express; dawnfix validate makes it")
    assert list(VALIDATOR.iter_errors(data)), f"the schema accepts what the parser refuses ({msg})"


@pytest.mark.parametrize("data", [
    base(),
    base(autonomy="draft-pr", test={"command": "go test ./..."}),
    base(sources=[{"aws": {"region": "eu-west-1", "log_groups": ["a", {"name": "b", "stream_prefix": "x"}]}},
                  {"gcp": {"project": "my-proj-1"}}]),
    base(rules=[{"name": "r", "conditions": ["status >= 500", "route ^= '/api'"],
                 "actions": ["ignore", {"severity": "low"}, {"notify": ["email", "issue"]}]}]),
    base(limits={"spike_factor": 2.5, "max_findings": 150}, phi_mode=True, report={"issues": "none", "digest": []}),
], ids=["minimal", "draft-pr", "aws+gcp", "rules", "limits"])
def test_what_the_parser_accepts_the_schema_accepts(data):
    parse(data)
    assert list(VALIDATOR.iter_errors(data)) == []
