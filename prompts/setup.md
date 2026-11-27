# Set up Dawnfix

Sets up Dawnfix in the current GitHub repo: `.dawnfix.yml`, a read-only AWS role or GCP
identity, the `dawnfix.yml` workflow, repo variables, a dry run and a setup PR.

````text
Set up Dawnfix (github.com/dawnfix/dawnfix) in this GitHub repo. Work as a wizard: one step
at a time, show each command before you run it, and wait for my yes before anything that
writes (a cloud stack, a file, a repo variable, a commit, a PR).

Hard rules:
- Never ask me to paste a secret into this chat, and never print or echo one. That covers
  the Anthropic API key, the optional DAWNFIX_LICENSE, PATs and cloud keys. I set secrets
  myself in my own terminal with `gh secret set NAME --repo <repo>` (gh asks without echo).
- The AWS role and the GCP identity must be read-only. If the read-only check fails, stop the
  cloud part and tell me which actions are the problem. Do not edit the policy to make it pass.
- Never push to the default branch. Everything lands through a PR I review.

Before step 1, tell me plainly what this costs me (Dawnfix itself is free, no key): my own
Anthropic tokens, only on runs that find a new error; GitHub Actions minutes (the hourly read
job is about a minute a run, ~750 a month; free on public repos); small CloudWatch API charges
(GetMetricData $0.01 per 1,000 metrics, for load balancer 5xx).

0. Ask me for REF: v0.2.0 or a later release tag, or a commit SHA, of github.com/dawnfix/dawnfix
   (v0.1.0 has no prompts/ci/, which the workflow needs). Check it exists:
   curl -fsI https://raw.githubusercontent.com/dawnfix/dawnfix/REF/prompts/ci/fix.md must answer
   200; if not, stop and tell me to pick a tag from https://github.com/dawnfix/dawnfix/tags. Fetch it:
   git clone --quiet https://github.com/dawnfix/dawnfix "$HOME/.cache/dawnfix-src" (or fetch
   if it exists), then git -C "$HOME/.cache/dawnfix-src" checkout --quiet REF. Call it SRC.
   Install the CLI (Python 3.11+): python3 -m venv "$HOME/.cache/dawnfix/venv" and
   "$HOME/.cache/dawnfix/venv/bin/pip" install "dawnfix-core @ git+https://github.com/dawnfix/dawnfix@REF#subdirectory=core"
   (use "dawnfix-core[gcp] @ ..." if GCP is involved). Call the binary `dawnfix`.
1. Detect: GitHub repo (git remote, gh repo view --json nameWithOwner,defaultBranchRef),
   default branch, language and test command (package.json "test", pytest, go test ./...,
   cargo test, make test). Stop if there is no GitHub remote or `gh auth status` fails. If
   .dawnfix.yml exists, offer to edit it instead of overwriting. Ask me to confirm the test command.
