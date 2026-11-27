# Dawnfix Sweeper

After a migration or cutover, find what the old AWS stack left behind and write a teardown
**plan**: Markdown for the humans who run it, JSON for machines.
Each item has an estimated monthly cost and the exact delete command. The tool never deletes
anything: every AWS call goes through a read-only allowlist (`src/dawnfix_sweeper/guard.py`,
built on dawnfix-core's `make_client`), and `iam/sweeper-read-only-policy.json` grants
exactly those calls.

Free. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the repo root).

Install from PyPI: `pipx install dawnfix` (or `pip install dawnfix` in a venv). One package
holds every Dawnfix CLI (`dawnfix`, `logbill`, `parity`, `sweeper`, `leastpriv`, `receipt`,
`fleet`); `sweeper --version` prints the release. For development in this folder:
`make install test` (an editable install of this tool and `../core`).

Use it from your coding agent: `prompts/sweeper.md` at the repo root is a copy-paste prompt
that runs the CLI below and summarises the plan. Sample plan: https://dawnfix.dev/sweeper/sample.

```bash
sweeper scan --before-date 2026-09-01 --region us-east-1 --region eu-west-1 \
  [--tag stack=legacy] [--ip-ranges ip-ranges.json] [--prices my-prices.json] [--out plans/]
# -> plans/sweeper-plan.md, plans/sweeper-plan.json; exit 0, 2 if a collector failed, 3 if the guard refused a call
```

What it looks for (created or last active before `--before-date`):

| Kind | Rule | Action |
|---|---|---|
| Route 53 record | alias/CNAME to an ELB (v2 or classic) or Beanstalk name that no longer exists, or to one this plan deletes; with `--ip-ranges`, A/AAAA to AWS EC2 space this account no longer owns | delete / verify |
| ECS service | ACTIVE, desired count 0 | delete |
| Beanstalk environment | not terminated, last updated before the cutover (Green health -> verify) | delete / verify |
| Beanstalk application | every live environment is in the plan | delete |
| Load balancer (ALB/NLB/GWLB) | no attached target group has a healthy target (no TGs -> verify) | delete / verify |
| Classic ELB | no registered instance is InService | delete |
| Target group | zero registered targets (still on a kept LB -> verify) | delete / verify |
| NAT gateway | no `BytesOutToDestination` since the cutover (CloudWatch); no datapoints or metrics unreadable -> verify; its Elastic IPs are released after it | delete / verify |
| EC2 instance | stopped since before the cutover (stop time from `StateTransitionReason`); priced as its EBS volumes; names volumes that survive termination | verify |
| RDS instance | stopped, or available with peak `DatabaseConnections` 0 since the cutover; delete keeps a final snapshot; Aurora not checked | verify |
| RDS snapshot | manual, before the cutover; of a deleted database -> verify (may be the last copy) | delete / verify |
| AMI | own, not used by any instance (launch templates unchecked -> verify) | verify |
| Snapshot | own, before the cutover, not backing a kept AMI (AWS Backup/DLM -> verify) | delete / verify |
| EBS volume | `available` (attached to nothing) | delete, with an optional backup snapshot command |
| Elastic IP | not associated | delete |
| Log group | no event since the cutover | delete |

Commands come out in dependency order: DNS first (dangling names are a takeover risk),
consumers before what they consume, logs last. A database is never "delete" on metrics alone.

Not covered yet (heavier, or needs more than a Describe call to judge): CloudFront
distributions, S3 buckets and API Gateway stages behind dangling DNS; Aurora clusters and
cluster snapshots; launch templates and Auto Scaling groups (so AMIs stay "verify");
ElastiCache, OpenSearch, EKS; cross-account AMI sharing.

## Prices

`src/dawnfix_sweeper/prices.json` holds AWS on-demand list prices for 17 regions (the
ones Dawnfix Logbill covers) from the **AWS Price List bulk API**, the public,
unauthenticated offer files: AmazonEC2 (EBS, snapshots, NAT gateway, EC2 instance hours;
Beanstalk is priced as its EC2 and load balancers), AmazonVPC (public IPv4), AWSELB (ALB,
NLB, GWLB, classic), AmazonCloudWatch (log storage), AmazonRDS (MySQL/PostgreSQL Single-AZ
instance hours, gp2/gp3 storage, backup storage). Each entry names its offer and usage type;
`source.offers` has each offer's publication date (AmazonEC2 2026-10-27, AmazonRDS 2026-10-26,
AmazonVPC 2026-10-16, AmazonCloudWatch 2026-10-07, AWSELB 2026-09-11; retrieved 2026-10-28).
The tool never fetches prices at run time. Refresh (maintainers, network):

```bash
python3 -I tools/refresh_prices.py fetch /tmp/raw          # streams ~300 MB CSV for AmazonEC2 us-east-1, less elsewhere
python3 -I tools/refresh_prices.py build /tmp/raw > src/dawnfix_sweeper/prices.json
```

Still estimated by rule, not by a price: Multi-AZ RDS is counted as twice Single-AZ;
snapshot sizes are upper bounds (billing is incremental); RDS engines other than MySQL,
MariaDB (priced as MySQL) and PostgreSQL are left unpriced; a region outside the 17 is priced
at us-east-1 and the plan says so. Never included: Savings Plans, reserved capacity, credits,
free tier, LCU and data charges.

## Permissions

`iam/sweeper-read-only-policy.json` (a test keeps it equal to the guard's allowlist):
`ec2:Describe{Volumes,Addresses,Snapshots,Images,Instances,NatGateways}`,
`elasticloadbalancing:Describe{LoadBalancers,TargetGroups,TargetHealth,Tags,InstanceHealth}`,
`elasticbeanstalk:Describe{Environments,Applications,EnvironmentResources}`,
`elasticbeanstalk:ListTagsForResource`, `ecs:ListClusters`, `ecs:ListServices`, `ecs:DescribeServices`,
`rds:DescribeDBInstances`, `rds:DescribeDBSnapshots`, `cloudwatch:GetMetricData`,
`route53:ListHostedZones`, `route53:ListResourceRecordSets`, `logs:DescribeLogGroups`,
`logs:DescribeLogStreams`, `logs:ListTagsForResource` (`sts:GetCallerIdentity` needs no
permission). `ReadOnlyAccess` covers it. `GetMetricData` costs about $0.01 per 1,000 metrics:
one call per region for NAT gateways and one for RDS.

Brand, org and URLs are constants in `src/dawnfix_sweeper/constants.py`, including
the closing pitch (`plan.json` -> `pitch`): one line about Dawnfix Receipt, free in your
own CI (`templates/github/workflows/dawnfix-receipt.yml`).

`sample/make_sample.py` builds `sample/sample.json` (the site's sample plan) from the test
suite's synthetic worlds; a test fails when it is stale.

Tests: `make install test` (installs `../core` too). botocore Stubber only; no AWS calls.

Source available under FSL-1.1-ALv2: see [LICENSE](../LICENSE) at the repo root.
