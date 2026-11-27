# Set up Dawnfix

Sets up Dawnfix in the current GitHub repo: `.dawnfix.yml`, a read-only AWS role or GCP
identity, a short `dawnfix.yml` workflow that calls the reusable one, repo variables, a dry
run and a setup PR. `npx dawnfix init` does the file part by itself; this prompt adds the
cloud role, the checks and the PR around it.

````text
Set up Dawnfix (github.com/dawnfix/dawnfix) in this GitHub repo. Work as a wizard: one step
at a time, show each command before you run it, and wait for my yes before anything that
writes (a cloud stack, a file, a repo variable, a commit, a PR).

Hard rules:
- Never ask me to paste a secret into this chat, and never print or echo one. That covers
  the Anthropic API key, the optional DAWNFIX_ENTERPRISE_KEY, PATs and cloud keys. I set secrets
  myself in my own terminal with `gh secret set NAME --repo <repo>` (gh asks without echo).
- The AWS role and the GCP identity must be read-only. If the read-only check fails, stop the
  cloud part and tell me which actions are the problem. Do not edit the policy to make it pass.
- Never push to the default branch. Everything lands through a PR I review.

Before step 1, tell me plainly what this costs me (Dawnfix itself is free, no key): my own
Anthropic tokens, only on runs that find a new error; GitHub Actions minutes (the hourly read
job is about a minute a run, ~750 a month; free on public repos); small CloudWatch API charges
(GetMetricData $0.01 per 1,000 metrics, for load balancer 5xx).

0. Tools: Node 20+ (for npx) and Python 3.11+. Install the Python CLI from PyPI:
   python3 -m venv "$HOME/.cache/dawnfix/venv" and "$HOME/.cache/dawnfix/venv/bin/pip" install dawnfix
   (use "dawnfix[gcp]" if GCP is involved). Call the binary `dawnfix`; `dawnfix --version` is
   the release, VERSION. Fetch the repo at that release for the infra files:
   git clone --quiet --branch vVERSION https://github.com/dawnfix/dawnfix "$HOME/.cache/dawnfix-src"
   (or fetch and check out vVERSION if it exists). Call it SRC. (Fallback without PyPI: pip
   install "dawnfix-core @ git+https://github.com/dawnfix/dawnfix@vVERSION#subdirectory=core";
   any git ref used this way, or as the workflow's core-ref, must be v0.2.0 or later: older
   refs have no prompts/ci/.)
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
5. Write the two files with `npx dawnfix init`, passing what we settled as flags, first with
   --dry-run so I see both files in full: --cloud aws|gcp, --aws-region, --log-group (repeat),
   --alarms, --aws-role-arn <RoleArn> or --gcp-project/--gcp-wif-provider, --autonomy diagnose,
   --test-command "<the confirmed command>", --install-command "<npm ci, pip install -e ., ...>".
   autonomy: diagnose to start (issues only); plan = an issue with the planned fix; draft-pr =
   failing test + fix as a draft PR, never merged. test.command: plain words only (no quotes,
   ; && | or $); leave it out if there are no tests (then issues only). On my yes, run it again
   with --yes instead of --dry-run. Then edit .dawnfix.yml if needed (SRC/templates/dawnfix.yml
   lists every key: alb, rules, limits): limits.fix_prs_per_day 3; ask if logs can hold health
   or other sensitive personal data: if yes, phi_mode: true, and tell me I need my own BAA with
   the model provider. Run `dawnfix validate --config .dawnfix.yml` until it passes.
6. The workflow init wrote is about 15 lines: it calls
   dawnfix/dawnfix/.github/workflows/dawnfix.yml@v0 (the jobs, their per-job permissions and
   the agent's instructions all come from that release). Keep `permissions` as written: the
   caller's are a ceiling and each job asks for less. Its cron must equal .dawnfix.yml's
   `schedule`. Pin @vVERSION or a commit SHA instead of @v0 if I want it frozen. (If I would
   rather keep the whole workflow in my repo: copy SRC/templates/github/workflows/dawnfix.yml
   instead; it reads repository variables, listed in its header, instead of inputs.)
7. Variables: only those the workflow reads (grep -oE '\$\{\{ *(vars|secrets)\.[A-Za-z0-9_]+'
   .github/workflows/dawnfix.yml | sort -u), e.g. DAWNFIX_AWS_ROLE_ARN when init was not given
   the role. Show them as a list, then set them on one yes with gh variable set NAME --repo
   <repo> --body <value>.
   Secrets, which I type in my terminal: gh secret set ANTHROPIC_API_KEY --repo <repo>. Optional:
   DAWNFIX_ENTERPRISE_KEY (Enterprise only: turns on hosted reporting at dawnfix.dev; without it nothing
   is sent anywhere; to set who gets the hosted digest, I run, in my own terminal,
   sh SRC/hosted/service.sh workspace --emails a@example.com,b@example.com). For plan or draft-pr, PRs made with GITHUB_TOKEN do not trigger CI: explain
   the options, a GitHub App I own (`pr-app-id:` under `with:` + secret DAWNFIX_PR_APP_PRIVATE_KEY
   passed under `secrets:`) or a fine-grained PAT (secret DAWNFIX_PR_TOKEN, passed under
   `secrets:`), Contents and Pull requests read/write on this repo only. Show `gh api repos/<repo>/actions/permissions/workflow` ("Allow GitHub Actions to create
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
   are reported. Then `npx dawnfix doctor` (config, pinned workflow, secret and variable names,
   Free or Enterprise). After a week on diagnose, suggest draft-pr through another PR.
````
