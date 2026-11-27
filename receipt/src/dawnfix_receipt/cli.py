"""receipt --deploy-sha SHA --deployed-at ISO [--window 3d] [--tag-key K] [--post --pr N]"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from . import __version__
from . import costs as cx
from . import github as gh
from . import ingest
from . import receipt as rc
from .constants import BRAND, GITHUB_API
from .guard import ReadOnlyViolation, make_client

GROUP_SERVICE_USAGE = [{"Type": "DIMENSION", "Key": "SERVICE"}, {"Type": "DIMENSION", "Key": "USAGE_TYPE"}]


def _when(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO timestamp: {s!r}") from None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _window(s: str) -> int:
    try:
        return rc.parse_window(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="receipt", description=f"{BRAND}: what a deploy did to the AWS bill.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--deploy-sha", required=True)
    p.add_argument("--deployed-at", required=True, type=_when, help="ISO 8601; UTC if no offset")
    p.add_argument("--window", default="3d", type=_window, help="days on each side, e.g. 3d (default)")
    p.add_argument("--tag-key", help="also break down by this cost allocation tag (must be activated in Billing)")
    p.add_argument("--metric", default="UnblendedCost", choices=["UnblendedCost", "NetUnblendedCost",
                                                                  "AmortizedCost", "NetAmortizedCost"])
    p.add_argument("--lag-hours", type=int, default=24, help="treat a day as complete this long after it ends")
    p.add_argument("--cache-dir", default=".receipt-cache", help="'' disables the cache")
    p.add_argument("--profile")
    p.add_argument("--json", dest="json_out", help="also write the analysis here")
    p.add_argument("--ingest-out", metavar="PATH",
                   help="add this deploy to a counts-only dawnfix.receipt/1 document (created if missing) "
                        "for the CI workflow to send with an Enterprise key; see schema/receipt-ingest.schema.json")
    p.add_argument("--post", action="store_true", help="post or update the GitHub comment (default: print it)")
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--pr", type=int, help="comment on this PR instead of the commit")
    return p


def run(args, *, ce=None, now: datetime | None = None, http=None, env=None) -> int:
    env = os.environ if env is None else env
    now = now or datetime.now(timezone.utc)
    plan = rc.Plan(args.deployed_at, args.window, now, args.lag_hours)
    cache = cx.Cache(Path(args.cache_dir) if args.cache_dir else None)
    result = rc.Result(args.deploy_sha, plan, tag_key=args.tag_key, metric=args.metric)
    if plan.after_days:  # nothing to compare yet means no CE spend at all
        if ce is None:
            import boto3

            ce = make_client(boto3.session.Session(profile_name=args.profile), "ce")
        start = plan.before_days[0]
        end = plan.after_days[-1] + timedelta(days=1)
        try:
            pages = cx.fetch(ce, cx.request_for(start, end, GROUP_SERVICE_USAGE, args.metric), cache, now)
            series, estimated = cx.daily_by_key(pages, args.metric)
            result.lines = rc.averages(series, plan.before_days, plan.after_days)
            result.before_totals = [sum(s.get(d, 0.0) for s in series.values()) for d in plan.before_days]
            result.estimated_days = sorted(estimated)
            if args.tag_key:
                tag_req = cx.request_for(start, end, [{"Type": "TAG", "Key": args.tag_key}], args.metric)
                tag_series, _ = cx.daily_by_key(cx.fetch(ce, tag_req, cache, now), args.metric)
                result.tag_lines = rc.averages(
                    tag_series, plan.before_days, plan.after_days,
                    label=lambda k: (k.split("$", 1)[1] or "(untagged)") if "$" in k else k)
        except ReadOnlyViolation as e:
            print(f"receipt: {e}", file=sys.stderr)
            return 3
        except (ClientError, BotoCoreError) as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)
            print(f"receipt: Cost Explorer failed: {code}", file=sys.stderr)
            return 2
    result.ce_requests, result.ce_cache_hits = cache.requests, cache.hits
    body = rc.comment(result)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result.to_dict(), indent=2) + "\n")
    if args.ingest_out:
        ingest.write(args.ingest_out, result, now)
    print(result.headline(), file=sys.stderr)
    if not args.post:
        sys.stdout.write(body)
        return 0
    token = env.get("GITHUB_TOKEN")
    if not token or not args.repo:
        print("receipt: --post needs GITHUB_TOKEN and --repo (or GITHUB_REPOSITORY)", file=sys.stderr)
        return 2
    kw = {"http": http} if http else {}
    try:
        action, cid = gh.upsert_comment(args.repo, token, rc.marker(args.deploy_sha), body, pr=args.pr,
                                        sha=None if args.pr else args.deploy_sha,
                                        api=env.get("GITHUB_API_URL", GITHUB_API), **kw)
    except gh.GitHubError as e:
        print(f"receipt: {e}", file=sys.stderr)
        return 2
    print(f"receipt: comment {action} ({cid})", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    return run(parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
