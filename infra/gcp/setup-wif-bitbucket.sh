#!/usr/bin/env bash
# Dawnfix: let one Bitbucket repository's dawnfix read step read Cloud Logging in one GCP project
# through Workload Identity Federation (Bitbucket Pipelines OIDC, oidc: true). No service
# account, no keys.
#
#   infra/gcp/setup-wif-bitbucket.sh [--dry-run] [--branch main] [--with-monitoring] \
#       WORKSPACE WORKSPACE_UUID REPOSITORY_UUID PROJECT_ID [POOL] [PROVIDER]
#
#   WORKSPACE        the workspace slug (BITBUCKET_WORKSPACE); the OIDC issuer is per workspace
#   WORKSPACE_UUID   the workspace UUID without braces (the token audience is
#                    ari:cloud:bitbucket::workspace/<WORKSPACE_UUID>)
#   REPOSITORY_UUID  the repository UUID with its braces (BITBUCKET_REPO_UUID)
#   PROJECT_ID       GCP project whose logs Dawnfix reads
#   POOL             workload identity pool id (default: dawnfix)
#   PROVIDER         OIDC provider id in that pool (default: bitbucket)
#   --dry-run        print the gcloud commands, run nothing
#   --branch B       the branch whose pipelines may authenticate (default: main)
#   --with-monitoring  also grant roles/monitoring.viewer
#
# Grants roles/logging.viewer only. Never roles/logging.privateLogViewer (data access audit
# logs) and never roles/logging.admin. Safe to re-run: existing pool and provider are
# reused, and the provider's condition and mapping are re-applied.
set -euo pipefail

usage() { sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

DRY_RUN=0
BRANCH="main"
MONITORING=0
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --branch) shift; BRANCH="${1:-}"; [ -n "$BRANCH" ] || usage ;;
    --branch=*) BRANCH="${1#--branch=}" ;;
    --with-monitoring) MONITORING=1 ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done
[ "${#ARGS[@]}" -ge 4 ] && [ "${#ARGS[@]}" -le 6 ] || usage

WORKSPACE="${ARGS[0]}"
WORKSPACE_UUID="${ARGS[1]}"
REPOSITORY_UUID="${ARGS[2]}"
PROJECT_ID="${ARGS[3]}"
POOL="${ARGS[4]:-dawnfix}"
PROVIDER="${ARGS[5]:-bitbucket}"

UUID='[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
[[ "$WORKSPACE" =~ ^[A-Za-z0-9_.-]{1,100}$ ]] || { echo "bad WORKSPACE: $WORKSPACE" >&2; exit 2; }
[[ "$WORKSPACE_UUID" =~ ^${UUID}$ ]] || { echo "WORKSPACE_UUID must be a uuid without braces: $WORKSPACE_UUID" >&2; exit 2; }
[[ "$REPOSITORY_UUID" =~ ^\{${UUID}\}$ ]] || { echo "REPOSITORY_UUID must be a uuid with braces: $REPOSITORY_UUID" >&2; exit 2; }
[[ "$PROJECT_ID" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || { echo "bad PROJECT_ID: $PROJECT_ID" >&2; exit 2; }
[[ "$POOL" =~ ^[a-z0-9-]{4,32}$ ]] || { echo "bad POOL id: $POOL" >&2; exit 2; }
[[ "$PROVIDER" =~ ^[a-z0-9-]{4,32}$ ]] || { echo "bad PROVIDER id: $PROVIDER" >&2; exit 2; }
[[ "$BRANCH" =~ ^[A-Za-z0-9_./-]{1,255}$ ]] || { echo "bad branch: $BRANCH" >&2; exit 2; }

ISSUER="https://api.bitbucket.org/2.0/workspaces/${WORKSPACE}/pipelines-config/identity/oidc"
AUDIENCE="ari:cloud:bitbucket::workspace/${WORKSPACE_UUID}"
MAPPING="google.subject=assertion.sub,attribute.repository_uuid=assertion.repositoryUuid,attribute.branch=assertion.branchName,attribute.workspace_uuid=assertion.workspaceUuid"
CONDITION="assertion.repositoryUuid=='${REPOSITORY_UUID}' && assertion.branchName=='${BRANCH}'"

# Print a command, shell-quoted; run it unless --dry-run.
run() {
  printf '+'; printf ' %q' "$@"; printf '\n'
  if [ "$DRY_RUN" -eq 0 ]; then "$@"; fi
}

# Is this resource already there? Always false in a dry run (nothing is called).
exists() {
  [ "$DRY_RUN" -eq 0 ] && "$@" >/dev/null 2>&1
}

if [ "$DRY_RUN" -eq 0 ]; then
  command -v gcloud >/dev/null || { echo "gcloud not found" >&2; exit 1; }
  PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
else
  echo "# dry run: nothing is executed; PROJECT_NUMBER is looked up with"
  echo "#   gcloud projects describe $PROJECT_ID --format='value(projectNumber)'"
  PROJECT_NUMBER="PROJECT_NUMBER"
fi

run gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  logging.googleapis.com --project="$PROJECT_ID"

if exists gcloud iam workload-identity-pools describe "$POOL" --project="$PROJECT_ID" --location=global; then
  echo "pool $POOL exists; reusing it"
else
  run gcloud iam workload-identity-pools create "$POOL" --project="$PROJECT_ID" --location=global \
    --display-name="Dawnfix" --description="Dawnfix read-only logs"
fi

if exists gcloud iam workload-identity-pools providers describe "$PROVIDER" --project="$PROJECT_ID" \
    --location=global --workload-identity-pool="$POOL"; then
  echo "provider $PROVIDER exists; re-applying issuer, mapping and condition"
  run gcloud iam workload-identity-pools providers update-oidc "$PROVIDER" --project="$PROJECT_ID" \
    --location=global --workload-identity-pool="$POOL" --issuer-uri="$ISSUER" \
    --attribute-mapping="$MAPPING" --attribute-condition="$CONDITION" --allowed-audiences="$AUDIENCE"
else
  run gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project="$PROJECT_ID" \
    --location=global --workload-identity-pool="$POOL" --display-name="Bitbucket Pipelines" \
    --issuer-uri="$ISSUER" --attribute-mapping="$MAPPING" --attribute-condition="$CONDITION" --allowed-audiences="$AUDIENCE"
fi

MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository_uuid/${REPOSITORY_UUID}"
ROLES=(roles/logging.viewer)
if [ "$MONITORING" -eq 1 ]; then ROLES+=(roles/monitoring.viewer); fi
for role in "${ROLES[@]}"; do
  # add-iam-policy-binding is a no-op when the binding already exists.
  run gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$MEMBER" --role="$role" \
    --condition=None --quiet
done

PROVIDER_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo
echo "Done. Set this repository variable (not secret) on the repository ${REPOSITORY_UUID}:"
echo "  DAWNFIX_GCP_WIF_PROVIDER=${PROVIDER_NAME}"
echo "(Repository settings > Pipelines > Repository variables)"
