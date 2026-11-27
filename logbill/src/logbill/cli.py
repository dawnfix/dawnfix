"""logbill scan | locate | fix"""
import argparse
import json
import sys
from pathlib import Path

from dawnfix_core.sources.aws import ReadOnlyViolation

from . import brand
from .awsread import READ_OPERATIONS, error_code, make_client
from .fix import VALID_RETENTION, apply, command, confirm_apply, targets_from_report, targets_live
from .locate import locate
from .prices import Prices, usd
from .report import render_html, render_json, summary_text
from .scan import ScanFailed, run_scan


def _session(profile):
    import boto3

    return boto3.session.Session(profile_name=profile) if profile else boto3.session.Session()


def _regions(arg: str | None, session) -> list[str]:
    if arg and arg.strip() == "all":
        return sorted(session.get_available_regions("logs"))
    if arg:
        return [r.strip() for r in arg.split(",") if r.strip()]
    return [session.region_name or "us-east-1"]


def _factory(session):
    cache = {}

    def make(service, region, allowed=READ_OPERATIONS):
        k = (service, region, frozenset(allowed))
        if k not in cache:
            cache[k] = make_client(session, service, region, allowed)
        return cache[k]
    return make


def _confirm(yes: bool):
    def ask(prompt: str) -> bool:
        print(prompt, file=sys.stderr)
        if yes:
            print("(--yes given)", file=sys.stderr)
            return True
        if not sys.stdin.isatty():
            print(f"{brand.CLI}: no terminal to confirm on; skipping Logs Insights (use --yes)", file=sys.stderr)
            return False
        print("[y/N] ", end="", file=sys.stderr, flush=True)
        return sys.stdin.readline().strip().lower() in ("y", "yes")
    return ask


def _aws_errors():
    from botocore.exceptions import BotoCoreError, NoCredentialsError, ProfileNotFound

    return NoCredentialsError, ProfileNotFound, BotoCoreError


def cmd_scan(a) -> int:
    if a.days < 1 or a.days > 455:
        print(f"{brand.CLI}: --days must be 1..455", file=sys.stderr)
        return 2
    if a.retention_days not in VALID_RETENTION:
        print(f"{brand.CLI}: --retention-days must be one of {VALID_RETENTION}", file=sys.stderr)
        return 2
    prices = Prices.load(a.prices)
    no_creds, no_profile, boto_err = _aws_errors()
    try:
        session = _session(a.profile)
        regions = _regions(a.regions, session)
        report = run_scan(make_client=_factory(session), regions=regions, days=a.days, prices=prices,
                          top=a.top, budget_gb=a.insights_budget_gb, hours=a.insights_hours,
                          retention_days=a.retention_days, confirm=_confirm(a.yes))
    except (no_creds, no_profile) as e:
        print(f"{brand.CLI}: no usable AWS credentials ({type(e).__name__}); sign in first, e.g. "
              f"aws sso login --profile <name>", file=sys.stderr)
        return 1
    except ScanFailed as e:
        print(f"{brand.CLI}: every region failed: {e}", file=sys.stderr)
        return 1
    except ReadOnlyViolation as e:
        print(f"{brand.CLI}: {e}", file=sys.stderr)
        return 1
    except boto_err as e:
        print(f"{brand.CLI}: AWS error ({error_code(e)})", file=sys.stderr)
        return 1

    out = Path(a.out)
    out.write_text(render_html(report))
    json_path = None
    if a.json == "-":
        sys.stdout.write(render_json(report))
    else:
        jp = Path(a.json) if a.json else out.with_suffix(".json")
        jp.write_text(render_json(report))
        json_path = str(jp)
    print(summary_text(report, str(out), json_path), file=sys.stderr if a.json == "-" else sys.stdout)
    return 0


def cmd_locate(a) -> int:
    repo = Path(a.repo)
    if not repo.is_dir():
        print(f"{brand.CLI}: no such directory {repo}", file=sys.stderr)
        return 2
    rp = Path(a.report)
    if not rp.is_file():
        print(f"{brand.CLI}: no report at {rp}; run `{brand.CLI} scan` first", file=sys.stderr)
        return 2
    res = locate(repo, rp, a.top)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    if not res:
        print("No patterns in the report (Logs Insights did not run).")
        return 0
    for p in res:
        print(f"{usd(p['monthly_usd'])}/mo  [{p['region']} {p['group']}]  id {p['id']}")
        print(f"  pattern: {p['text']}")
        if not p["candidates"]:
            print("  no source line found" + (f" (searched: {', '.join(p['fragments'])})" if p["fragments"]
                                               else " (no literal text in the pattern)"))
        for c in p["candidates"]:
            print(f"  {c['file']}:{c['line']}: {c['text']}")
    return 0


