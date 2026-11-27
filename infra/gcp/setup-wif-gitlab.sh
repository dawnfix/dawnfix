#!/usr/bin/env bash
# Dawnfix: let one GitLab project's dawnfix-read job read Cloud Logging in one GCP project
# through Workload Identity Federation (GitLab id_tokens). No service account, no keys.
#
#   infra/gcp/setup-wif-gitlab.sh [--dry-run] [--branch main] [--gitlab-url https://gitlab.com] \
#       [--with-monitoring] PROJECT_ID GITLAB_PROJECT [POOL] [PROVIDER]
#
#   PROJECT_ID     GCP project whose logs Dawnfix reads
#   GITLAB_PROJECT group/subgroup/project allowed to authenticate (CI_PROJECT_PATH)
#   POOL           workload identity pool id (default: dawnfix)
#   PROVIDER       OIDC provider id in that pool (default: gitlab)
#   --dry-run      print the gcloud commands, run nothing
#   --branch B     the branch whose pipelines may authenticate (default: main; keep it protected)
#   --gitlab-url U the GitLab server, issuer and token audience (default: https://gitlab.com)
#   --with-monitoring  also grant roles/monitoring.viewer
#
# Grants roles/logging.viewer only. Never roles/logging.privateLogViewer (data access audit
# logs) and never roles/logging.admin. Safe to re-run: existing pool and provider are
# reused, and the provider's condition and mapping are re-applied.
set -euo pipefail

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

DRY_RUN=0
BRANCH="main"
GITLAB_URL="https://gitlab.com"
MONITORING=0
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --branch) shift; BRANCH="${1:-}"; [ -n "$BRANCH" ] || usage ;;
    --branch=*) BRANCH="${1#--branch=}" ;;
    --gitlab-url) shift; GITLAB_URL="${1:-}" ;;
    --gitlab-url=*) GITLAB_URL="${1#--gitlab-url=}" ;;
    --with-monitoring) MONITORING=1 ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done
[ "${#ARGS[@]}" -ge 2 ] && [ "${#ARGS[@]}" -le 4 ] || usage

PROJECT_ID="${ARGS[0]}"
GITLAB_PROJECT="${ARGS[1]}"
POOL="${ARGS[2]:-dawnfix}"
PROVIDER="${ARGS[3]:-gitlab}"

[[ "$PROJECT_ID" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || { echo "bad PROJECT_ID: $PROJECT_ID" >&2; exit 2; }
[[ "$GITLAB_PROJECT" =~ ^[A-Za-z0-9_.][A-Za-z0-9_.-]*(/[A-Za-z0-9_.][A-Za-z0-9_.-]*)+$ ]] || { echo "GITLAB_PROJECT must be group/project: $GITLAB_PROJECT" >&2; exit 2; }
[[ "$GITLAB_URL" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?$ ]] || { echo "--gitlab-url must be https://<host>: $GITLAB_URL" >&2; exit 2; }
[[ "$POOL" =~ ^[a-z0-9-]{4,32}$ ]] || { echo "bad POOL id: $POOL" >&2; exit 2; }
[[ "$PROVIDER" =~ ^[a-z0-9-]{4,32}$ ]] || { echo "bad PROVIDER id: $PROVIDER" >&2; exit 2; }
[[ "$BRANCH" =~ ^[A-Za-z0-9_./-]{1,255}$ ]] || { echo "bad branch: $BRANCH" >&2; exit 2; }

ISSUER="$GITLAB_URL"
MAPPING="google.subject=assertion.sub,attribute.project_path=assertion.project_path,attribute.ref=assertion.ref,attribute.ref_type=assertion.ref_type"
CONDITION="assertion.project_path=='${GITLAB_PROJECT}' && assertion.ref_type=='branch' && assertion.ref=='${BRANCH}'"

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
    --attribute-mapping="$MAPPING" --attribute-condition="$CONDITION" --allowed-audiences="$GITLAB_URL"
else
  run gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project="$PROJECT_ID" \
    --location=global --workload-identity-pool="$POOL" --display-name="GitLab CI" \
    --issuer-uri="$ISSUER" --attribute-mapping="$MAPPING" --attribute-condition="$CONDITION" --allowed-audiences="$GITLAB_URL"
fi

MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.project_path/${GITLAB_PROJECT}"
ROLES=(roles/logging.viewer)
if [ "$MONITORING" -eq 1 ]; then ROLES+=(roles/monitoring.viewer); fi
for role in "${ROLES[@]}"; do
  # add-iam-policy-binding is a no-op when the binding already exists.
  run gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$MEMBER" --role="$role" \
    --condition=None --quiet
done

PROVIDER_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo
echo "Done. Set this CI/CD variable on ${GITLAB_PROJECT}:"
echo "  DAWNFIX_GCP_WIF_PROVIDER=${PROVIDER_NAME}"
echo "e.g. glab variable set DAWNFIX_GCP_WIF_PROVIDER --repo ${GITLAB_PROJECT} --value '${PROVIDER_NAME}'"
