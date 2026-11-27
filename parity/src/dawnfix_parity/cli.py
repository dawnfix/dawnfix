"""parity diff | check | inventory | validate

Exit codes: 0 no drift (or diff/inventory ran), 1 drift found (check), 2 config or usage
error, 3 AWS error (credentials, access denied, throttled), 4 read-only guard tripped.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from datetime import datetime, timezone

from . import brand, report
from .aws import AwsError, EnvAws, ReadOnlyViolation, refused
from .cloudtrail import RateLimiter, lookup_reads
from .collect import collect
from .config import ConfigError, load
from .diff import DEFAULT_FAIL_ON, FINDING_KINDS, diff
from .ingest import build_ingest
from .inventory import INVENTORY_FLAGS, build
from .model import ValueHasher
from .resolve import Resolver

EXIT_OK, EXIT_DRIFT, EXIT_CONFIG, EXIT_AWS, EXIT_GUARD = 0, 1, 2, 3, 4


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=brand.CLI_NAME, description=f"{brand.PRODUCT_NAME}: read-only config parity "
                                "and secret inventory for SSM, Secrets Manager, ECS and Lambda.")
    p.add_argument("-c", "--config", default=brand.CONFIG_FILE, help=f"default {brand.CONFIG_FILE}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def pair(sp):
        sp.add_argument("--left", required=True, help="environment name, e.g. dev")
        sp.add_argument("--right", required=True, help="environment name, e.g. prod")
        sp.add_argument("--compare-hashes", action="store_true",
                        help="also read values and compare salted SHA-256 digests in memory (never printed)")
        sp.add_argument("--format", choices=("text", "markdown", "json"), default="text")
        sp.add_argument("-o", "--output", help="write the report here instead of stdout")
        sp.add_argument("--aws-profile", action="append", default=[], metavar="ENV=PROFILE",
                        help="use this AWS profile for ENV instead of .parity.yml's aws.profile/role_arn "
                             "(CI: one OIDC role per environment, written to a profile); repeatable")

    d = sub.add_parser("diff", help="compare two environments")
    pair(d)
    c = sub.add_parser("check", help="diff for CI: exit 1 on drift, Markdown job summary")
    pair(c)
    c.add_argument("--fail-on", default=",".join(DEFAULT_FAIL_ON),
                   help="comma list of finding kinds and/or inventory flags "
                        f"({', '.join(list(FINDING_KINDS) + list(INVENTORY_FLAGS))})")
    c.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY"),
                   help="append a Markdown summary here (default $GITHUB_STEP_SUMMARY)")
    c.add_argument("--inventory", action="store_true",
                   help="also count inventory flags (unread, never rotated, rotation overdue, orphaned) "
                        "in the summary and --ingest-out, without failing on them")
    c.add_argument("--ingest-out", metavar="PATH",
                   help="write the dawnfix.parity/1 document (counts and enums only, no names or values) here")
    i = sub.add_parser("inventory", help="per secret/parameter: age, reads, rotation, references")
    i.add_argument("--env", action="append", help="environment(s); default all")
    i.add_argument("--cloudtrail", action="store_true",
                   help="opt-in: look up GetSecretValue/GetParameter* in CloudTrail to show who reads what")
    i.add_argument("--cloudtrail-days", type=int, default=30, help="1-90, default 30")
    i.add_argument("--cloudtrail-max-pages", type=int, default=20, help="per event name, 50 events/page")
    i.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    i.add_argument("-o", "--output")
    i.add_argument("--aws-profile", action="append", default=[], metavar="ENV=PROFILE",
                   help="use this AWS profile for ENV (see diff --help); repeatable")
    sub.add_parser("validate", help="parse the config only; no AWS calls")
    return p


def _emit(text: str, path: str | None, out):
    if path:
        with open(path, "w") as f:
            f.write(text)
    else:
        out.write(text)


def _profiles(cfg, pairs: list[str]) -> None:
    """--aws-profile ENV=PROFILE: that profile already holds ENV's role (CI writes one per
    OIDC role), so it replaces both aws.profile and aws.role_arn for ENV."""
    for p in pairs:
        env, sep, profile = p.partition("=")
        if not sep or not env.strip() or not profile.strip():
            raise ConfigError(f"--aws-profile: expected ENV=PROFILE, got {p!r}")
        e = cfg.env(env.strip())
        e.profile, e.role_arn = profile.strip(), None


def _envs_for(cfg, names, aws_factory):
    envs = [cfg.env(n) for n in names]
    return envs, {e.name: aws_factory(e) for e in envs}


def _pitched(text: str) -> str:
    """JSON reports carry the closing pitch (brand constants) for a caller to show."""
    doc = json.loads(text)
    doc["pitch"] = {"line": brand.PITCH_LINE, "url": brand.PITCH_URL}
    return json.dumps(doc, indent=2, default=str) + "\n"


def run(argv=None, aws_factory=None, now: datetime | None = None, out=None, err=None,
        hasher: ValueHasher | None = None, limiter: RateLimiter | None = None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    aws_factory = aws_factory or (lambda e: EnvAws(e))
    now = now or datetime.now(timezone.utc)
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_CONFIG
    try:
        cfg = load(args.config)
        _profiles(cfg, getattr(args, "aws_profile", []))
        if args.cmd == "validate":
            out.write(f"{args.config}: ok ({', '.join(cfg.envs)})\n")
            return EXIT_OK

        if args.cmd in ("diff", "check"):
            if args.left == args.right:
                raise ConfigError("--left and --right must differ")
            fail_on = DEFAULT_FAIL_ON
            if args.cmd == "check":
                fail_on = tuple(x.strip() for x in args.fail_on.split(",") if x.strip())
                bad = set(fail_on) - set(FINDING_KINDS) - set(INVENTORY_FLAGS)
                if bad:
                    raise ConfigError(f"--fail-on: unknown {', '.join(sorted(bad))}")
            envs, awss = _envs_for(cfg, [args.left, args.right], aws_factory)
            h = (hasher or ValueHasher()) if args.compare_hashes else None
            snaps = collect(envs, awss, h)
            resolver = Resolver(snaps, {e.name: e for e in envs}, awss)
            res = diff(cfg, snaps[args.left], snaps[args.right], resolver)
            render = {"text": report.diff_text, "markdown": report.diff_markdown, "json": report.diff_json}[args.format]
            text = render(res, fail_on)
            _emit(_pitched(text) if args.format == "json" else text, args.output, out)
            if args.cmd == "diff":
                return EXIT_OK
            failing = len(res.active(fail_on))
            inv_flags = [f for f in fail_on if f in INVENTORY_FLAGS]
            md = report.diff_markdown(res, fail_on)
            rows = None
            if inv_flags or args.inventory:
                rows = {n: build(cfg, snaps[n], resolver, now) for n in (args.left, args.right)}
                for env_rows in rows.values():
                    for r in env_rows:
                        hit = [f for f in r.flags if f in inv_flags and not _allowed(cfg, f, r.item.ckey)]
                        if hit:
                            failing += 1
                            err.write(f"{r.item.env} {r.item.name}: {', '.join(hit)}\n")
                md += "\n" + report.inventory_markdown(rows, None)
            if args.summary:
                with open(args.summary, "a") as f:
                    f.write(md)
            if args.ingest_out:
                doc = build_ingest(res, failing, rows, now,
                                   allowed_flag=lambda flag, r: _allowed(cfg, flag, r.item.ckey))
                with open(args.ingest_out, "w") as f:
                    json.dump(doc, f, indent=2)
                    f.write("\n")
            return EXIT_DRIFT if failing else EXIT_OK

        if args.cmd == "inventory":
            names = args.env or list(cfg.envs)
            all_envs, awss = _envs_for(cfg, list(cfg.envs), aws_factory)
            snaps = collect(all_envs, awss, None)
            resolver = Resolver(snaps, cfg.envs, awss)
            rows, days = {}, None
            for n in names:
                reads = None
                if args.cloudtrail:
                    days = max(1, min(args.cloudtrail_days, 90))
                    reads = lookup_reads(awss[n].client("cloudtrail"), now, days, args.cloudtrail_max_pages,
                                         limiter or RateLimiter())
                    if reads.truncated:
                        err.write(f"warning: {n}: CloudTrail lookup hit --cloudtrail-max-pages; readers are partial\n")
                rows[n] = build(cfg, snaps[cfg.env(n).name], resolver, now, reads)
            render = {"text": report.inventory_text, "markdown": report.inventory_markdown,
                      "json": report.inventory_json}[args.format]
            text = render(rows, days)
            _emit(_pitched(text) if args.format == "json" else text, args.output, out)
            return EXIT_OK
    except ConfigError as e:
        err.write(f"config error: {e}\n")
        return EXIT_CONFIG
    except ReadOnlyViolation as e:
        err.write(f"refused: {refused(e)}\n")
        return EXIT_GUARD
    except AwsError as e:
        err.write(f"AWS error: {e}\n")
        if e.code in ("ExpiredToken", "ExpiredTokenException", "UnrecognizedClientException"):
            err.write("credentials expired: run `aws sso login --profile <profile>` or re-run the OIDC step\n")
        return EXIT_AWS
    except Exception as e:  # botocore credential errors and the like: no message, may echo input
        name = type(e).__name__
        if name in ("NoCredentialsError", "ProfileNotFound", "NoRegionError", "TokenRetrievalError",
                    "SSOTokenLoadError", "UnauthorizedSSOTokenError", "ClientError"):
            err.write(f"AWS error: {name}\n")
            return EXIT_AWS
        raise
    return EXIT_CONFIG


def _allowed(cfg, kind, key) -> bool:
    return any(a.kind in ("*", kind) and fnmatch.fnmatchcase(key, a.key) for a in cfg.allow)


def main():
    sys.exit(run())
