"""dawnfix run read | agent | publish | report | context"""
import argparse
import json
import os
import sys
from pathlib import Path

from .. import config as cfg
from .agent import AgentError, run_agent
from .context import ContextError, detect
from .gitsafe import GitError
from .hosts import HostError, adapter_for
from .publish import PublishError, Refused, run_publish
from .read import FIXTURE, fixture_sources, run_read
from .report import run_report
from .scrub import say
from .stages import HOST_TOKEN, StageError, check_stage_env, register_secrets
from .web import Http

# The CI systems where each job is a fresh container, so a stage can be isolated by its job.
JOB_ISOLATION_CI = ("gitlab-ci", "bitbucket-pipelines")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dawnfix run", description=(
        "The CI-agnostic engine: one command per stage, each for its own CI job with only its own secret."))
    sub = p.add_subparsers(dest="stage", required=True)
    r = sub.add_parser("read", help="the read-only tick (cloud credentials only)")
    r.add_argument("--config", default=".dawnfix.yml")
    r.add_argument("--state", required=True, help="known fingerprints; keep it between runs (CI cache)")
    r.add_argument("--out", default=".dawnfix-out/read", help="artifact directory")
    r.add_argument("--baseline", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("agent", help="Claude Code headless (the AI API key only)")
    a.add_argument("--mode", required=True, choices=["diagnose", "fix"])
    a.add_argument("--dir", default=".", help="the checkout the agent works in")
    a.add_argument("--findings", required=True, help="findings.json from the read stage")
    a.add_argument("--out", required=True, help="artifact directory, outside the checkout")
    a.add_argument("--config", help="default: <dir>/.dawnfix.yml")
    a.add_argument("--budget", type=int, help="draft PRs left today, for the prompt (default: limits.fix_prs_per_day)")
    a.add_argument("--pass-env", action="append", default=[], metavar="NAME",
                   help="also pass this non-secret variable to the agent (e.g. a toolchain path)")
    a.add_argument("--claude-bin", help="a claude executable instead of the pinned npx package")
    a.add_argument("--isolation", choices=["namespace", "job"], default="namespace",
                   help="namespace (default): the agent contained in a PID namespace or cgroup, its changes "
                        "captured with git. job: GitLab CI and Bitbucket Pipelines only, where this stage is its "
                        "own fresh container: no containment, no git; the changed files are exported for the "
                        "publish job to check")
    u = sub.add_parser("publish", help="validate, commit, push, open a draft PR or issue (the host token only)")
    u.add_argument("--artifact", required=True, help="the agent stage's --out directory")
    u.add_argument("--findings", required=True, help="findings.json from the read stage (not the agent's copy)")
    u.add_argument("--dir", default=".", help="a fresh checkout of the commit the agent started from")
    u.add_argument("--out", default=".dawnfix-out/publish", help="opened.json and the bodies, for the report stage")
    u.add_argument("--isolation", choices=["namespace", "job"], default="namespace",
                   help="job: take only the exported files of an agent job run with --isolation job")
    e = sub.add_parser("report", help="optional Enterprise POSTs (the Enterprise key only)")
    e.add_argument("--ingest", help="ingest.json from the read stage")
    e.add_argument("--opened", help="opened.json from the publish stage")
    e.add_argument("--pr-state", choices=["merged", "closed"], help="a dawnfix PR was merged or closed")
    e.add_argument("--branch", default="", help="with --pr-state: its head branch, dawnfix/<fingerprint>")
    e.add_argument("--pr-url", default="", help="with --pr-state: its URL")
    sub.add_parser("context", help="print the detected CI context (no secrets)")
    return p


def main(argv=None, *, env=None, http=None, sources=None, push_env=None) -> int:
    args = parser().parse_args(argv)
    env = dict(os.environ) if env is None else env
    register_secrets(env)
    http = http or Http()
    try:
        ctx = detect(env)
        if args.stage == "context":
            print(json.dumps(ctx.as_dict(), indent=2))
            return 0
        check_stage_env(args.stage, env)
        if args.stage == "read":
            if sources is None:
                sources = fixture_sources(env, Path(args.config))
            return run_read(config=Path(args.config), state=Path(args.state), out_dir=Path(args.out),
                            baseline=args.baseline, dry_run=args.dry_run, autonomy=env.get("DAWNFIX_AUTONOMY", ""),
                            sources=sources, env=env, fixture=sources is not None and bool(env.get(FIXTURE)))
        if args.stage == "agent":
            d = Path(args.dir)
            if args.isolation == "job" and ctx.provider not in JOB_ISOLATION_CI:
                raise StageError(
                    f"--isolation job is only for a CI that runs each stage in its own fresh container "
                    f"(GitLab CI, Bitbucket Pipelines), not {ctx.provider}: there the agent stage needs its "
                    "PID namespace (the default)")
            claude = [args.claude_bin] if args.claude_bin else ([env["DAWNFIX_CLAUDE_BIN"]] if env.get("DAWNFIX_CLAUDE_BIN") else None)
            return run_agent(mode=args.mode, workdir=d, findings=Path(args.findings), out_dir=Path(args.out),
                             config_path=Path(args.config) if args.config else d / ".dawnfix.yml", env=env, http=http,
                             claude_cmd=claude, budget=args.budget, pass_env=args.pass_env,
                             isolation=args.isolation, base_commit=ctx.commit,
                             require_network_sandbox=ctx.provider == "bitbucket-pipelines")
        if args.stage == "publish":
            token = env.get(HOST_TOKEN, "")
            if not token:
                raise StageError(f"no repo host token: set {HOST_TOKEN} in this job only (contents and pull or "
                                 "merge requests write, issues write, this repo only)")
            # DAWNFIX_BITBUCKET_EMAIL (not secret): the token is an Atlassian API token of that account
            # (Basic auth). Without it a Bitbucket token is an access token (Bearer).
            host = adapter_for(ctx, token, http, bitbucket_email=env.get("DAWNFIX_BITBUCKET_EMAIL", ""))
            return run_publish(checkout=Path(args.dir), artifact=Path(args.artifact), findings_path=Path(args.findings),
                               out_dir=Path(args.out), host=host, token=token, push_env=push_env,
                               autonomy=env.get("DAWNFIX_AUTONOMY", ""), isolation=args.isolation)
        return run_report(env=env, ctx=ctx, http=http, ingest=Path(args.ingest) if args.ingest else None,
                          opened=Path(args.opened) if args.opened else None, pr_state=args.pr_state or "",
                          branch=args.branch, pr_url=args.pr_url)
    except StageError as e:
        say(f"error: {e}")
        return 2
    except cfg.ConfigError as e:
        say(f"error: config error: {e}")
        return 2
    except Refused as e:
        say(f"error: the agent's changes {e}; nothing published")
        return 1
    except ContextError as e:
        say(f"error: {e}")
        return 2
    except (AgentError, PublishError, HostError, GitError) as e:
        say(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
