#!/bin/sh
# Per-client helpers for setting up the Fleet collector (fleet/README.md). Run from the
# agency's repo root.
#
#   fleet-client.sh external-id <slug> [--rotate]
#       Makes a random External ID for one client and writes it to
#       .fleet-secrets/<slug>.external-id (directory 0700, file 0600). It is NEVER printed:
#       the output is the file's path and the value's length only.
#   fleet-client.sh launch <slug> --region <r> --hub-arn <arn> [--template-url <https url>]
#       Prints how the client deploys the read role: a CloudFormation quick-create link and an
#       `aws cloudformation deploy` command. The External ID is not in either: the client pastes
#       it into the NoEcho ExternalId field, from the value the agency sends it privately.
#   fleet-client.sh secret <slug> --repo <owner/name>
#       Prints the command that stores the External ID as the FLEET_EXTERNAL_ID_<SLUG> repo
#       secret from the file (stdin), for the user to run in their own terminal.
set -eu

dir=".fleet-secrets"
usage() { sed -n '4,17p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 2 ] || usage
cmd=$1 slug=$2; shift 2
case "$slug" in *[!a-z0-9]*|"") echo "fleet-client: a client slug is 1-40 lowercase letters and digits" >&2; exit 2 ;; esac
[ ${#slug} -le 40 ] || { echo "fleet-client: slug too long" >&2; exit 2; }
file="$dir/$slug.external-id"

rotate=0 region="" hub="" template_url="" repo=""
while [ $# -gt 0 ]; do
  case "$1" in
    --rotate) rotate=1; shift ;;
    --region) region=${2:-}; shift 2 ;;
    --hub-arn) hub=${2:-}; shift 2 ;;
    --template-url) template_url=${2:-}; shift 2 ;;
    --repo) repo=${2:-}; shift 2 ;;
    *) usage ;;
  esac
done

urlencode() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }

case "$cmd" in
  external-id)
    if [ -e "$file" ] && [ "$rotate" = 0 ]; then
      echo "fleet-client: $file exists; keeping it (pass --rotate to replace it, then update the client's stack)" >&2
      exit 0
    fi
    umask 077
    mkdir -p "$dir"
    chmod 700 "$dir"
    tmp="$file.tmp.$$"
    # 40 characters of [A-Za-z0-9]: ~238 bits, inside the template's 16-128 and the collector's pattern.
    python3 -c 'import secrets, string; a = string.ascii_letters + string.digits; print("".join(secrets.choice(a) for _ in range(40)), end="")' > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$file"
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && ! git check-ignore -q "$file"; then
      echo "fleet-client: WARNING $dir/ is not git-ignored; add it to .gitignore before committing" >&2
    fi
    echo "fleet-client: External ID for $slug written to $file (mode 600, $(wc -c < "$file" | tr -d ' ') characters, not shown)"
    ;;
  launch)
    [ -n "$region" ] && [ -n "$hub" ] || usage
    case "$region" in *[!a-z0-9-]*) echo "fleet-client: bad region" >&2; exit 2 ;; esac
    printf '%s' "$hub" | grep -Eq '^arn:aws[a-z-]*:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]{1,128}$' ||
      { echo "fleet-client: --hub-arn must be the agency hub role's ARN" >&2; exit 2; }
    [ -f "$file" ] || { echo "fleet-client: no External ID yet; run: fleet-client.sh external-id $slug" >&2; exit 2; }
    echo "Send the client, over your usual private channel, the External ID in $file."
    echo "Then the client deploys the read role in each account (ExternalId field: paste that value):"
    echo
    if [ -n "$template_url" ]; then
      case "$template_url" in https://*) ;; *) echo "fleet-client: --template-url must be https" >&2; exit 2 ;; esac
      echo "  Console (Launch Stack):"
      echo "  https://$region.console.aws.amazon.com/cloudformation/home?region=$region#/stacks/quickcreate?templateURL=$(urlencode "$template_url")&stackName=fleet-read&param_AgencyPrincipalArn=$(urlencode "$hub")&param_RoleName=fleet-read"
      echo
    fi
    echo "  CLI (in the client's account, with its admin credentials):"
    echo "  aws cloudformation deploy --region $region --stack-name fleet-read --capabilities CAPABILITY_NAMED_IAM \\"
    echo "    --template-file fleet-client-read-role.yaml \\"
    echo "    --parameter-overrides AgencyPrincipalArn=$hub ExternalId=\"\$(cat fleet-external-id.txt)\""
    echo
    echo "  (fleet-client-read-role.yaml is in the public repo under fleet/infra/aws/.)"
    ;;
  secret)
    [ -n "$repo" ] || usage
    printf '%s' "$repo" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' || { echo "fleet-client: --repo owner/name" >&2; exit 2; }
    [ -f "$file" ] || { echo "fleet-client: no External ID yet for $slug" >&2; exit 2; }
    name="FLEET_EXTERNAL_ID_$(printf '%s' "$slug" | tr '[:lower:]' '[:upper:]')"
    echo "Run in your own terminal (the value goes from the file to gh on stdin, never on screen):"
    echo "  gh secret set $name --repo $repo < $file"
    ;;
  *) usage ;;
esac
