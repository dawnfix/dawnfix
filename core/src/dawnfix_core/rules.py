"""Rules: `conditions` (all must match) and `actions` (ignore, severity, notify).

Condition syntax: `<field> <op> <value>`, e.g. `route ^= "/payments"`.
Ops: == != ~= (regex search) ^= (prefix) $= (suffix) and > >= < <= for numbers.
Rules run in order; `ignore` wins, and the last matching `severity` wins.
"""
import re
from dataclasses import dataclass, field

SEVERITIES = ("critical", "high", "medium", "low")
FIELDS = {
    "source", "source_id", "kind", "service", "route", "method", "status",
    "error", "error_class", "alarm", "count", "severity", "fingerprint",
}
NUMERIC = {"status", "count"}
OPS = ("==", "!=", "~=", "^=", "$=", ">=", "<=", ">", "<")
CONDITION = re.compile(r"^\s*([a-z_]+)\s*(==|!=|~=|\^=|\$=|>=|<=|>|<)\s*(.+?)\s*$")
NOTIFY = ("email", "issue", "none")


class RuleError(ValueError):
    pass


@dataclass
class Condition:
    field: str
    op: str
    value: object
    text: str

    def test(self, facts: dict) -> bool:
        v = facts.get(self.field)
        if self.field in NUMERIC:
            if v is None:
                return self.op == "!="
            v, want = float(v), float(self.value)
            return {
                "==": v == want, "!=": v != want, ">": v > want,
                ">=": v >= want, "<": v < want, "<=": v <= want,
            }[self.op]
        v = "" if v is None else str(v)
        if self.op == "==":
            return v == self.value
        if self.op == "!=":
            return v != self.value
        if self.op == "~=":
            return bool(self.value.search(v))
        if self.op == "^=":
            return v.startswith(self.value)
        if self.op == "$=":
            return v.endswith(self.value)
        return False


@dataclass
class Rule:
    name: str
    conditions: list[Condition]
    ignore: bool = False
    severity: str | None = None
    notify: list[str] = field(default_factory=list)

    def matches(self, facts: dict) -> bool:
        return all(c.test(facts) for c in self.conditions)


def parse_condition(text) -> Condition:
    if not isinstance(text, str):
        raise RuleError(f"condition {text!r}: expected a string like 'route ^= \"/payments\"'")
    m = CONDITION.match(text)
    if not m:
        raise RuleError(f"condition {text!r}: expected '<field> <op> <value>' with op one of {' '.join(OPS)}")
    fld, op, raw = m.groups()
    if fld not in FIELDS:
        raise RuleError(f"condition {text!r}: unknown field {fld!r} (one of {', '.join(sorted(FIELDS))})")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]
    if fld in NUMERIC:
        try:
            value = float(raw)
        except ValueError:
            raise RuleError(f"condition {text!r}: {fld} needs a number") from None
    else:
        if op in (">", ">=", "<", "<="):
            raise RuleError(f"condition {text!r}: {op} only works on {', '.join(sorted(NUMERIC))}")
        if op == "~=":
            try:
                value = re.compile(raw)
            except re.error as e:
                raise RuleError(f"condition {text!r}: bad regex ({e})") from None
        else:
            value = raw
    return Condition(fld, op, value, text)


def parse_rule(d) -> Rule:
    if not isinstance(d, dict):
        raise RuleError("expected a mapping with name, conditions, actions")
    unknown = set(d) - {"name", "conditions", "actions"}
    if unknown:
        raise RuleError(f"unknown key(s) {', '.join(sorted(unknown))}")
    name = d.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        raise RuleError("name: expected a string of 1-64 characters")
    conds = d.get("conditions")
    if not isinstance(conds, list) or not conds:
        raise RuleError(f"{name}: conditions must be a non-empty list")
    acts = d.get("actions")
    if not isinstance(acts, list) or not acts:
        raise RuleError(f"{name}: actions must be a non-empty list")
    rule = Rule(name=name, conditions=[parse_condition(c) for c in conds])
    for a in acts:
        if a == "ignore":
            rule.ignore = True
        elif isinstance(a, dict) and len(a) == 1:
            k, v = next(iter(a.items()))
            if k == "severity":
                if v not in SEVERITIES:
                    raise RuleError(f"{name}: severity must be one of {', '.join(SEVERITIES)}")
                rule.severity = v
            elif k == "notify":
                vals = v if isinstance(v, list) else [v]
                if not all(x in NOTIFY for x in vals):
                    raise RuleError(f"{name}: notify must be one of {', '.join(NOTIFY)}")
                rule.notify.extend(vals)
            else:
                raise RuleError(f"{name}: unknown action {k!r} (ignore, severity, notify)")
        else:
            raise RuleError(f"{name}: unknown action {a!r} (ignore, severity: <level>, notify: <channel>)")
    return rule


def apply(rules: list[Rule], facts: dict) -> dict:
    """Returns {'ignore', 'severity', 'notify', 'rules'} for one finding."""
    out = {"ignore": False, "severity": facts.get("severity"), "notify": [], "rules": []}
    for r in rules:
        if not r.matches({**facts, "severity": out["severity"]}):
            continue
        out["rules"].append(r.name)
        out["ignore"] = out["ignore"] or r.ignore
        if r.severity:
            out["severity"] = r.severity
        for n in r.notify:
            if n not in out["notify"]:
                out["notify"].append(n)
    return out
