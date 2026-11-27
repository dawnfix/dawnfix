# GCP: Workload Identity Federation for Dawnfix

`setup-wif.sh` lets the dawnfix workflow of one GitHub repository read Cloud Logging in
one project, with no service account and no key file.

```sh
infra/gcp/setup-wif.sh --dry-run --branch main my-project-id example-org/my-app   # print only
infra/gcp/setup-wif.sh --branch main my-project-id example-org/my-app             # run
```

Arguments: `PROJECT_ID GITHUB_REPO [POOL=dawnfix] [PROVIDER=github]`. Options:
`--dry-run` (echo every gcloud command, run none), `--branch B` (also require
`assertion.ref == refs/heads/B`; recommended, matches the AWS role's default-branch trust),
`--with-monitoring` (also grant `roles/monitoring.viewer`).

What it does, in order:

1. Enables `iam`, `iamcredentials`, `sts` and `logging` APIs.
2. Creates the workload identity pool, or reuses it.
3. Creates the OIDC provider for `https://token.actions.githubusercontent.com`, or updates the
   existing one so the settings below are always re-applied:
   - mapping `google.subject=assertion.sub, attribute.repository=assertion.repository, attribute.ref=assertion.ref`
   - condition `assertion.repository=='ORG/REPO'` (plus the branch when `--branch` is given).
     Tokens from every other repository are rejected at the provider.
4. Grants `roles/logging.viewer` (and optionally `roles/monitoring.viewer`) to
   `principalSet://iam.googleapis.com/projects/NUMBER/locations/global/workloadIdentityPools/POOL/attribute.repository/ORG/REPO`.
5. Prints the provider resource name for the repo variable `DAWNFIX_GCP_WIF_PROVIDER`.

Roles it never grants: `roles/logging.privateLogViewer` (data access audit logs, which can
hold request payloads), `roles/logging.admin`, anything with write access.

Re-running is safe: describe-before-create for the pool and provider, and
`add-iam-policy-binding` is a no-op for an existing binding. It does not remove bindings or
providers it no longer wants; delete the pool to undo everything:

```sh
gcloud iam workload-identity-pools delete dawnfix --project=my-project-id --location=global
```

Notes:

- The caller needs `roles/iam.workloadIdentityPoolAdmin`, `roles/resourcemanager.projectIamAdmin`
  and `roles/serviceusage.serviceUsageAdmin` (or Owner) on the project.
- A deleted pool keeps its id for 30 days; pick another `POOL` if you recreate within that time.
- The condition matches the repository *name*. If the repository could be deleted and its name
  re-registered by someone else, pin `assertion.repository_id` instead (not done by the script yet).
- `--dry-run` cannot look up the project number, so the printed resource names show
  `PROJECT_NUMBER`.
- Checked with `shellcheck` 0.11.0 (clean) and dry runs; it has not been run against a real project.
