"""leastpriv role ROLE_NAME --days 90 [--format json|terraform|cloudformation|all] [--out DIR]"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from . import __version__
from . import render as rd
from .collect import collect
from .constants import BRAND, OUT_DIR, TOOL
from .guard import ReadOnlyViolation, make_client
from .trim import trim


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=TOOL, description=f"{BRAND}: least-privilege diff for an IAM role. "
                                                            "Never applies anything.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("role", help="trim one role")
    r.add_argument("role_name")
    r.add_argument("--days", type=int, default=90, help="unused for this many days means removable (default 90)")
    r.add_argument("--format", default="all", choices=[*rd.FORMATS, "all"])
    r.add_argument("--out", default=OUT_DIR)
    r.add_argument("--region", default="us-east-1", help="region of the Access Analyzer unused-access analyzer")
    r.add_argument("--analyzer-arn", help="unused-access analyzer to read (default: first active one found)")
    r.add_argument("--no-analyzer", action="store_true", help="use only the IAM last-accessed report")
    r.add_argument("--policy-file", action="append", default=[], metavar="POLICY=PATH",
                   help="repo JSON file holding that policy; writes a git-apply patch against it (repeat)")
    r.add_argument("--profile")
    return p


def _policy_files(specs: list[str]) -> dict[str, str]:
    out = {}
    for s in specs:
        name, sep, path = s.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"{TOOL}: bad --policy-file {s!r}; use POLICY=path/to/file.json")
        out[name] = path
    return out


def cmd_role(args, *, iam=None, aa=None, sleep=time.sleep, now=None) -> int:
    if not 1 <= args.days <= 400:
        # IAM keeps last-accessed history for 400 days.
        print(f"{TOOL}: --days must be 1..400 (IAM's last-accessed history is 400 days)", file=sys.stderr)
        return 2
    files = _policy_files(args.policy_file)
    if iam is None:
        import boto3

        session = boto3.session.Session(profile_name=args.profile)
        iam = make_client(session, "iam", "us-east-1")
        if not args.no_analyzer:
            aa = make_client(session, "accessanalyzer", args.region)
    try:
        ev = collect(iam, None if args.no_analyzer else aa, args.role_name, args.analyzer_arn, sleep=sleep)
    except ReadOnlyViolation as e:
        print(f"{TOOL}: {e}", file=sys.stderr)
        return 3
    except (ClientError, BotoCoreError, RuntimeError, TimeoutError) as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code") if hasattr(e, "response") else str(e)
        print(f"{TOOL}: {code}", file=sys.stderr)
        return 2
    result = trim(ev, args.days, now=now)
    formats = rd.FORMATS if args.format == "all" else (args.format,)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for c in result.changes:
        if not c.changed:
            continue
        slug = rd._slug(c.policy.name)
        (out / f"{slug}.json").write_text(rd.as_json(c.new_document) or "null\n")
        for fmt in formats:
            (out / f"{slug}.{fmt}.diff").write_text(rd.diff(c, fmt))
        if c.policy.name in files:
            path = files[c.policy.name]
            text = Path(path).read_text()
            if json.loads(text) != c.policy.document:
                print(f"{TOOL}: {path} differs from the live {c.policy.name} policy (drift); no patch written "
                      "for it. Reconcile the repo with AWS first.", file=sys.stderr)
                continue
            m = re.search(r"\n( +)\S", text)
            new = json.dumps(c.new_document, indent=len(m.group(1)) if m else 2) + "\n" if c.new_document else ""
            (out / f"{slug}.patch").write_text("".join(difflib.unified_diff(
                text.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{path}", f"b/{path}")))
    (out / "pr.md").write_text(rd.pr_body(result, formats))
    (out / "report.json").write_text(json.dumps(rd.report(result), indent=2, default=str) + "\n")
    rem = result.removals
    high = sum(1 for x in rem if x.risk == "high")
    print(f"{TOOL}: {args.role_name}: {len(rem)} unused permission(s) to remove ({high} high risk) across "
          f"{sum(1 for c in result.changes if c.changed)} policy(ies); PR body in {out / 'pr.md'}. "
          "Nothing was applied.", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return cmd_role(args)


if __name__ == "__main__":
    raise SystemExit(main())
