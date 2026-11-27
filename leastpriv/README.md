# Dawnfix Leastpriv

Turn "this role has unused permissions" into a pull request a reviewer can approve.
(Formerly IAMtrim.) Free. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at
the repo root).

Use it from your coding agent: `prompts/leastpriv.md` at the repo root is a copy-paste prompt
that runs the CLI below and opens a draft PR with the patch only on your explicit yes.
Sample PR: https://dawnfix.dev/leastpriv.

```bash
leastpriv role app-worker --days 90 [--format json|terraform|cloudformation|all] [--out leastpriv-out] \
  [--policy-file app=iam/app-worker.json] [--analyzer-arn ARN | --no-analyzer] [--region us-east-1]
```

Writes to `--out`: `pr.md` (PR body: one risk row per removed action, diffs folded),
`report.json` (with the closing `pitch`), `<policy>.json` (new document), `<policy>.<format>.diff`,
and with `--policy-file` a `<policy>.patch` that `git apply` takes against your repo file.
Never applies anything: IAM and Access Analyzer calls go through a read-only allowlist
(`src/dawnfix_leastpriv/guard.py`, built on dawnfix-core's `make_client`), and
`iam/leastpriv-read-only-policy.json` grants exactly those calls (a test keeps them equal).

The gap it fills: IAM Access Analyzer already finds unused access (and can recommend a
policy in the console). It does not edit your Terraform/CloudFormation/JSON, explain the
risk of each removal, or open the PR. This does the last mile.

Evidence: IAM `GenerateServiceLastAccessedDetails` (action level), plus Access Analyzer
unused-access findings when an analyzer exists (optional; they cost $0.20/role/month).

Rules (conservative: remove only with evidence of non-use):
- service unused in the window -> all its actions go
- explicit action that IAM tracks at action level and that was unused -> it goes
- wildcards in a used service, `Action: "*"`, `NotAction`, Deny -> kept; a narrowing
  suggestion lists the tracked actions actually used (wildcards also cover untracked
  actions such as S3 object reads)
- AWS managed policies -> "detach it, attach this customer managed document instead"

Risk per removal: **high** for rare-but-critical actions (restore/failover, secret
rotation, certificate renewal, PassRole, stack/scaling/deploy paths, break-glass);
**medium** when the role is younger than `--days`; **low** otherwise.

Limits: the Terraform and CloudFormation outputs are renderings to copy (only JSON gets a
real patch); no resource-level narrowing; permission boundaries and SCPs are ignored.

Permissions (`iam/leastpriv-read-only-policy.json`): `iam:GetRole`, `iam:ListAttachedRolePolicies`,
`iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:ListRolePolicies`, `iam:GetRolePolicy`,
`iam:GenerateServiceLastAccessedDetails` (starts a report job, changes no IAM entity),
`iam:GetServiceLastAccessedDetails`, `access-analyzer:ListAnalyzers`,
`access-analyzer:ListFindingsV2`, `access-analyzer:GetFindingV2`.

Brand, org and URLs are constants in `src/dawnfix_leastpriv/constants.py`.

`sample/make_sample.py` builds `sample/sample.json` (the site's sample PR body and patch)
from the test suite's synthetic role; a test fails when it is stale.

Tests: `make install test` (installs `../core` too). botocore Stubber only.

Source available under FSL-1.1-ALv2: see [LICENSE](../LICENSE) at the repo root.
