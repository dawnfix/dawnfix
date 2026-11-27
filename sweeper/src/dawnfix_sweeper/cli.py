"""sweeper scan --before-date YYYY-MM-DD [--tag K=V] [--region R] [--out DIR]"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from . import plan as pl
from .constants import BRAND, PLAN_BASENAME
from .guard import ReadOnlyViolation
from .pricing import Prices
from .scan import Scanner, load_ip_ranges, parse_tag_filters


def _date(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc) if "T" not in s else \
            datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date: {s!r} (use YYYY-MM-DD)") from None


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sweeper", description=f"{BRAND}: read-only post-cutover teardown plan.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="scan and write a teardown plan (never deletes)")
    s.add_argument("--before-date", required=True, type=_date,
                   help="cutover date: things created or last active before it are candidates")
    s.add_argument("--tag", action="append", default=[], metavar="KEY[=VALUE]",
                   help="only resources with this tag (repeat for AND). Route 53 records are not tag-filtered")
    s.add_argument("--region", action="append", default=[], help="region to scan (repeat); default: session region")
    s.add_argument("--profile", help="AWS profile")
    s.add_argument("--prices", help="price table JSON (default: bundled prices.json)")
    s.add_argument("--ip-ranges", help="AWS ip-ranges.json, enables the A/AAAA record check")
    s.add_argument("--out", default=".", help="directory for sweeper-plan.md and sweeper-plan.json")
    return p


def cmd_scan(args, session=None, clients=None, now=None) -> int:
    if session is None:
        import boto3

        session = boto3.session.Session(profile_name=args.profile)
    regions = args.region or [session.region_name or "us-east-1"]
    tags = parse_tag_filters(args.tag)
    prices = Prices.load(args.prices)
    ip_ranges = load_ip_ranges(args.ip_ranges) if args.ip_ranges else None
    now = now or datetime.now(timezone.utc)
    scanner = Scanner(session, regions, args.before_date, tags, prices, ip_ranges, clients=clients, now=now)
    try:
        result = scanner.run()
    except ReadOnlyViolation as e:
        print(f"sweeper: {e}", file=sys.stderr)
        return 3
    doc = pl.build(result, before=args.before_date, regions=regions, tags=tags, prices_meta=prices.meta(), now=now)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{PLAN_BASENAME}.json").write_text(json.dumps(doc, indent=2, default=str) + "\n")
    (out / f"{PLAN_BASENAME}.md").write_text(pl.markdown(doc))
    s = doc["summary"]
    print(f"sweeper: {s['items']} items ({s['delete']} delete, {s['verify']} verify), "
          f"~${s['monthly_usd_total']:,.2f}/month; plan in {out / PLAN_BASENAME}.md"
          + (f"; {len(doc['errors'])} collector(s) failed" if doc["errors"] else ""), file=sys.stderr)
    return 2 if doc["errors"] else 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return cmd_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
