# AWS: read-only role for Dawnfix

`dawnfix-read-role.yaml` creates one IAM role that the dawnfix workflow of **one GitHub
repository** can assume through GitHub OIDC. No access keys exist anywhere.

| What | Value |
|---|---|
| Trust | `token.actions.githubusercontent.com`, `aud = sts.amazonaws.com`, `sub = repo:ORG/REPO:ref:refs/heads/BRANCH` (or `repo:ORG/REPO:environment:NAME` when `Environment` is set). Exact match, no wildcards |
| Logs | `FilterLogEvents`, `GetLogEvents`, `StartQuery` on log groups matching `LogGroupPrefix` (default `*`); `Describe*`, `StopQuery`, `GetQueryResults` on `*` |
| CloudWatch | `DescribeAlarms`, `GetMetricData`, `GetMetricStatistics`, `ListMetrics` |
| ELB | `DescribeLoadBalancers`, `DescribeTargetGroups`, `DescribeTargetHealth` |
| Session | `MaxSessionDuration` 3600 s; the workflow asks for 900 s |
| Output | `RoleArn`: put it in the repo variable `DAWNFIX_AWS_ROLE_ARN` and in `role:` of `.dawnfix.yml` |

Nothing else: no S3, no Secrets Manager, no SSM, no writes of any kind.

## One OIDC provider per account

An AWS account can hold only one IAM OIDC provider for `token.actions.githubusercontent.com`.
Check first:

```sh
aws iam list-open-id-connect-providers \
  --query "OpenIDConnectProviderList[?ends_with(Arn, '/token.actions.githubusercontent.com')].Arn" --output text
```

- Nothing printed: keep `CreateOIDCProvider=true`.
- An ARN printed: set `CreateOIDCProvider=false` and `ExistingOIDCProviderArn=<that ARN>`. The
  stack refuses to create otherwise (template `Rules`). Its client ID list must contain
  `sts.amazonaws.com` (the default for providers made for configure-aws-credentials).

Deleting a stack that created the provider deletes the provider, which breaks every other
role in the account that trusts it. Stacks for further repos should use `false`.

## Deploy with the CLI

```sh
aws cloudformation deploy \
  --template-file infra/aws/dawnfix-read-role.yaml \
  --stack-name dawnfix-read-my-app \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      GitHubOrg=example-org GitHubRepo=my-app Branch=main \
      CreateOIDCProvider=true RoleName=dawnfix-read-my-app LogGroupPrefix='*'

aws cloudformation describe-stacks --stack-name dawnfix-read-my-app \
  --query "Stacks[0].Outputs[?OutputKey=='RoleArn'].OutputValue" --output text
```

## Verify it is read-only

`verify_readonly.py` is what the wizard runs (with the customer's own admin credentials, not
the role's) before it accepts a role, including roles the customer made by hand:

```sh
python infra/aws/verify_readonly.py arn:aws:iam::123456789012:role/dawnfix-read-my-app \
  --log-group my-api-prod --region us-east-1 [--aws-profile admin] [--json]
```

1. `iam:SimulatePrincipalPolicy` (counts permission boundaries and SCPs): a fixed list of
   writes and secret reads (`logs:DeleteLogGroup`, `logs:PutLogEvents`,
   `cloudwatch:PutMetricAlarm`, a sample of `iam:*`, `s3:PutObject`, `s3:GetObject`,
   `ec2:TerminateInstances`, `secretsmanager:GetSecretValue`, ...) must be denied, against
   `*` and against each `--log-group`; the five operations dawnfix-core calls must be allowed.
2. Policy scan: every `Allow` in the role's inline and attached policies must stay inside
   `logs:Describe*/Get*/List*/FilterLogEvents/StartQuery/StopQuery`, `cloudwatch:Describe*/Get*/List*`,
   `elasticloadbalancing:Describe*`. The simulator compares resources literally, so a grant of
   `s3:PutObject` on one bucket is invisible against `*`; the scan catches it. `NotAction` is refused.
3. Trust: a GitHub OIDC statement must pin `aud` and a `sub` naming one repository.

Exit 0 = accepted, 1 = refused (the report says why), 2 = bad ARN or AWS error. The caller
needs `iam:SimulatePrincipalPolicy`, `iam:GetRole`, `iam:ListRolePolicies`,
`iam:GetRolePolicy`, `iam:ListAttachedRolePolicies`, `iam:GetPolicy`, `iam:GetPolicyVersion`.


### Role profiles

`--profile` says which role is being checked (`--aws-profile` is the caller's credentials):

- `dawnfix` (default): the error-log read role above.
- `fleet`: the agency board's per-client read role. Required (and the only grants allowed):
  `cloudwatch:DescribeAlarms`, `acm:ListCertificates`, `acm:DescribeCertificate`,
  `ce:GetCostAndUsage` — exactly what the board's collector calls (`fleet/infra/tests/test_verify_profile.py`
  holds the two lists equal). Any wildcard or other action fails the policy scan; log, metric
  and certificate-export actions must be denied; a cross-account trust must carry an exact
  `sts:ExternalId` condition. `--log-group` is ignored.

```sh
python infra/aws/verify_readonly.py arn:aws:iam::123456789012:role/fleet-read --profile fleet [--aws-profile admin]
```

An older `--profile <aws profile>` that is not a role profile name still works as
`--aws-profile`, with a note on stderr.

## Tests

No AWS account is touched; IAM is stubbed with botocore `Stubber`, and the template is
checked structurally with a CloudFormation-aware YAML loader (refs, conditions, `Fn::Sub`
variables, patterns, the exact action set, and that the template passes the verifier's scan).

```sh
core/.venv/bin/pytest -q infra/tests
```

`cfn-lint` and `aws cloudformation validate-template` have not been run on this template yet.
