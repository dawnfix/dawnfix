"""fleet collect | validate | check.

    fleet collect --client <slug> [--config fleet.yml] [--out summary.json]
                  [--cache-dir .fleet-cache] [--no-spend]
    fleet validate [--config fleet.yml]
    fleet check summary.json

Exit: 0 written (credential failures are data, shown on the board), 2 bad config or
arguments, 1 anything else. Credentials come from the environment: in GitHub Actions, the
OIDC role `aws-actions/configure-aws-credentials` assumed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, load
from .summary import SummaryError, validate


def _collect(args) -> int:
    clients = load(args.config)
    client = clients.get(args.client)
    if client is None:
        print(f"fleet: no client {args.client!r} in {args.config}", file=sys.stderr)
        return 2
    import boto3

    from .collect import collect

    doc = collect(client, base_session=boto3.session.Session(),
                  cache_dir=Path(args.cache_dir) if args.cache_dir else None,
                  spend_enabled=not args.no_spend)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text)
    for a in doc["accounts"]:
        spend = a["spend"]["status"] + ("(cached)" if a["spend"]["cached"] else "")
        print(f"fleet: {a['env']} {a['account'][:6]} credential={a['credential']} alarms={a['alarms']['status']} "
              f"spend={spend} certs={a['certs']['status']}", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fleet", description="Read-only client account summary for the fleet board.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--client", required=True, help="client slug, as in fleet.yml")
    c.add_argument("--config", default="fleet.yml")
    c.add_argument("--out", default="summary.json", help="file to write, or - for stdout")
    c.add_argument("--cache-dir", default=".fleet-cache",
                   help="keeps one Cost Explorer answer per account per UTC day ('' to disable)")
    c.add_argument("--no-spend", action="store_true", help="skip Cost Explorer ($0.01 per request)")
    v = sub.add_parser("validate")
    v.add_argument("--config", default="fleet.yml")
    k = sub.add_parser("check")
    k.add_argument("file")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0

    try:
        if args.cmd == "collect":
            return _collect(args)
        if args.cmd == "validate":
            clients = load(args.config)
            n = sum(len(c.accounts) for c in clients.values())
            print(f"ok: {len(clients)} clients, {n} accounts")
            return 0
        validate(json.loads(Path(args.file).read_text()))
        print("ok")
        return 0
    except ConfigError as e:
        print(f"fleet: config: {e}", file=sys.stderr)
        return 2
    except SummaryError as e:
        print(f"fleet: summary: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"fleet: {type(e).__name__}", file=sys.stderr)
        return 2
