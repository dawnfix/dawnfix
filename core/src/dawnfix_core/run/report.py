"""dawnfix run report: the optional Enterprise calls to the hosted service, the same as the
reusable workflow's: POST /v1/ingest (the read stage's ingest.json) and POST /v1/prs (each PR
the publish stage opened, or a PR's merged/closed state). Only DAWNFIX_ENTERPRISE_KEY; without
it, the standard Enterprise line and nothing sent. Never fails the pipeline."""
import json
import re
from pathlib import Path

from .scrub import say
from .web import Http, host_of

NEED_KEY = {
    "ingest": "Hosted reporting (status page and digest) needs an Enterprise key. Contact dawnfix@sivakoza.ai to get one.",
    "prs": "Hosted PR tracking needs an Enterprise key. Contact dawnfix@sivakoza.ai to get one.",
}
KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _post(http, base, path, key, repo, data: bytes, run_id=""):
    headers = {"Content-Type": "application/json", "X-Dawnfix-Repo": repo}
    if run_id and re.match(r"^[0-9]{1,20}$", run_id):
        headers["X-Dawnfix-Run"] = run_id
    # The key goes only to the configured hosted-service host (web.Http checks).
    return http.request("POST", f"{base}{path}", headers=headers, body=data, token=key,
                        allowed_hosts=(host_of(base),))


def run_report(*, env, ctx, http: Http, ingest: Path | None = None, opened: Path | None = None,
               pr_state: str = "", branch: str = "", pr_url: str = "") -> int:
    key = env.get("DAWNFIX_ENTERPRISE_KEY", "")
    what = "ingest" if ingest else "prs"
    if not key:
        say(NEED_KEY[what])
        return 0
    if not KEY_RE.match(key):
        say(f"warning: {NEED_KEY[what]}")
        say("DAWNFIX_ENTERPRISE_KEY is not a key (it has characters a key never has); nothing sent")
        return 0
    base = (env.get("DAWNFIX_INGEST_URL") or "https://dawnfix.dev").rstrip("/")
    if not base.startswith("https://"):
        say("warning: the ingest URL must be an https base URL (the engine appends /v1/ingest); nothing sent")
        return 0
    repo = ctx.repo
    if not repo:
        say("warning: no repo detected (set DAWNFIX_REPO); nothing sent")
        return 0
    if ingest:
        r = _post(http, base, "/v1/ingest", key, repo, ingest.read_bytes(), ctx.run_id)
        c = r.status
        if c == 201:
            say("ingest: HTTP 201, tick recorded")
        elif c == 200:
            say("ingest: HTTP 200, this run was already recorded")
        elif c in (401, 402, 403):
            say(f"warning: {NEED_KEY['ingest']}")
            say(f"ingest: HTTP {c}, the Enterprise key was not accepted")
        elif c in (400, 413, 415):
            p = r.data.get("path", "?") if isinstance(r.data, dict) else "?"
            say(f"warning: ingest rejected the payload (HTTP {c} at {p}); this tick is missing from the digest and status page")
        elif c == 429:
            say("warning: ingest rate limited (HTTP 429); this tick is missing from the digest and status page")
        else:
            say(f"warning: ingest POST failed (HTTP {c:03d}); digest and status page will miss this tick")
    items = []
    if opened and opened.is_file():
        items = [(o["fingerprint"], o["url"], "open") for o in json.loads(opened.read_text()).get("opened", [])]
    if pr_state:
        fp = branch.removeprefix("dawnfix/")
        if not re.match(r"^[0-9a-f]{16}$", fp):
            say(f"{branch} is not a dawnfix fix branch; nothing to send")
        elif pr_state not in ("merged", "closed"):
            say("--pr-state must be merged or closed")
            return 2
        else:
            items.append((fp, pr_url, pr_state))
    for fp, url, state in items:
        data = json.dumps({"fingerprint": fp, "pr_url": url, "state": state}).encode()
        c = _post(http, base, "/v1/prs", key, repo, data).status
        if c == 200:
            say(f"service: PR state {state} recorded")
        elif c in (401, 402, 403):
            say(f"warning: {NEED_KEY['prs']}")
            say(f"service: HTTP {c}, the Enterprise key was not accepted")
        elif c == 404:
            say("warning: service does not know this repo or finding yet (HTTP 404); the ingest of this run may have failed")
        else:
            say(f"warning: PR state POST failed (HTTP {c:03d})")
    return 0
