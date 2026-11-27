#!/bin/sh
# Talk to the hosted Dawnfix service with your Enterprise key (hosted/README.md).
#
#   service.sh license                                   GET  /v1/license
#   service.sh workspace --emails a@x.com,b@x.com        PATCH /v1/workspace (sign-in + digest)
#   service.sh client --name "Client Co" --emails a@x.com --repo owner/name
#                                                        POST /v1/clients (a client workspace)
#   service.sh fleet-client --name "Client Co" [--emails a@x.com] [--weekly on] [--auto-send off]
#                                                        POST /v1/clients, then PATCH /v1/fleet/client
#
# The key is read from $DAWNFIX_ENTERPRISE_KEY, or asked for without echo when stdin is a
# terminal. Run it in your own terminal, not through a coding agent, so the key never
# passes through one. Output is the service's JSON answer, which holds no key: a new
# client's key goes straight into that repo's DAWNFIX_ENTERPRISE_KEY secret through
# `gh secret set` and is never printed. The service URL is $DAWNFIX_URL, default
# https://dawnfix.dev.
set -eu

url="${DAWNFIX_URL:-https://dawnfix.dev}"
url="${url%/}"
case "$url" in https://*) ;; *) echo "service: the service URL must be https" >&2; exit 2 ;; esac

usage() { sed -n '3,9p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || usage
cmd=$1; shift

emails="" name="" repo="" weekly="" auto_send=""
while [ $# -gt 0 ]; do
  case "$1" in
    --emails) emails=${2:-}; shift 2 ;;
    --name) name=${2:-}; shift 2 ;;
    --repo) repo=${2:-}; shift 2 ;;
    --weekly) weekly=${2:-}; shift 2 ;;
    --auto-send) auto_send=${2:-}; shift 2 ;;
    *) usage ;;
  esac
done

key="${DAWNFIX_ENTERPRISE_KEY:-}"
if [ -z "$key" ] && [ -t 0 ]; then
  printf 'Dawnfix Enterprise key (not shown): ' >&2
  stty -echo 2>/dev/null || true
  IFS= read -r key || true
  stty echo 2>/dev/null || true
  printf '\n' >&2
fi
# No key, or a key the service refuses (401, 402, 403): the one line, and exit 0. Everything
# outside this helper (the workflows, every CLI) works the same without a key.
need_key="The hosted service needs an Enterprise key. Contact dawnfix@sivakoza.ai to get one."
[ -n "$key" ] || { echo "$need_key"; echo "service: set DAWNFIX_ENTERPRISE_KEY, or run this in a terminal to type it" >&2; exit 0; }
case "$key" in *[!A-Za-z0-9_-]*) echo "$need_key"; echo "service: that does not look like a key" >&2; exit 0 ;; esac

# {"emails": [...], "display_name"?: "..."} from a comma list; the service re-validates.
body_json() {
  python3 - "$emails" "$name" <<'PY'
import json, sys
emails = [e.strip() for e in sys.argv[1].split(",") if e.strip()]
doc = {"emails": emails}
if sys.argv[2]:
    doc["display_name"] = sys.argv[2]
print(json.dumps(doc))
PY
}

out=$(mktemp)
trap 'rm -f "$out"' EXIT

# The key goes in a header read from stdin (-K -), so it never shows in argv / ps.
# $extra_header, when set, is one more header line (X-Fleet-Client: <slug>).
extra_header=""
call() { # method path [json-body]
  if [ -n "${3:-}" ]; then
    { printf 'header = "Authorization: Bearer %s"\n' "$key"
      [ -z "$extra_header" ] || printf 'header = "%s"\n' "$extra_header"; } |
      curl -sS -o "$out" -w '%{http_code}' --max-time 15 -K - -X "$1" \
        -H 'Content-Type: application/json' --data-binary "$3" "$url$2"
  else
    printf 'header = "Authorization: Bearer %s"\n' "$key" |
      curl -sS -o "$out" -w '%{http_code}' --max-time 15 -K - -X "$1" "$url$2"
  fi
}

explain() {
  case "$1" in 401|402|403) echo "$need_key" ;; esac
  case "$1" in
    401) echo "service: HTTP 401, the key is not known (check for a typo, or that the Enterprise subscription is live)" >&2 ;;
    402) echo "service: HTTP 402, the key does not cover this: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("reason", ""))' "$out" 2>/dev/null)" >&2 ;;
    403) echo "service: HTTP 403, the key was revoked or does not allow this" >&2 ;;
    *) echo "service: HTTP $1" >&2 ;;
  esac
}

refused() { case "$1" in 401|402|403) exit 0 ;; *) exit 1 ;; esac; }

case "$cmd" in
  license)
    code=$(call GET /v1/license)
    cat "$out"; echo
    [ "$code" = 200 ] || { explain "$code"; refused "$code"; }
    ;;
  workspace)
    [ -n "$emails" ] || usage
    code=$(call PATCH /v1/workspace "$(body_json)")
    cat "$out"; echo
    [ "$code" = 200 ] || { explain "$code"; refused "$code"; }
    ;;
  client)
    [ -n "$name" ] && [ -n "$repo" ] || usage
    command -v gh >/dev/null 2>&1 || { echo "service: gh is needed to store the client's key" >&2; exit 2; }
    code=$(call POST /v1/clients "$(body_json)")
    if [ "$code" != 201 ]; then cat "$out"; echo; explain "$code"; refused "$code"; fi
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["license_key"], end="")' "$out" |
      gh secret set DAWNFIX_ENTERPRISE_KEY --repo "$repo"
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); d.pop("license_key", None); print(json.dumps(d, indent=2))' "$out"
    echo "service: the client's key is stored as DAWNFIX_ENTERPRISE_KEY in $repo (not shown)" >&2
    ;;
  fleet-client)
    # A client for the Fleet board. The agency's runner posts for it with the agency key, so
    # the client's own key is not needed here: it is dropped, never printed or stored.
    [ -n "$name" ] || usage
    for v in "$weekly" "$auto_send"; do case "$v" in ""|on|off) ;; *) usage ;; esac; done
    code=$(call POST /v1/clients "$(body_json)")
    if [ "$code" != 201 ]; then cat "$out"; echo; explain "$code"; refused "$code"; fi
    slug=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["client"]["slug"])' "$out")
    case "$slug" in *[!a-z0-9]*|"") echo "service: unexpected slug in the answer" >&2; exit 1 ;; esac
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); d.pop("license_key", None); print(json.dumps(d, indent=2))' "$out"
    if [ -n "$weekly$auto_send" ]; then
      flags=$(python3 -c 'import json,sys; d={}
if sys.argv[1]: d["weekly_email"] = sys.argv[1] == "on"
if sys.argv[2]: d["auto_send_after_24h"] = sys.argv[2] == "on"
print(json.dumps(d))' "$weekly" "$auto_send")
      extra_header="X-Fleet-Client: $slug"
      code=$(call PATCH /v1/fleet/client "$flags")
      cat "$out"; echo
      [ "$code" = 200 ] || { explain "$code"; refused "$code"; }
    fi
    echo "service: client $slug registered; add it to fleet.yml and the workflow matrix" >&2
    ;;
  *) usage ;;
esac
