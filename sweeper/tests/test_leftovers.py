"""The cheap, high-value leftovers: stopped EC2, idle NAT gateways, classic ELBs, idle RDS and old RDS snapshots."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from botocore.stub import ANY

from dawnfix_sweeper import cli
from dawnfix_sweeper.guard import READ_ONLY_OPERATIONS, ReadOnlyViolation, iam_actions, make_client
from dawnfix_sweeper.pricing import Prices
from dawnfix_sweeper.scan import Scanner
from tests.conftest import activate

ROOT = Path(__file__).resolve().parent.parent
BEFORE = datetime(2026, 9, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
R = "us-east-1"


def d(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def empty_rest(st):
    """Every other collector finds nothing."""
    st["sts"].add_response("get_caller_identity", {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:role/r",
                                                   "UserId": "AID"})


def world(st, cw_error=False):
    empty_rest(st)
    st["ec2"].add_response("describe_instances", {"Reservations": [{"Instances": [
        {"InstanceId": "i-stopped", "InstanceType": "t3.large", "ImageId": "ami-x", "State": {"Name": "stopped"},
         "StateTransitionReason": "User initiated (2026-08-01 10:00:00 GMT)", "LaunchTime": d("2025-01-01"),
         "Tags": [{"Key": "Name", "Value": "old-worker"}]},
        {"InstanceId": "i-stopped-new", "InstanceType": "t3.large", "State": {"Name": "stopped"},
         "StateTransitionReason": "User initiated (2026-10-01 10:00:00 GMT)", "LaunchTime": d("2025-01-01")},
        {"InstanceId": "i-running", "InstanceType": "t3.large", "State": {"Name": "running"}},
    ]}]})
    st["ec2"].add_response("describe_volumes", {"Volumes": [
        {"VolumeId": "vol-root", "VolumeType": "gp3", "Size": 50, "State": "in-use",
         "Attachments": [{"InstanceId": "i-stopped", "DeleteOnTermination": True}]},
        {"VolumeId": "vol-data", "VolumeType": "gp2", "Size": 200, "State": "in-use",
         "Attachments": [{"InstanceId": "i-stopped", "DeleteOnTermination": False}]},
    ]}, {"Filters": [{"Name": "attachment.instance-id", "Values": ["i-stopped"]}]})
    st["ec2"].add_response("describe_addresses", {"Addresses": []})
    st["ec2"].add_response("describe_volumes", {"Volumes": []}, {"Filters": [{"Name": "status", "Values": ["available"]}]})
    st["ec2"].add_response("describe_images", {"Images": []}, {"Owners": ["self"]})
    st["ec2"].add_response("describe_snapshots", {"Snapshots": []}, {"OwnerIds": ["self"]})
    st["ec2"].add_response("describe_nat_gateways", {"NatGateways": [
        {"NatGatewayId": "nat-idle", "State": "available", "CreateTime": d("2026-03-01"),
         "NatGatewayAddresses": [{"AllocationId": "eipalloc-nat", "PublicIp": "54.0.0.1"}]},
        {"NatGatewayId": "nat-busy", "State": "available", "CreateTime": d("2026-03-01"),
         "NatGatewayAddresses": [{"AllocationId": "eipalloc-busy", "PublicIp": "54.0.0.2"}]},
        {"NatGatewayId": "nat-new", "State": "available", "CreateTime": d("2026-10-01")},
    ]}, {"Filter": [{"Name": "state", "Values": ["available"]}]})
    if cw_error:
        st["cloudwatch"].add_client_error("get_metric_data", "AccessDenied", "no")
    else:
        st["cloudwatch"].add_response("get_metric_data", {"MetricDataResults": [
            {"Id": "m0", "Values": [0.0, 0.0, 0.0], "StatusCode": "Complete"},
            {"Id": "m1", "Values": [5e9, 4e9], "StatusCode": "Complete"},
        ]}, {"MetricDataQueries": ANY, "StartTime": BEFORE, "EndTime": NOW, "ScanBy": "TimestampAscending"})
    st["elbv2"].add_response("describe_load_balancers", {"LoadBalancers": []})
    st["elbv2"].add_response("describe_target_groups", {"TargetGroups": []})
    st["elb"].add_response("describe_load_balancers", {"LoadBalancerDescriptions": [
        {"LoadBalancerName": "legacy-clb", "DNSName": "legacy-clb-1.us-east-1.elb.amazonaws.com",
         "CreatedTime": d("2024-01-01"), "Scheme": "internet-facing", "AvailabilityZones": ["us-east-1a", "us-east-1b"],
         "Instances": [{"InstanceId": "i-gone"}]},
        {"LoadBalancerName": "live-clb", "DNSName": "live-clb-2.us-east-1.elb.amazonaws.com",
         "CreatedTime": d("2024-01-01"), "Scheme": "internal", "AvailabilityZones": ["us-east-1a"],
         "Instances": [{"InstanceId": "i-running"}]},
    ]})
    st["elb"].add_response("describe_instance_health", {"InstanceStates": [
        {"InstanceId": "i-gone", "State": "OutOfService"}]}, {"LoadBalancerName": "legacy-clb"})
    st["elb"].add_response("describe_instance_health", {"InstanceStates": [
        {"InstanceId": "i-running", "State": "InService"}]}, {"LoadBalancerName": "live-clb"})
    st["elasticbeanstalk"].add_response("describe_environments", {"Environments": []}, {"IncludeDeleted": False})
    st["elasticbeanstalk"].add_response("describe_applications", {"Applications": []})
    st["ecs"].add_response("list_clusters", {"clusterArns": []})
    st["rds"].add_response("describe_db_instances", {"DBInstances": [
        {"DBInstanceIdentifier": "legacy-db", "DBInstanceClass": "db.t3.medium", "Engine": "postgres",
         "DBInstanceStatus": "available", "InstanceCreateTime": d("2025-01-01"), "AllocatedStorage": 100,
         "StorageType": "gp3", "MultiAZ": False, "DeletionProtection": True},
        {"DBInstanceIdentifier": "stopped-db", "DBInstanceClass": "db.m5.large", "Engine": "mysql",
         "DBInstanceStatus": "stopped", "InstanceCreateTime": d("2025-01-01"), "AllocatedStorage": 50,
         "StorageType": "gp2", "MultiAZ": True},
        {"DBInstanceIdentifier": "live-db", "DBInstanceClass": "db.t3.medium", "Engine": "postgres",
         "DBInstanceStatus": "available", "InstanceCreateTime": d("2025-01-01"), "AllocatedStorage": 20,
         "StorageType": "gp3"},
        {"DBInstanceIdentifier": "aurora-1", "DBInstanceClass": "db.r6g.large", "Engine": "aurora-postgresql",
         "DBInstanceStatus": "available", "DBClusterIdentifier": "c1", "InstanceCreateTime": d("2025-01-01")},
    ]})
    if cw_error:
        st["cloudwatch"].add_client_error("get_metric_data", "AccessDenied", "no")
    else:
        st["cloudwatch"].add_response("get_metric_data", {"MetricDataResults": [
            {"Id": "m0", "Values": [0.0, 0.0], "StatusCode": "Complete"},
            {"Id": "m1", "Values": [3.0, 12.0], "StatusCode": "Complete"},
        ]}, {"MetricDataQueries": ANY, "StartTime": BEFORE, "EndTime": NOW, "ScanBy": "TimestampAscending"})
    st["rds"].add_response("describe_db_snapshots", {"DBSnapshots": [
        {"DBSnapshotIdentifier": "pre-migration", "DBInstanceIdentifier": "live-db", "AllocatedStorage": 20,
         "SnapshotCreateTime": d("2026-08-15"), "SnapshotType": "manual"},
        {"DBSnapshotIdentifier": "orphan-final", "DBInstanceIdentifier": "deleted-db", "AllocatedStorage": 500,
         "SnapshotCreateTime": d("2026-05-01"), "SnapshotType": "manual"},
        {"DBSnapshotIdentifier": "after-cutover", "DBInstanceIdentifier": "live-db", "AllocatedStorage": 20,
         "SnapshotCreateTime": d("2026-10-01"), "SnapshotType": "manual"},
    ]}, {"SnapshotType": "manual"})
    st["logs"].add_response("describe_log_groups", {"logGroups": []})
    st["route53"].add_response("list_hosted_zones", {"HostedZones": [
        {"Id": "/hostedzone/Z1", "Name": "example.com.", "CallerReference": "c"}], "IsTruncated": False,
        "Marker": "", "MaxItems": "100"})
    st["route53"].add_response("list_resource_record_sets", {"ResourceRecordSets": [
        {"Name": "legacy.example.com.", "Type": "CNAME", "TTL": 60,
         "ResourceRecords": [{"Value": "legacy-clb-1.us-east-1.elb.amazonaws.com"}]},
        {"Name": "live.example.com.", "Type": "CNAME", "TTL": 60,
         "ResourceRecords": [{"Value": "live-clb-2.us-east-1.elb.amazonaws.com"}]},
    ], "IsTruncated": False, "MaxItems": "300"}, {"HostedZoneId": "Z1"})


def scan(clients, session):
    return Scanner(session, [R], BEFORE, {}, Prices.load(), None, clients=clients, now=NOW).run()


def test_new_leftovers(stubs, session):
    clients, st = stubs
    world(st)
    activate(st)
    res = scan(clients, session)
    for s in st.values():
        s.assert_no_pending_responses()
    items = {i.id: i for i in res["items"]}
    assert res["errors"] == []
    assert set(items) == {"i-stopped", "nat-idle", "legacy-clb", "legacy-db", "stopped-db", "pre-migration",
                          "orphan-final", "Z1/legacy.example.com./CNAME"}
    p = Prices.load().region(R)
    # stopped instance: EBS only, verify, and the volume that survives termination is named
    inst = items["i-stopped"]
    assert inst.action == "verify" and inst.monthly_usd == pytest.approx(50 * 0.08 + 200 * 0.10)
    assert "vol-data survive termination" in inst.reason
    assert inst.commands == ["aws ec2 terminate-instances --instance-ids i-stopped --region us-east-1"]
    assert inst.backup_commands[0].startswith("aws ec2 create-image --instance-id i-stopped")
    # idle NAT: hourly + its public IPv4, delete then release its EIP
    nat = items["nat-idle"]
    assert nat.action == "delete" and nat.monthly_usd == pytest.approx((0.045 + 0.005) * 730)
    assert nat.commands == ["aws ec2 delete-nat-gateway --nat-gateway-id nat-idle --region us-east-1",
                            "aws ec2 release-address --allocation-id eipalloc-nat --region us-east-1"]
    # classic ELB with nothing InService, and the record pointing at it goes first
    clb = items["legacy-clb"]
    assert clb.monthly_usd == pytest.approx(0.025 * 730 + 2 * 0.005 * 730)
    assert clb.commands == ["aws elb delete-load-balancer --load-balancer-name legacy-clb --region us-east-1"]
    rec = items["Z1/legacy.example.com./CNAME"]
    assert rec.action == "verify" and rec.depends_on == ["legacy-clb"]
    # RDS: idle (no connections) priced compute + storage; stopped priced storage only (Multi-AZ x2)
    db = items["legacy-db"]
    assert db.action == "verify" and "deletion protection" in db.reason
    assert db.monthly_usd == pytest.approx(p.get("rds_hour.postgres.db.t3.medium") * 730 + 100 * 0.115)
    assert db.commands[0].endswith("--final-db-snapshot-identifier legacy-db-final-20261027 --region us-east-1")
    assert items["stopped-db"].monthly_usd == pytest.approx(50 * 0.115 * 2)
    assert "7 days" in items["stopped-db"].reason
    assert items["pre-migration"].action == "delete"
    assert items["orphan-final"].action == "verify" and "last copy" in items["orphan-final"].reason
    assert items["orphan-final"].monthly_usd == pytest.approx(500 * 0.095)
    assert any("Aurora" in n for n in res["notes"])
    # phase order
    order = [i.kind for i in res["items"]]
    assert order.index("route53_record") < order.index("classic_elb") < order.index("nat_gateway") \
        < order.index("ec2_instance") < order.index("rds_instance") < order.index("rds_snapshot")


def test_metrics_failure_is_reported_never_guessed(stubs, session):
    clients, st = stubs
    world(st, cw_error=True)
    activate(st)
    res = scan(clients, session)
    items = {i.id: i for i in res["items"]}
    assert {"collector": "nat_gateway_traffic", "region": R, "error_code": "AccessDenied"} in res["errors"]
    assert {"collector": "rds_connections", "region": R, "error_code": "AccessDenied"} in res["errors"]
    # unknown traffic: both NATs become "verify"; an available database is never listed without evidence
    assert items["nat-idle"].action == "verify" and items["nat-busy"].action == "verify"
    assert "legacy-db" not in items and "stopped-db" in items


def test_regional_prices_and_fallback():
    prices = Prices.load()
    assert prices.region("eu-central-1").get("ebs_gb_month.gp3") > prices.region("us-east-1").get("ebs_gb_month.gp3")
    assert prices.region("mars-north-1").get("ebs_gb_month.gp3") == prices.region("us-east-1").get("ebs_gb_month.gp3")
    meta = prices.meta()
    assert set(meta["publication_dates"]) == {"AmazonEC2", "AmazonVPC", "AWSELB", "AmazonCloudWatch", "AmazonRDS"}
    assert all(u.startswith("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/") for u in meta["sources"])
    assert len(prices.regions) == 17
    doc = json.loads((ROOT / "src" / "dawnfix_sweeper" / "prices.json").read_text())
    for key, entry in doc["prices"].items():
        assert entry.get("offer") and entry.get("usage_type"), key
        assert R in entry["regions"], key


def test_unpriced_region_is_noted(stubs, session):
    clients, st = stubs
    st["sts"].add_response("get_caller_identity", {"Account": "1", "Arn": "arn:aws:iam::1:role/r", "UserId": "A"})
    activate(st)
    s = Scanner(session, ["mars-north-1"], BEFORE, {}, Prices.load(), None,
                clients={("sts", "mars-north-1"): clients[("sts", R)]}, now=NOW)
    s._safe = lambda *a: None  # no collector runs: only the note matters here
    res = s.run()
    assert any("mars-north-1 is not in the price table" in n for n in res["notes"])


def test_iam_policy_is_exactly_the_allowlist():
    doc = json.loads((ROOT / "iam" / "sweeper-read-only-policy.json").read_text())
    acts = {a for st in doc["Statement"] for a in st["Action"]}
    assert acts == iam_actions()
    for a in acts:
        verb = a.split(":")[1]
        assert verb.startswith(("Describe", "Get", "List")), a
    assert "cloudwatch:GetMetricData" in acts and "rds:DescribeDBSnapshots" in acts


def test_guard_refuses_unknown_service_and_writes(session):
    with pytest.raises(ReadOnlyViolation):
        make_client(session, "s3", R)
    for service, op, kw in [("rds", "delete_db_instance", {"DBInstanceIdentifier": "x"}),
                            ("elb", "delete_load_balancer", {"LoadBalancerName": "x"}),
                            ("ec2", "delete_nat_gateway", {"NatGatewayId": "nat-1"}),
                            ("cloudwatch", "put_metric_data", {"Namespace": "x", "MetricData": []})]:
        assert op not in {o.lower() for o in READ_ONLY_OPERATIONS[service]}
        with pytest.raises(ReadOnlyViolation):
            getattr(make_client(session, service, R), op)(**kw)


def test_plan_carries_the_pitch(stubs, session, tmp_path):
    clients, st = stubs
    world(st)
    activate(st)
    args = cli.parser().parse_args(["scan", "--before-date", "2026-09-01", "--region", R, "--out", str(tmp_path)])
    assert cli.cmd_scan(args, session=session, clients=clients, now=NOW) == 0
    doc = json.loads((tmp_path / "sweeper-plan.json").read_text())
    assert doc["pitch"]["url"].endswith("/receipt")
    assert doc["pitch"]["line"].startswith(f"You're paying about ${doc['summary']['monthly_usd_total']:,.0f}/month")
    assert "Dawnfix Receipt" in doc["pitch"]["line"]
    assert "dawnfix-receipt.yml" in doc["pitch"]["line"]
    for gone in ("Solo", "paid", "plan,", "from $"):
        assert gone not in doc["pitch"]["line"]


def test_licence_is_fsl_at_the_repo_root():
    assert not (ROOT / "LICENSE").exists()
    assert "Functional Source License" in (ROOT.parent / "LICENSE").read_text()
    assert 'license = "FSL-1.1-ALv2"' in (ROOT / "pyproject.toml").read_text()
