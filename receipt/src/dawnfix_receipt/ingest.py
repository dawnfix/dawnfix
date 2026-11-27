"""The counts-only document the CI workflow sends to the hosted service with an Enterprise key
(`dawnfix.receipt/1`).

What leaves the customer's runner, per deploy, and nothing else (schema/receipt-ingest.schema.json):

- ``deploy_id``: 16 hex of SHA-256 over a fixed prefix and the commit SHA. An id for
  "this deploy again" across the daily re-runs, not a secret and not the SHA.
- ``deployed_on``: the UTC day of the deploy.
- ``window_days``, ``after_days``, ``final``: how complete the comparison is
  (provisional until every after-day has settled in Cost Explorer).
- ``material``: whether the change cleared the noise floor.
- ``delta_cents_per_day_bucket``: the signed $/day change, in cents, snapped down to a
  1-2-5 grid (+2000 means "+$20 to +$50 a day"). Never the before or after totals, so the
  hosted service cannot reconstruct the size of the AWS bill.
- ``top_driver``: the AWS service that moved most, as a closed enum of AWS product
  families (``DRIVERS``) or ``other``/``none``. These are AWS's catalogue names, not the
  customer's data: no usage type (they carry regions and instance sizes), no tag key or
  value (customer-defined), no resource, account or repo name.

The repo travels only as the X-Dawnfix-Repo header the workflow sets, as for Parity and Flare.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "dawnfix.receipt/1"
MAX_DEPLOYS = 50
# 1-2-5 grid in cents: 0, $1, $2, $5, $10, ... $5,000,000 a day.
BUCKETS = [0] + [m * 10 ** e for e in range(2, 9) for m in (1, 2, 5)]
# Cost Explorer SERVICE dimension value (regex) -> driver enum. First match wins.
DRIVERS: list[tuple[str, str]] = [
    (r"^Amazon Elastic Compute Cloud - Compute$", "ec2_compute"),
    (r"^EC2 - Other$", "ec2_other"),
    (r"^Amazon Relational Database Service$", "rds"),
    (r"^Amazon Aurora", "rds"),
    (r"^Amazon Simple Storage Service$", "s3"),
    (r"^AmazonCloudWatch$|^Amazon CloudWatch", "cloudwatch"),
    (r"^AWS Lambda$", "lambda"),
    (r"^Amazon Elastic Load Balancing$|^Elastic Load Balancing", "elb"),
    (r"^Amazon Elastic Container Service", "ecs"),
    (r"^Amazon Elastic Kubernetes Service$", "eks"),
    (r"^Amazon DynamoDB$", "dynamodb"),
    (r"^Amazon CloudFront$", "cloudfront"),
    (r"^AWS Data Transfer$|^Data Transfer", "data_transfer"),
    (r"^Amazon Virtual Private Cloud$", "vpc"),
    (r"^Amazon ElastiCache$", "elasticache"),
    (r"^Amazon OpenSearch Service$", "opensearch"),
    (r"^Amazon Simple Queue Service$", "sqs"),
    (r"^Amazon Kinesis", "kinesis"),
    (r"^AWS Key Management Service$", "kms"),
    (r"^AWS Secrets Manager$", "secrets_manager"),
    (r"^Amazon Route 53$", "route53"),
    (r"^Amazon EC2 Container Registry \(ECR\)$|^Amazon Elastic Container Registry", "ecr"),
    (r"^AWS Step Functions$", "step_functions"),
    (r"^Amazon API Gateway$", "api_gateway"),
    (r"^Amazon Bedrock|^Claude", "bedrock"),
    (r"^Amazon SageMaker$", "sagemaker"),
]
DRIVER_ENUM = sorted({d for _, d in DRIVERS} | {"other", "none"})


def deploy_id(sha: str) -> str:
    return hashlib.sha256(f"{SCHEMA}:{sha.strip().lower()}".encode()).hexdigest()[:16]


def bucket(delta_usd_per_day: float) -> int:
    """Signed cents snapped down (toward zero) to the 1-2-5 grid."""
    cents = abs(round(delta_usd_per_day * 100))
    b = max(x for x in BUCKETS if x <= cents) if cents >= BUCKETS[1] else 0
    return -b if delta_usd_per_day < 0 and b else b


def driver(service: str) -> str:
    for pattern, name in DRIVERS:
        if re.search(pattern, service):
            return name
    return "other"


def deploy_entry(result) -> dict:
    """One deploy from a receipt.Result: counts and enums only."""
    p = result.plan
    top = "none"
    if p.after_days and result.material:
        d = result.drivers()
        if d:
            top = driver(d[0].key.partition(" | ")[0])
    return {
        "deploy_id": deploy_id(result.sha),
        "deployed_on": p.deploy_day.isoformat(),
        "window_days": p.window,
        "after_days": len(p.after_days),
        "final": p.final,
        "material": bool(p.after_days) and result.material,
        "delta_cents_per_day_bucket": bucket(result.delta) if p.after_days else 0,
        "top_driver": top,
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(path: str | Path, result, now: datetime | None = None) -> dict:
    """Add this deploy to the document at `path` (created if missing), replacing an older entry
    for the same deploy, so a loop over recent deploys builds one document for one POST."""
    path = Path(path)
    doc = None
    if path.exists():
        try:
            doc = json.loads(path.read_text())
        except ValueError:
            doc = None
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            doc = None
    entry = deploy_entry(result)
    deploys = [d for d in (doc or {}).get("deploys", []) if d.get("deploy_id") != entry["deploy_id"]]
    deploys.append(entry)
    deploys.sort(key=lambda d: (d["deployed_on"], d["deploy_id"]))
    stamp = (now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if now else _now())
    out = {"schema": SCHEMA, "generated_at": stamp, "deploys": deploys[-MAX_DEPLOYS:]}
    path.write_text(json.dumps(out, indent=2) + "\n")
    return out
