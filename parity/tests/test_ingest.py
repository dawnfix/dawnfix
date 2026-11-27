"""`parity check --ingest-out`: the dawnfix.parity/1 document. Counts, enums, a hashed
pair id; no name, no ARN, no account, no value. Validated against the schema file."""
import io
import json
import re
from pathlib import Path

import jsonschema
import pytest

from dawnfix_parity import brand
from dawnfix_parity.cli import EXIT_CONFIG, EXIT_DRIFT, run
from dawnfix_parity.diff import FINDING_KINDS
from dawnfix_parity.ingest import SCHEMA, pair_id
from dawnfix_parity.inventory import INVENTORY_FLAGS
from tests.conftest import DEV, NOW, PLANTED, PROD, WORLD

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema" / "parity-ingest.schema.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_FILE.read_text())


def check(world, config_file, tmp_path, *extra, hashes=False):
    world.queue_env("dev", hashes)
    world.queue_env("prod", hashes)
    path = tmp_path / "parity-ingest.json"
    out, err = io.StringIO(), io.StringIO()
    argv = ["-c", str(config_file), "check", "--left", "dev", "--right", "prod", "--summary", str(tmp_path / "s.md"),
            "--ingest-out", str(path), *extra] + (["--compare-hashes"] if hashes else [])
    code = run(argv, aws_factory=world.factory, now=NOW, out=out, err=err)
    return code, json.loads(path.read_text()), path.read_text(), (tmp_path / "s.md").read_text()


def names_in_world():
    """Every name, ARN, account and value of the synthetic world: none may reach the document."""
    out = {DEV, PROD, "dev", "prod", "shop", "PASSWORD", "STRIPE", "DB_URL", "LOG_FORMAT", "QUEUE"}
    for env in WORLD.values():
        out |= {p["Name"] for p in env["params"]} | {s["Name"] for s in env["secrets"]}
        out |= {s["ARN"] for s in env["secrets"]} | set(env["values"].values())
        out |= {f["FunctionName"] for f in env["functions"]} | {env["service"]}
    return {n for n in out | set(PLANTED.values()) if n not in ("true", "info", "on", "json", "text")}


def test_document_validates_and_counts(world, config_file, tmp_path, schema):
    code, doc, raw, summary = check(world, config_file, tmp_path, "--inventory")
    assert code == EXIT_DRIFT
    jsonschema.validate(doc, schema)
    assert doc["schema"] == SCHEMA and doc["result"] == "drift" and doc["generated_at"] == "2026-10-27T10:00:00Z"
    assert doc["pair"] == pair_id("dev", "prod") and re.fullmatch(r"[0-9a-f]{16}", doc["pair"])
    assert doc["findings"]["plaintext_secret"] == 1 and doc["findings"]["type_mismatch"] >= 2
    assert doc["findings"]["dangling_reference"] == 2 and doc["findings"]["cross_env_reference"] == 2
    assert set(doc["findings"]) == set(FINDING_KINDS)
    assert set(doc["inventory"]["flags"]) == set(INVENTORY_FLAGS)
    assert doc["inventory"]["items"] == 11 and doc["inventory"]["flags"]["never_rotated"] >= 1
    assert doc["failing"] == sum(v for k, v in doc["findings"].items() if FINDING_KINDS[k][1])
    # the names are in the job summary (it stays in GitHub), and only there
    assert "shop-prod-worker/PASSWORD" in summary or "lambda:shop-{env}-worker/PASSWORD" in summary


def test_no_name_or_value_leaves(world, config_file, tmp_path):
    _, doc, raw, _ = check(world, config_file, tmp_path, "--inventory", hashes=True)
    strings = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                strings.append(k)
                walk(x)
        elif isinstance(v, str):
            strings.append(v)
    walk(doc)
    for s in strings:
        assert re.fullmatch(r"[a-z_]+|[0-9a-f]{16}|dawnfix\.parity/1|\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", s), s
    for n in names_in_world():
        assert n not in raw, n
    assert doc["hashed"] is True and doc["findings"]["value_shared"] >= 1


