import pytest
import yaml

from dawnfix_core.rules import RuleError, apply, parse_condition, parse_rule

FACTS = {"source": "aws", "kind": "log", "service": "my-api-prod", "route": "/payments/:id", "status": 502,
         "count": 12, "alarm": "", "error": "x is undefined", "error_class": "TypeError", "severity": "medium"}


@pytest.mark.parametrize("cond, want", [
    ('route ^= "/payments"', True),
    ("route ^= /orders", False),
    ('route $= "/:id"', True),
    ('route == "/payments/:id"', True),
    ("service != my-api-prod", False),
    ('error ~= "undefined$"', True),
    ("error_class ~= ^Type", True),
    ("status >= 500", True),
    ("status < 500", False),
    ("count > 10", True),
    ("alarm ~= AlarmLow", False),
])
def test_conditions(cond, want):
    assert parse_condition(cond).test(FACTS) is want


def test_numeric_missing_value():
    assert parse_condition("status >= 500").test({"status": None}) is False


def test_bad_conditions():
    for bad in ("route", "route >= /a", "status == abc", "nope == 1", 5):
        with pytest.raises(RuleError):
            parse_condition(bad)


def test_spec_yaml_shapes_parse():
    rules = yaml.safe_load("""
- name: ignore scale-in alarms
  conditions: [ alarm ~= "AlarmLow" ]
  actions: [ ignore ]
- name: payments are critical
  conditions: [ route ^= "/payments" ]
  actions: [ severity: critical, notify: email ]
""")
    a, b = (parse_rule(r) for r in rules)
    assert a.ignore and a.conditions[0].value.pattern == "AlarmLow"
    assert b.severity == "critical" and b.notify == ["email"]


def test_apply_order_last_severity_wins_ignore_sticks():
    rules = [
        parse_rule({"name": "all high", "conditions": ["status >= 500"], "actions": [{"severity": "high"}]}),
        parse_rule({"name": "payments", "conditions": ["route ^= /payments"], "actions": [{"severity": "critical"}]}),
        parse_rule({"name": "mute", "conditions": ["service == other"], "actions": ["ignore"]}),
    ]
    v = apply(rules, FACTS)
    assert v == {"ignore": False, "severity": "critical", "notify": [], "rules": ["all high", "payments"]}
    assert apply(rules, {**FACTS, "service": "other"})["ignore"] is True


def test_conditions_see_severity_set_by_earlier_rule():
    rules = [
        parse_rule({"name": "a", "conditions": ["route ^= /payments"], "actions": [{"severity": "critical"}]}),
        parse_rule({"name": "b", "conditions": ["severity == critical"], "actions": [{"notify": "email"}]}),
    ]
    assert apply(rules, FACTS)["notify"] == ["email"]