def cmd_fix(a) -> int:
    if a.retention_days not in VALID_RETENTION:
        print(f"{brand.CLI}: --retention-days must be one of {VALID_RETENTION}", file=sys.stderr)
        return 2
    only = set(a.group or []) or None
    session = None
    try:
        if a.report:
            targets = targets_from_report(json.loads(Path(a.report).read_text()), only)
        else:
            session = _session(a.profile)
            make = _factory(session)
            targets = targets_live(lambda r: make("logs", r), _regions(a.regions, session), only)
    except Exception as e:
        print(f"{brand.CLI}: could not list log groups ({error_code(e)})", file=sys.stderr)
        return 1
    if not targets:
        print("No never-expiring log groups found.")
        return 0
    print(f"# {len(targets)} log group(s) without retention -> {a.retention_days} days")
    for region, name in targets:
        print(command(region, name, a.retention_days, a.profile))
    if not a.apply:
        print(f"# Nothing changed. Run these yourself, or re-run with --apply "
              f"(needs logs:PutRetentionPolicy, see iam/logbill-apply-retention-policy.json).", file=sys.stderr)
        return 0
    if not confirm_apply(len(targets), a.retention_days):
        print(f"{brand.CLI}: not confirmed; nothing changed", file=sys.stderr)
        return 1
    session = session or _session(a.profile)
    results = apply(lambda r, allowed: make_client(session, "logs", r, allowed), targets, a.retention_days)
    bad = [x for x in results if not x["ok"]]
    for x in results:
        print(f"{'ok ' if x['ok'] else 'ERR'} {x['region']} {x['group']}" + (f" ({x['error']})" if not x["ok"] else ""))
    return 1 if bad else 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=brand.CLI, description=f"{brand.PRODUCT}: read-only CloudWatch Logs bill X-ray.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan log groups, price them, write the report")
    s.add_argument("--profile")
    s.add_argument("--regions", help="comma list, or 'all' (default: the profile's region)")
    s.add_argument("--days", type=int, default=30, help="ingestion window (default 30)")
    s.add_argument("--out", default=f"{brand.CLI}-report.html", help="HTML report path")
    s.add_argument("--json", help="JSON report path (default: next to --out); '-' prints it to stdout")
    s.add_argument("--insights-budget-gb", type=float, default=5.0,
                   help="max GB Logs Insights may scan in total; 0 disables pattern analysis (default 5)")
    s.add_argument("--insights-hours", type=float, default=24.0, help="query window per group (default 24)")
    s.add_argument("--top", type=int, default=10, help="groups to analyse in detail (default 10)")
    s.add_argument("--retention-days", type=int, default=30, help="retention to price the savings at (default 30)")
    s.add_argument("--prices", help="price table (default: the bundled prices.json)")
    s.add_argument("--yes", action="store_true", help="run Logs Insights without asking")
    s.set_defaults(func=cmd_scan)

    loc = sub.add_parser("locate", help="map the report's top patterns to source lines")
    loc.add_argument("--repo", required=True)
    loc.add_argument("--report", default=f"{brand.CLI}-report.json")
    loc.add_argument("--top", type=int, default=10)
    loc.add_argument("--json", action="store_true")
    loc.set_defaults(func=cmd_locate)

    f = sub.add_parser("fix", help="print put-retention-policy commands (or --apply them)")
    f.add_argument("--retention-days", type=int, default=30)
    f.add_argument("--report", help="take never-expiring groups from a scan's JSON instead of listing live")
    f.add_argument("--profile")
    f.add_argument("--regions")
    f.add_argument("--group", action="append", help="only this log group (repeatable)")
    f.add_argument("--apply", action="store_true", help="make the change; asks you to type a confirmation")
    f.set_defaults(func=cmd_fix)
    return p


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
