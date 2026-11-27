"""dawnfix run read: the read job of the reusable workflow, for any CI. Cloud credentials only
(OIDC); no AI key, no host token. Validates .dawnfix.yml, runs the tick, and writes into --out:

  config.json    the resolved config
  findings.json  the redacted findings (the agent stage's input; only when something is new)
  ingest.json    the counts the report stage may send (Enterprise)
  outputs.env    has_new, autonomy, ... as KEY=VALUE lines, for the CI to branch on

State (known fingerprints) is the file --state; the CI keeps it between runs (a cache). With
no state file the run is a baseline: existing errors are recorded, not reported.

TEST ONLY: DAWNFIX_READ_FIXTURE=<path> reads recorded log events from a JSON file instead of
the cloud (schema dawnfix.read-fixture/1), for proving a pipeline end to end without a cloud
account. It is refused unless DAWNFIX_ALLOW_READ_FIXTURE=1 is also set, it is never on by
default, and a run with it is never a baseline (each run is a fresh test).
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import cli as core_cli
from .. import config as cfg
from .guard import HASHES_FILE, write_hashes
from .scrub import say
from .stages import StageError

FIXTURE = "DAWNFIX_READ_FIXTURE"
FIXTURE_ALLOW = "DAWNFIX_ALLOW_READ_FIXTURE"
FIXTURE_SCHEMA = "dawnfix.read-fixture/1"


class FixtureSource:
    """Recorded log events from a file, standing in for the cloud sources (tests only)."""

    def __init__(self, doc: dict):
        from ..normalize import Event, find_error_class
        self.id = str(doc.get("source_id") or "aws:us-east-1")
        if not re.match(r"^(aws|gcp):[A-Za-z0-9_.-]{1,64}$", self.id):
            raise StageError(f"{FIXTURE}: source_id must be aws:<region> or gcp:<project>")
        self.type = self.id.split(":")[0]
        self.truncated = False
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self._events = []
        for e in doc.get("events") or []:
            if not isinstance(e, dict):
                raise StageError(f"{FIXTURE}: each event is an object")
            msg, status = str(e.get("message", "")), e.get("status")
            self._events.append(Event(
                source=self.type, source_id=self.id, kind=str(e.get("kind") or "log"), service=str(e.get("service", "")),
                route=str(e.get("route", "")), method=e.get("method"), status=int(status) if status is not None else None,
                error_class=str(e.get("error_class") or find_error_class(msg, status)), message=msg,
                timestamp=now, count=int(e.get("count", 1))))

    def events(self, window):
        return list(self._events)


def fixture_sources(env, config: Path):
    """The recorded-log source when DAWNFIX_READ_FIXTURE is set (and allowed), else None."""
    path = env.get(FIXTURE, "")
    if not path:
        return None
    if env.get(FIXTURE_ALLOW) != "1":
        raise StageError(f"{FIXTURE} is a test-only input (recorded log events instead of your cloud); it is "
                         f"refused unless {FIXTURE_ALLOW}=1 is set too. Unset {FIXTURE} for a real run")
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise StageError(f"{FIXTURE}: {path} is not a file")
    try:
        doc = json.loads(p.read_text())
    except ValueError:
        doc = None
    if not isinstance(doc, dict) or doc.get("schema") != FIXTURE_SCHEMA:
        raise StageError(f"{FIXTURE}: {path} is not a {FIXTURE_SCHEMA} document")
    say(f"warning: TEST ONLY: reading recorded log events from {path} ({FIXTURE}), not from your cloud")
    return [FixtureSource(doc)]


def run_read(*, config: Path, state: Path, out_dir: Path, baseline=False, dry_run=False, autonomy="",
             sources=None, env=None, fixture=False) -> int:
    conf = cfg.load(str(config))
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = conf.resolved()
    (out_dir / "config.json").write_text(json.dumps(resolved, indent=2) + "\n")
    if autonomy and autonomy not in ("diagnose", "plan", "draft-pr"):
        say(f"error: autonomy must be diagnose, plan or draft-pr, not '{autonomy}'")
        return 2
    autonomy = autonomy or conf.autonomy
    if not baseline and not state.exists() and not dry_run and not fixture:
        say("warning: no saved state found; running as --baseline so existing errors are recorded, not fixed")
        baseline = True
    args = ["tick", "--config", str(config), "--state", str(state), "--out", str(out_dir / "findings.json"),
            "--ingest-out", str(out_dir / "ingest.json")]
    if baseline:
        args.append("--baseline")
    if dry_run:
        args.append("--dry-run")
    rc = core_cli.main(args, sources=sources)
    if rc not in (0, 10):
        return rc
    has_new = rc == 10 and not baseline and not dry_run
    limits = resolved["limits"]
    lines = {"has_new": str(has_new).lower(), "autonomy": autonomy, "issues": resolved["report"]["issues"],
             "max_turns": int(limits["max_turns"]), "timeout_minutes": int(limits["timeout_minutes"]),
             "fix_prs_per_day": int(limits["fix_prs_per_day"]), "test_command": resolved["test"]["command"] or "",
             "fixture": str(bool(fixture)).lower()}
    # Hashes only, never values: the publish stage redacts these from anything it sends.
    write_hashes(out_dir / HASHES_FILE, env or {})
    (out_dir / "outputs.env").write_text("".join(f"{k}={v}\n" for k, v in lines.items()))
    if autonomy == "draft-pr" and not resolved["test"]["command"]:
        say("warning: autonomy is draft-pr but .dawnfix.yml has no test.command; the fix stage can only open issues")
    say(f"has_new={lines['has_new']}")
    return 0