def test_without_inventory_it_is_null(world, config_file, tmp_path, schema):
    _, doc, _, _ = check(world, config_file, tmp_path)
    jsonschema.validate(doc, schema)
    assert doc["inventory"] is None


def test_pass_document(world, config_file, tmp_path, schema):
    code, doc, _, _ = check(world, config_file, tmp_path, "--fail-on", "value_shared")
    assert code == 0 and doc["result"] == "pass" and doc["failing"] == 0
    jsonschema.validate(doc, schema)


def test_allowed_findings_move_to_allowed(world, config_file, tmp_path):
    config_file.write_text(config_file.read_text() + "allow:\n  - {kind: plaintext_secret, key: '*', reason: x}\n")
    _, doc, _, _ = check(world, config_file, tmp_path)
    assert doc["findings"]["plaintext_secret"] == 0 and doc["allowed"] == 1


def test_schema_is_strict(schema):
    def closed(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, node
                assert set(node["required"]) == set(node["properties"]), node
            for v in node.values():
                closed(v)
        elif isinstance(node, list):
            for v in node:
                closed(v)
    closed(schema)
    assert set(schema["properties"]["findings"]["required"]) == set(FINDING_KINDS)
    flags = schema["properties"]["inventory"]["oneOf"][1]["properties"]["flags"]["required"]
    assert set(flags) == set(INVENTORY_FLAGS)
    # a name smuggled in anywhere is rejected
    good = {"schema": SCHEMA, "generated_at": "2026-10-27T10:00:00Z", "pair": "0" * 16, "hashed": False,
            "result": "pass", "keys": {"left": 0, "right": 0, "references": 0},
            "findings": {k: 0 for k in FINDING_KINDS}, "allowed": 0, "failing": 0, "inventory": None}
    jsonschema.validate(good, schema)
    for bad in ({**good, "env": "prod"}, {**good, "pair": "prod"}, {**good, "keys": {**good["keys"], "name": 1}},
                {**good, "findings": {**good["findings"], "type_mismatch": "ssm:DB_URL"}},
                {**good, "inventory": {"items": 1, "flags": {f: 0 for f in INVENTORY_FLAGS}, "names": []}}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


def test_pair_id_is_order_sensitive_and_stable():
    assert pair_id("dev", "prod") == pair_id("dev", "prod") != pair_id("prod", "dev")


def test_aws_profile_override(config_file):
    from dawnfix_parity.config import load
    from dawnfix_parity.cli import _profiles

    cfg = load(config_file)
    cfg.env("prod").role_arn = "arn:aws:iam::222222222222:role/x"
    _profiles(cfg, ["prod=dawnfix-parity-right"])
    assert cfg.env("prod").profile == "dawnfix-parity-right" and cfg.env("prod").role_arn is None
    code = run(["-c", str(config_file), "diff", "--left", "dev", "--right", "prod", "--aws-profile", "prod"],
               out=io.StringIO(), err=(err := io.StringIO()))
    assert code == EXIT_CONFIG and "ENV=PROFILE" in err.getvalue()
    code = run(["-c", str(config_file), "diff", "--left", "dev", "--right", "prod", "--aws-profile", "qa=x"],
               out=io.StringIO(), err=(err := io.StringIO()))
    assert code == EXIT_CONFIG and "unknown environment" in err.getvalue()


def test_json_reports_carry_the_pitch(world, config_file):
    world.queue_env("dev")
    world.queue_env("prod")
    out = io.StringIO()
    assert run(["-c", str(config_file), "diff", "--left", "dev", "--right", "prod", "--format", "json"],
               aws_factory=world.factory, now=NOW, out=out, err=io.StringIO()) == 0
    doc = json.loads(out.getvalue())
    assert doc["pitch"] == {"line": brand.PITCH_LINE, "url": brand.PITCH_URL}
    assert brand.PITCH_URL.startswith("https://") and brand.CI_WORKFLOW in brand.PITCH_LINE
    for gone in ("Solo", "paid", "$", "plan"):
        assert gone not in brand.PITCH_LINE
