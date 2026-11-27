from pathlib import Path

import pytest

from dawnfix_core.config import ConfigError, load, parse

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "dawnfix.yml"


def test_example_loads():
    c = load(EXAMPLE)
    assert c.version == 1 and c.autonomy == "diagnose"
    aws, gcp = c.sources
    assert aws.region == "us-east-1" and aws.alarms and aws.alb == "app/my-lb/*"
    assert [g.name for g in aws.log_groups] == ["my-api-prod", "my-worker-prod"]
    assert aws.log_groups[1].stream_prefix == "cron"
    assert gcp.project == "my-proj" and gcp.filter == "severity>=ERROR"
    assert [r.name for r in c.rules] == ["ignore scale-in alarms", "payments are critical"]
    assert c.rules[1].severity == "critical" and c.rules[1].notify == ["email"]
    assert c.limits["spike_factor"] == 3 and c.limits["max_findings"] == 50
    assert c.report == {"issues": "github", "digest": ["ops@example.com"]}


def base(**over):
    d = {"version": 1, "sources": [{"aws": {"region": "us-east-1", "alarms": True}}]}
    d.update(over)
    return d


@pytest.mark.parametrize("data, msg", [
    ({"sources": []}, "missing required key(s) version"),
    (base(version=2), "only version 1"),
    (base(autonomy="yolo"), "autonomy: must be one of"),
    (base(schedule="hourly"), "5-field cron"),
    (base(sources=[]), "sources: expected a non-empty list"),
    (base(sources=[{"azure": {}}]), "unknown source type 'azure'"),
    (base(sources=[{"aws": {"alarms": True}}]), "sources[0].aws: missing required key(s) region"),
    (base(sources=[{"aws": {"region": "us-east-1"}}]), "nothing to watch"),
    (base(sources=[{"aws": {"region": "Mars", "alarms": True}}]), "sources[0].aws.region"),
    (base(sources=[{"aws": {"region": "us-east-1", "alarms": True, "role": "admin"}}]), "role"),
    (base(sources=[{"aws": {"region": "us-east-1", "alarms": "yes"}}]), "alarms: expected true or false"),
    (base(sources=[{"aws": {"region": "us-east-1", "alarms": True, "logs": []}}]), "unknown key(s) logs"),
    (base(sources=[{"gcp": {"project": "X"}}]), "sources[0].gcp.project"),
    (base(sources=[{"aws": {"region": "us-east-1", "alarms": True}}, {"aws": {"region": "us-east-1", "alarms": True}}]),
     "duplicate source aws:us-east-1"),
    (base(rules=[{"name": "x", "conditions": ["colour == red"], "actions": ["ignore"]}]), "rules[0]: condition"),
    (base(rules=[{"name": "x", "conditions": ["route ^= /a"], "actions": ["explode"]}]), "unknown action"),
    (base(rules=[{"name": "x", "conditions": ["route ~= ("], "actions": ["ignore"]}]), "bad regex"),
    (base(limits={"max_turns": 0}), "limits.max_turns: expected a positive number"),
    (base(limits={"max_turns": 2.5}), "whole number"),
    (base(limits={"tokens": 5}), "limits: unknown key(s) tokens"),
    (base(report={"issues": "trello"}), "report.issues"),
    (base(report={"digest": ["not-an-email"]}), "report.digest"),
    (base(phi_mode="on"), "phi_mode: expected true or false"),
    (base(limits={"max_findings": 151}), "limits.max_findings: at most 150"),
    (base(test="npm test"), "test: expected a mapping"),
    (base(test={"cmd": "npm test"}), "test: unknown key(s) cmd"),
    (base(test={"command": ""}), "test.command: expected a non-empty string"),
    (base(test={"command": 42}), "test.command: expected a non-empty string"),
    (base(test={"command": "npm test; curl evil"}), "test.command"),
    (base(test={"command": 'npm test -- "a b"'}), "test.command"),
    (base(test={"command": "npm  test"}), "test.command"),
    (base(test={"command": "make test && rm -rf /"}), "test.command"),
    (base(test={"command": "$(id)"}), "test.command"),
    (base(test={"command": "npm test " + "x" * 200}), "at most 200"),
    (base(colour="red"), "config: unknown key(s) colour"),
    (base(extends="org/.github:dawnfix-shared.yml"), "extends: not implemented"),
    ("just a string", "expected a mapping"),
])
def test_errors(data, msg):
    with pytest.raises(ConfigError) as e:
        parse(data)
    assert msg in str(e.value)


def test_invalid_yaml_reports_position(tmp_path):
    p = tmp_path / "c.yml"
    p.write_text("version: 1\nsources: [\n")
    with pytest.raises(ConfigError, match="invalid YAML at line"):
        load(p)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load(tmp_path / "nope.yml")


def test_max_findings_cap_boundary():
    assert parse(base(limits={"max_findings": 150})).limits["max_findings"] == 150
    assert parse(base()).limits["max_findings"] == 50


@pytest.mark.parametrize("command", ["npm test", "python -m pytest -q", "go test ./...", "uv run pytest tests/unit",
                                     "make test", "pnpm --filter=api test", "cargo test"])
def test_test_command_accepted(command):
    assert parse(base(test={"command": command})).test_command == command


def test_test_command_optional():
    assert parse(base()).test_command is None
    assert parse(base(test={})).test_command is None
    assert parse(base(test={"command": None})).test_command is None


def test_resolved_has_what_the_workflow_reads():
    c = parse(base(autonomy="draft-pr", test={"command": "npm test"}, phi_mode=True,
                   limits={"fix_prs_per_day": 2}, report={"issues": "none"}))
    r = c.resolved()
    assert r["autonomy"] == "draft-pr" and r["schedule"] == "17 * * * *" and r["phi_mode"] is True
    assert r["test"] == {"command": "npm test"}
    assert r["limits"]["fix_prs_per_day"] == 2 and r["limits"]["max_turns"] == 40
    assert r["limits"]["max_findings"] == 50
    assert r["report"] == {"issues": "none", "digest": []}
    assert r["sources"] == ["aws:us-east-1"]
