# IAM for parity

| File | Attach to | Needed for |
|---|---|---|
| `parity-read-only-policy.json` | the role parity runs as, in every environment's account | `diff`, `check`, `inventory` (metadata only); `cloudtrail:LookupEvents` is used only with `--cloudtrail` and can be dropped |
| `parity-hash-mode-addon.json` | same role, only if you use `--compare-hashes` | reads values to hash them in memory; scope `Resource` to your prefixes |
| `github-oidc-trust-policy.json` | trust policy of that role | GitHub Actions OIDC; replace `ACCOUNT_ID`, `OWNER/REPO` |

The metadata policy grants no value-reading action: with it alone, parity physically
cannot read a parameter value or a secret. `ecs:DescribeTaskDefinition` and
`lambda:ListFunctions` do return plain (non-secret) environment values; parity drops
them unread unless `--compare-hashes` is set, and then keeps only a digest.

Cross-account (dev and prod in different accounts): give the CI role
`sts:AssumeRole` on each environment's parity role and set `role_arn` per environment
in `.parity.yml`.

Every API call the code can make is listed in `src/dawnfix_parity/aws.py`
(`READ_ONLY_OPERATIONS`); the client refuses anything else before the request is built.
`tests/test_guard.py` checks that these JSON files and that list agree.

## Trust: default branch only

`github-oidc-trust-policy.json` trusts exactly `repo:OWNER/REPO:ref:refs/heads/main`
(StringEquals). Do not add `repo:OWNER/REPO:pull_request` or wildcards: a pull request
can change the workflow it runs, so a PR-assumable role is a role anyone with push
access to a branch can use. Never attach `parity-hash-mode-addon.json` to a role that
PR tokens can assume. For tighter control, bind the job to a protected GitHub
Environment and trust `repo:OWNER/REPO:environment:<name>` instead.
