"""dawnfix tick | validate | config."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import config as cfg
from . import state as st
from . import tick as tk


def _write_json(path: str, doc: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n")


def cmd_tick(args, sources=None) -> int:
    config = cfg.load(args.config)
    state = st.load(args.state)
    result = tk.run(config, state, window_minutes=args.window_minutes, sources=sources,
                    baseline_only=args.baseline)
    s = result.findings["summary"]
    failed = [r["id"] + "=" + r["error_code"] for r in result.findings["sources"] if not r["ok"]]
    line = (f"dawnfix: {s['events']} events, {s['fingerprints']} fingerprints, "
            f"{s['new']} new, {s['spike']} spike, {s['known']} known, {s['ignored']} ignored")
    if failed:
        line += f"; failed sources: {', '.join(failed)}"
    if args.dry_run:
        # Exactly what would be sent to the hosted service; nothing is written.
        print(json.dumps(result.ingest, indent=2))
        print(line + " (dry run: state and findings not written)", file=sys.stderr)
        return result.exit_code
    _write_json(args.out, result.findings)
    if args.ingest_out:
        _write_json(args.ingest_out, result.ingest)
    if result.exit_code != tk.EXIT_ERROR:
        st.save(args.state, result.state)
    print(line, file=sys.stderr)
    return result.exit_code


def cmd_validate(args) -> int:
    config = cfg.load(args.config)
    kinds = ", ".join(s.id for s in config.sources)
    print(f"{args.config}: ok ({kinds}; {len(config.rules)} rules; autonomy {config.autonomy})")
    return 0


def cmd_config(args) -> int:
    config = cfg.load(args.config)
    doc = config.resolved()
    if args.json:
        print(json.dumps(doc, indent=2))
        return 0
    for k, v in doc.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                print(f"{k}.{k2}: {v2}")
        else:
            print(f"{k}: {v}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dawnfix", description="Deterministic, read-only prod log tick.")
    p.add_argument("--version", action="version", version=f"dawnfix-core {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("tick", help="query sources, dedupe, write findings.json")
    t.add_argument("--config", default=".dawnfix.yml")
    t.add_argument("--state", required=True, help="JSON state file (created if missing)")
    t.add_argument("--out", default="findings.json")
    t.add_argument("--ingest-out", help="also write the ingest payload here")
    t.add_argument("--window-minutes", type=int, default=60)
    t.add_argument("--dry-run", action="store_true", help="print the ingest payload; write nothing")
    t.add_argument("--baseline", action="store_true",
                   help="record everything seen as known (first run on a noisy prod); exit 0")

    v = sub.add_parser("validate", help="check .dawnfix.yml")
    v.add_argument("--config", default=".dawnfix.yml")

    c = sub.add_parser("config", help="print the resolved config (defaults filled in)")
    c.add_argument("--config", default=".dawnfix.yml")
    c.add_argument("--json", action="store_true", help="as JSON, for the workflow")
    return p


def main(argv=None, sources=None) -> int:
    args = parser().parse_args(argv)
    if args.command == "tick" and not (1 <= args.window_minutes <= 7 * 24 * 60):
        print("dawnfix: --window-minutes must be between 1 and 10080", file=sys.stderr)
        return tk.EXIT_USAGE
    try:
        if args.command == "tick":
            return cmd_tick(args, sources=sources)
        if args.command == "config":
            return cmd_config(args)
        return cmd_validate(args)
    except cfg.ConfigError as e:
        print(f"dawnfix: config error: {e}", file=sys.stderr)
        return tk.EXIT_USAGE
    except st.StateError as e:
        print(f"dawnfix: state error: {e}", file=sys.stderr)
        return tk.EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