2. Ask: AWS, GCP or both. Region per AWS source, project id for GCP.
3. AWS: read SRC/infra/aws/README.md and the Parameters of SRC/infra/aws/dawnfix-read-role.yaml.
   Check for an existing GitHub OIDC provider (aws iam list-open-id-connect-providers) and set
   CreateOIDCProvider / ExistingOIDCProviderArn as the README says. After I name the AWS profile:
   aws cloudformation deploy --stack-name dawnfix-read --template-file SRC/infra/aws/dawnfix-read-role.yaml
     --capabilities CAPABILITY_NAMED_IAM --region <region> --parameter-overrides GitHubOrg=.. GitHubRepo=.. Branch=.. ...
   Read the RoleArn output (aws cloudformation describe-stacks ... --query "Stacks[0].Outputs").
   Verify (needs iam:SimulatePrincipalPolicy on my profile; the venv's python has boto3):
   "$HOME/.cache/dawnfix/venv/bin/python" SRC/infra/aws/verify_readonly.py <RoleArn> --log-group <group> --region <region>
   [--aws-profile <admin profile>]. Exit 0: go on. Anything else: show the flagged actions, refuse
   the role, write its ARN nowhere. Then ask for log groups (offer aws logs describe-log-groups),
   whether to watch alarms, and an ALB glob like app/my-lb/* (or none).
4. GCP: bash SRC/infra/gcp/setup-wif.sh --dry-run --branch <default branch> <PROJECT_ID> <owner/repo>.
   Check the printed commands: the only role granted is roles/logging.viewer. Anything else
   (privateLogViewer, owner, editor, any write role): stop. On my yes run it without --dry-run
   and keep the DAWNFIX_GCP_WIF_PROVIDER value it prints. Ask for the log filter (default severity>=ERROR).
5. Write .dawnfix.yml from SRC/templates/dawnfix.yml and fill `sources`. autonomy: diagnose to
   start (issues only); plan = an issue with the planned fix; draft-pr = failing test + fix as a
   draft PR, never merged. Keep the off-the-hour `schedule`. limits.fix_prs_per_day 3. Ask if logs
   can hold health or other sensitive personal data: if yes, phi_mode: true, and tell me I need my
   own BAA with the model provider. report.issues: github. test.command: the confirmed command,
   plain words only (no quotes, ; && | or $); leave it out if there are no tests (then issues only).
   Remove the template's example rules unless I want them. Run `dawnfix validate --config .dawnfix.yml` until it passes.
6. Copy SRC/templates/github/workflows/dawnfix.yml to .github/workflows/dawnfix.yml. Replace
   DAWNFIX_CORE_REF with REF (it installs dawnfix-core and loads the agent instructions from
   prompts/ci/ at that ref). Put .dawnfix.yml's `schedule` in the cron line. Replace the run: of
   the "Install project dependencies" step (echo "no install step configured") with the repo's
   install command (npm ci, pip install -e ., ...). Do not touch permissions or the job split.
   `grep -n DAWNFIX_CORE_REF .github/workflows/dawnfix.yml` must print nothing. List the vars and
   secrets it reads: grep -oE '\$\{\{ *(vars|secrets)\.[A-Za-z0-9_]+' .github/workflows/dawnfix.yml | sort -u
7. Variables, shown as a list first, then set on one yes with gh variable set NAME --repo <repo>
   --body <value>: DAWNFIX_AWS_ROLE_ARN, DAWNFIX_AWS_REGION, DAWNFIX_GCP_WIF_PROVIDER, and
   optionally DAWNFIX_MODEL. Leave DAWNFIX_INGEST_URL unset.
   Secrets, which I type in my terminal: gh secret set ANTHROPIC_API_KEY --repo <repo>. Optional:
   DAWNFIX_LICENSE (Enterprise only: turns on hosted reporting at dawnfix.dev; without it nothing
   is sent anywhere; to set who gets the hosted digest, I run, in my own terminal,
   sh SRC/hosted/service.sh workspace --emails a@example.com,b@example.com). For plan or draft-pr, PRs made with GITHUB_TOKEN do not trigger CI: explain
   the options, a GitHub App I own (var DAWNFIX_PR_APP_ID + secret DAWNFIX_PR_APP_PRIVATE_KEY) or a
   fine-grained PAT (secret DAWNFIX_PR_TOKEN), Contents and Pull requests read/write on this repo
   only. Show `gh api repos/<repo>/actions/permissions/workflow` ("Allow GitHub Actions to create
   pull requests") and change it only on my yes. Confirm with gh secret list (names only).
8. Propose CODEOWNERS lines for /.github/ and /.dawnfix.yml. Show branch protection
   (gh api repos/<repo>/branches/<branch>/protection; 404 = none) and advise required review and
   code owner review. Do not change protection yourself.
9. Dry run with my own credentials (AWS_PROFILE, or gcloud auth application-default login):
   dawnfix tick --config .dawnfix.yml --state "$(mktemp -d)/state.json" --baseline --dry-run
   Show stdout verbatim as JSON: it is the only thing that would ever be sent, and only with an
   Enterprise key. Point out it holds enums, counts, fingerprints and route templates only. Show the
   stderr summary line. Exit 1: report the source error codes, help fix credentials, stop here.
10. On my yes: git switch -c dawnfix/setup, add .dawnfix.yml, the workflow and CODEOWNERS if
   changed, commit, push the branch, gh pr create with a body listing sources, autonomy, variable
   and secret names (never values) and the dry-run JSON. Next steps for me: merge, then
   gh workflow run dawnfix.yml -f baseline=true so existing errors are recorded and only new ones
   are reported. After a week on diagnose, suggest draft-pr through another PR.
````
