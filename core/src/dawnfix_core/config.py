"""Loads and validates .dawnfix.yml (every key: templates/dawnfix.yml)."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .rules import Rule, RuleError, parse_rule

AUTONOMY = ("diagnose", "plan", "draft-pr")
ISSUE_TRACKERS = ("github", "host", "linear", "jira", "none")
# github and host both mean the repo host's own issues (GitHub, GitLab); host is the neutral name.
HOST_ISSUES = ("github", "host")
ROLE_ARN = re.compile(r"^arn:aws[a-z-]*:iam::\d{1,12}:role/[\w+=,.@/-]+$")
REGION = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d$")
GCP_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# The fix job's only Bash permission is `Bash(<command>:*)`, built from this string, so it
# may hold no quotes, globs or shell operators: words of letters, digits and ./:=@+_-.
TEST_COMMAND = re.compile(r"^[A-Za-z0-9_./:=@+-]+( [A-Za-z0-9_./:=@+-]+)*$")
TEST_COMMAND_MAX = 200
# The hosted ingest caps a body at 64 KB, about 300 bytes per finding.
MAX_FINDINGS_CAP = 150

LIMIT_DEFAULTS = {
    "fix_prs_per_day": 3,
    "max_turns": 40,
    "timeout_minutes": 20,
    "max_events_per_source": 5000,
    "max_findings": 50,
    "spike_factor": 3.0,
    "spike_min_count": 10,
}


class ConfigError(Exception):
    pass


@dataclass
class LogGroup:
    name: str
    filter_pattern: str | None = None
    stream_prefix: str | None = None


@dataclass
class AwsSourceConfig:
    region: str
    role: str | None = None
    log_groups: list[LogGroup] = field(default_factory=list)
    alarms: bool = False
    alb: str | None = None

    @property
    def id(self) -> str:
        return f"aws:{self.region}"


@dataclass
class GcpSourceConfig:
    project: str
    filter: str = "severity>=ERROR"

    @property
    def id(self) -> str:
        return f"gcp:{self.project}"


@dataclass
class Config:
    version: int
    sources: list
    autonomy: str = "diagnose"
    schedule: str = "17 * * * *"
    rules: list[Rule] = field(default_factory=list)
    limits: dict = field(default_factory=lambda: dict(LIMIT_DEFAULTS))
    phi_mode: bool = False
    report: dict = field(default_factory=lambda: {"issues": "github", "digest": []})
    test_command: str | None = None

    def resolved(self) -> dict:
        """What `dawnfix config --json` prints: every value the workflow reads."""
        return {
            "version": self.version,
            "autonomy": self.autonomy,
            "schedule": self.schedule,
            "limits": dict(self.limits),
            "phi_mode": self.phi_mode,
            "report": {"issues": self.report["issues"], "digest": list(self.report["digest"])},
            "test": {"command": self.test_command},
            "sources": [s.id for s in self.sources],
            "rules": len(self.rules),
        }


def _keys(obj: Any, where: str, allowed: set, required: set = frozenset()) -> dict:
    if not isinstance(obj, dict):
        raise ConfigError(f"{where}: expected a mapping, got {type(obj).__name__}")
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(map(str, unknown))} (allowed: {', '.join(sorted(allowed))})")
    missing = sorted(required - set(obj))
    if missing:
        raise ConfigError(f"{where}: missing required key(s) {', '.join(missing)}")
    return obj


def _str(v, where, pattern=None, hint=""):
    if not isinstance(v, str) or not v.strip():
        raise ConfigError(f"{where}: expected a non-empty string")
    if pattern and not pattern.match(v):
        raise ConfigError(f"{where}: {v!r} is not valid{hint}")
    return v


def _bool(v, where):
    if not isinstance(v, bool):
        raise ConfigError(f"{where}: expected true or false")
    return v


def _aws(d, where) -> AwsSourceConfig:
    _keys(d, where, {"role", "region", "log_groups", "alarms", "alb"}, {"region"})
    groups = []
    raw_groups = d.get("log_groups") or []
    if not isinstance(raw_groups, list):
        raise ConfigError(f"{where}.log_groups: expected a list")
    for i, g in enumerate(raw_groups):
        w = f"{where}.log_groups[{i}]"
        if isinstance(g, str):
            groups.append(LogGroup(_str(g, w)))
        else:
            _keys(g, w, {"name", "filter_pattern", "stream_prefix"}, {"name"})
            groups.append(LogGroup(_str(g["name"], w + ".name"), g.get("filter_pattern"), g.get("stream_prefix")))
    src = AwsSourceConfig(
        region=_str(d["region"], where + ".region", REGION, " (e.g. us-east-1)"),
        role=_str(d["role"], where + ".role", ROLE_ARN, " (arn:aws:iam::<account>:role/<name>)") if d.get("role") else None,
        log_groups=groups,
        alarms=_bool(d.get("alarms", False), where + ".alarms"),
        alb=_str(d["alb"], where + ".alb", re.compile(r"^app/[\w-]+/[\w*-]+$"), " (app/<name>/<id> or app/<name>/*)") if d.get("alb") else None,
    )
    if not (src.log_groups or src.alarms or src.alb):
        raise ConfigError(f"{where}: nothing to watch; set log_groups, alarms or alb")
    return src


def _gcp(d, where) -> GcpSourceConfig:
    _keys(d, where, {"project", "filter"}, {"project"})
    return GcpSourceConfig(
        project=_str(d["project"], where + ".project", GCP_PROJECT, " (GCP project id)"),
        filter=_str(d.get("filter", "severity>=ERROR"), where + ".filter"),
    )


def parse(data: Any) -> Config:
    top = {"version", "autonomy", "schedule", "sources", "rules", "limits", "phi_mode", "report", "test", "extends"}
    _keys(data, "config", top, {"version", "sources"})
    if data.get("extends") is not None:
        raise ConfigError(
            "extends: not implemented yet in dawnfix-core; inline the shared settings in .dawnfix.yml for now"
        )
    if data["version"] != 1:
        raise ConfigError(f"version: only version 1 is supported, got {data['version']!r}")

    autonomy = data.get("autonomy", "diagnose")
    if autonomy not in AUTONOMY:
        raise ConfigError(f"autonomy: must be one of {', '.join(AUTONOMY)}, got {autonomy!r}")
    schedule = data.get("schedule", "17 * * * *")
    if not isinstance(schedule, str) or len(schedule.split()) != 5:
        raise ConfigError(f"schedule: expected a 5-field cron expression, got {schedule!r}")

    raw_sources = data["sources"]
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ConfigError("sources: expected a non-empty list")
    sources = []
    for i, s in enumerate(raw_sources):
        where = f"sources[{i}]"
        if not isinstance(s, dict) or len(s) != 1:
            raise ConfigError(f"{where}: each source is a single-key mapping, aws: {{...}} or gcp: {{...}}")
        kind, body = next(iter(s.items()))
        if kind == "aws":
            sources.append(_aws(body, f"{where}.aws"))
        elif kind == "gcp":
            sources.append(_gcp(body, f"{where}.gcp"))
        else:
            raise ConfigError(f"{where}: unknown source type {kind!r} (aws or gcp)")
    ids = [s.id for s in sources]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        raise ConfigError(f"sources: duplicate source {', '.join(sorted(dup))}; merge them into one entry")

    rules = []
    raw_rules = data.get("rules") or []
    if not isinstance(raw_rules, list):
        raise ConfigError("rules: expected a list")
    for i, r in enumerate(raw_rules):
        try:
            rules.append(parse_rule(r))
        except RuleError as e:
            raise ConfigError(f"rules[{i}]: {e}") from None

    limits = dict(LIMIT_DEFAULTS)
    raw_limits = _keys(data.get("limits") or {}, "limits", set(LIMIT_DEFAULTS))
    for k, v in raw_limits.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ConfigError(f"limits.{k}: expected a positive number")
        if k != "spike_factor" and not isinstance(v, int):
            raise ConfigError(f"limits.{k}: expected a whole number")
        limits[k] = v
    if limits["max_findings"] > MAX_FINDINGS_CAP:
        raise ConfigError(
            f"limits.max_findings: at most {MAX_FINDINGS_CAP} (the hosted ingest takes 64 KB per tick), "
            f"got {limits['max_findings']}"
        )

    report = {"issues": "github", "digest": []}
    raw_report = _keys(data.get("report") or {}, "report", {"issues", "digest"})
    if "issues" in raw_report:
        if raw_report["issues"] not in ISSUE_TRACKERS:
            raise ConfigError(f"report.issues: must be one of {', '.join(ISSUE_TRACKERS)}")
        report["issues"] = raw_report["issues"]
    digest = raw_report.get("digest", [])
    if not isinstance(digest, list) or not all(isinstance(x, str) and EMAIL.match(x) for x in digest):
        raise ConfigError("report.digest: expected a list of email addresses")
    report["digest"] = digest

    raw_test = _keys(data.get("test") or {}, "test", {"command"})
    test_command = None
    if raw_test.get("command") is not None:
        test_command = _str(raw_test["command"], "test.command")
        if len(test_command) > TEST_COMMAND_MAX or not TEST_COMMAND.match(test_command):
            raise ConfigError(
                f"test.command: {test_command[:60]!r} is not allowed; use plain words separated by single spaces "
                f"(letters, digits, . / : = @ + _ -), no quotes or shell operators, at most {TEST_COMMAND_MAX} characters"
            )

    return Config(
        version=1,
        sources=sources,
        autonomy=autonomy,
        schedule=schedule,
        rules=rules,
        limits=limits,
        phi_mode=_bool(data.get("phi_mode", False), "phi_mode"),
        report=report,
        test_command=test_command,
    )


def load(path: str | Path) -> Config:
    p = Path(path)
    try:
        text = p.read_text()
    except OSError as e:
        raise ConfigError(f"{p}: cannot read ({e.strerror})") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        at = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"{p}: invalid YAML{at}") from None
    return parse(data)
