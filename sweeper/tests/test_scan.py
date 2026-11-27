import json
from datetime import datetime, timezone

import pytest
from botocore.stub import ANY

from dawnfix_sweeper import cli
from dawnfix_sweeper import plan as pl
from dawnfix_sweeper.guard import ReadOnlyViolation, make_client
from dawnfix_sweeper.pricing import Prices
from dawnfix_sweeper.scan import Scanner, parse_tag_filters
from tests.conftest import activate

BEFORE = datetime(2026, 9, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
ACCT = "123456789012"
R = "us-east-1"
LB_OLD = f"arn:aws:elasticloadbalancing:{R}:{ACCT}:loadbalancer/app/old-lb/1111111111111111"
LB_LIVE = f"arn:aws:elasticloadbalancing:{R}:{ACCT}:loadbalancer/app/new-lb/2222222222222222"
TG_OLD = f"arn:aws:elasticloadbalancing:{R}:{ACCT}:targetgroup/old-tg/aaaaaaaaaaaaaaaa"
TG_LIVE = f"arn:aws:elasticloadbalancing:{R}:{ACCT}:targetgroup/new-tg/bbbbbbbbbbbbbbbb"
TG_EMPTY = f"arn:aws:elasticloadbalancing:{R}:{ACCT}:targetgroup/empty-tg/cccccccccccccccc"


def d(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def ms(s):
    return int(d(s).timestamp() * 1000)


def lb(arn, name, created, dns):
    return {"LoadBalancerArn": arn, "LoadBalancerName": name, "DNSName": dns, "CreatedTime": d(created),
            "Scheme": "internet-facing", "Type": "application",
            "AvailabilityZones": [{"ZoneName": "us-east-1a"}, {"ZoneName": "us-east-1b"}]}


def tg(arn, name, lbs):
    return {"TargetGroupArn": arn, "TargetGroupName": name, "LoadBalancerArns": lbs}


def world(stubs, tags_on_volume=None, tagged=False, logs_error=False):
    """One region where a Beanstalk stack was replaced on 2026-09-01 by something new."""
    st = stubs
    st["sts"].add_response("get_caller_identity", {"Account": ACCT, "Arn": "arn:aws:iam::123456789012:role/r",
                                                   "UserId": "AID"})
    # EC2
    st["ec2"].add_response("describe_instances", {"Reservations": [{"Instances": [
        {"InstanceId": "i-eb1", "InstanceType": "t3.small", "ImageId": "ami-used",
         "State": {"Name": "running"}, "PublicIpAddress": "3.3.3.3"},
        {"InstanceId": "i-dead", "InstanceType": "t3.small", "ImageId": "ami-old", "State": {"Name": "terminated"}},
    ]}]})
    st["ec2"].add_response("describe_addresses", {"Addresses": [
        {"AllocationId": "eipalloc-free", "PublicIp": "52.0.0.1", "Domain": "vpc"},
        {"AllocationId": "eipalloc-used", "PublicIp": "52.0.0.2", "AssociationId": "eipassoc-1", "Domain": "vpc"},
    ]})
    st["ec2"].add_response("describe_volumes", {"Volumes": [
        {"VolumeId": "vol-old", "VolumeType": "gp3", "Size": 100, "Iops": 3000, "Throughput": 125,
         "CreateTime": d("2026-06-01"), "State": "available",
         "Tags": [{"Key": k, "Value": v} for k, v in (tags_on_volume or {"Name": "old-db-data"}).items()]},
        {"VolumeId": "vol-new", "VolumeType": "gp3", "Size": 20, "CreateTime": d("2026-09-15"), "State": "available"},
    ]}, {"Filters": [{"Name": "status", "Values": ["available"]}]})
    st["ec2"].add_response("describe_images", {"Images": [
        {"ImageId": "ami-old", "Name": "legacy-app-2026-05", "CreationDate": "2026-05-01T00:00:00.000Z",
         "BlockDeviceMappings": [{"DeviceName": "/dev/xvda", "Ebs": {"SnapshotId": "snap-ami"}}]},
        {"ImageId": "ami-used", "Name": "base", "CreationDate": "2026-01-01T00:00:00.000Z",
         "BlockDeviceMappings": [{"DeviceName": "/dev/xvda", "Ebs": {"SnapshotId": "snap-kept"}}]},
    ]}, {"Owners": ["self"]})
    st["ec2"].add_response("describe_snapshots", {"Snapshots": [
        {"SnapshotId": "snap-ami", "VolumeSize": 8, "StartTime": d("2026-05-01"), "FullSnapshotSizeInBytes": 4_000_000_000},
        {"SnapshotId": "snap-old", "VolumeSize": 50, "StartTime": d("2026-04-01"), "Description": "pre-migration backup"},
        {"SnapshotId": "snap-kept", "VolumeSize": 8, "StartTime": d("2026-01-01")},
        {"SnapshotId": "snap-new", "VolumeSize": 8, "StartTime": d("2026-10-01")},
        {"SnapshotId": "snap-backup", "VolumeSize": 10, "StartTime": d("2026-03-01"),
         "Description": "This snapshot is created by the AWS Backup service."},
    ]}, {"OwnerIds": ["self"]})
    st["ec2"].add_response("describe_nat_gateways", {"NatGateways": []},
                           {"Filter": [{"Name": "state", "Values": ["available"]}]})
    # ELBv2
    st["elbv2"].add_response("describe_load_balancers", {"LoadBalancers": [
        lb(LB_OLD, "old-lb", "2026-03-01", "old-lb-111.us-east-1.elb.amazonaws.com"),
        lb(LB_LIVE, "new-lb", "2026-08-20", "new-lb-222.us-east-1.elb.amazonaws.com"),
    ]})
    st["elbv2"].add_response("describe_target_groups", {"TargetGroups": [
        tg(TG_OLD, "old-tg", [LB_OLD]), tg(TG_LIVE, "new-tg", [LB_LIVE]), tg(TG_EMPTY, "empty-tg", []),
    ]})
    if tagged:
        st["elbv2"].add_response("describe_tags", {"TagDescriptions": [
            {"ResourceArn": LB_OLD, "Tags": [{"Key": "stack", "Value": "legacy"}]}]},
            {"ResourceArns": [LB_OLD, LB_LIVE, TG_OLD, TG_LIVE, TG_EMPTY]})
    st["elbv2"].add_response("describe_target_health", {"TargetHealthDescriptions": [
        {"Target": {"Id": "i-gone"}, "TargetHealth": {"State": "unhealthy"}}]}, {"TargetGroupArn": TG_OLD})
    st["elbv2"].add_response("describe_target_health", {"TargetHealthDescriptions": [
        {"Target": {"Id": "10.0.0.1"}, "TargetHealth": {"State": "healthy"}}]}, {"TargetGroupArn": TG_LIVE})
    st["elbv2"].add_response("describe_target_health", {"TargetHealthDescriptions": []}, {"TargetGroupArn": TG_EMPTY})
    st["elb"].add_response("describe_load_balancers", {"LoadBalancerDescriptions": []})
    # Elastic Beanstalk
    st["elasticbeanstalk"].add_response("describe_environments", {"Environments": [
        {"EnvironmentId": "e-old", "EnvironmentName": "legacy-prod", "ApplicationName": "legacy",
         "CNAME": "legacy-prod.us-east-1.elasticbeanstalk.com", "Status": "Ready", "Health": "Grey",
         "DateCreated": d("2025-01-01"), "DateUpdated": d("2026-07-01"),
         "EnvironmentArn": f"arn:aws:elasticbeanstalk:{R}:{ACCT}:environment/legacy/legacy-prod"},
    ]}, {"IncludeDeleted": False})
    if tagged:
        st["elasticbeanstalk"].add_response("list_tags_for_resource", {"ResourceTags": [
            {"Key": "stack", "Value": "legacy"}]}, {"ResourceArn": ANY})
    st["elasticbeanstalk"].add_response("describe_environment_resources", {"EnvironmentResources": {
        "EnvironmentName": "legacy-prod", "Instances": [{"Id": "i-eb1"}], "LoadBalancers": []}},
        {"EnvironmentId": "e-old"})
    st["elasticbeanstalk"].add_response("describe_applications", {"Applications": [
        {"ApplicationName": "legacy", "DateCreated": d("2025-01-01"), "DateUpdated": d("2025-06-01"),
         "ApplicationArn": f"arn:aws:elasticbeanstalk:{R}:{ACCT}:application/legacy"}]})
    if tagged:
        st["elasticbeanstalk"].add_response("list_tags_for_resource", {"ResourceTags": []},
                                            {"ResourceArn": f"arn:aws:elasticbeanstalk:{R}:{ACCT}:application/legacy"})
    # ECS
    st["ecs"].add_response("list_clusters", {"clusterArns": ["arn:aws:ecs:us-east-1:123456789012:cluster/c1"]})
    st["ecs"].add_response("list_services", {"serviceArns": ["arn:aws:ecs:us-east-1:123456789012:service/c1/zero",
                                                             "arn:aws:ecs:us-east-1:123456789012:service/c1/live"]})
    st["ecs"].add_response("describe_services", {"services": [
        {"serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/c1/zero", "serviceName": "zero",
         "status": "ACTIVE", "desiredCount": 0, "createdAt": d("2026-04-01")},
        {"serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/c1/live", "serviceName": "live",
         "status": "ACTIVE", "desiredCount": 2, "createdAt": d("2026-04-01")},
    ]}, {"cluster": "arn:aws:ecs:us-east-1:123456789012:cluster/c1", "services": ANY, "include": ["TAGS"]})
    st["rds"].add_response("describe_db_instances", {"DBInstances": []})
    st["rds"].add_response("describe_db_snapshots", {"DBSnapshots": []}, {"SnapshotType": "manual"})
    # Logs
    if logs_error:
        st["logs"].add_client_error("describe_log_groups", "AccessDeniedException", "no")
    else:
        logs(st, tagged)
    # Route 53
    st["route53"].add_response("list_hosted_zones", {"HostedZones": [
        {"Id": "/hostedzone/Z1", "Name": "example.com.", "CallerReference": "c"}], "IsTruncated": False,
        "Marker": "", "MaxItems": "100"})
    st["route53"].add_response("list_resource_record_sets", {"ResourceRecordSets": [
        {"Name": "api.example.com.", "Type": "A", "AliasTarget": {
            "HostedZoneId": "Z35SXDOTRQ7X7K", "DNSName": "dualstack.gone-lb-999.us-east-1.elb.amazonaws.com.",
            "EvaluateTargetHealth": False}},
        {"Name": "old.example.com.", "Type": "CNAME", "TTL": 300,
         "ResourceRecords": [{"Value": "legacy-prod.us-east-1.elasticbeanstalk.com"}]},
        {"Name": "www.example.com.", "Type": "A", "AliasTarget": {
            "HostedZoneId": "Z35SXDOTRQ7X7K", "DNSName": "dualstack.new-lb-222.us-east-1.elb.amazonaws.com.",
            "EvaluateTargetHealth": False}},
        {"Name": "eu.example.com.", "Type": "CNAME", "TTL": 300,
         "ResourceRecords": [{"Value": "x-1.eu-west-1.elb.amazonaws.com"}]},
        {"Name": "ip.example.com.", "Type": "A", "TTL": 300, "ResourceRecords": [{"Value": "52.0.0.9"}]},
    ], "IsTruncated": False, "MaxItems": "300"}, {"HostedZoneId": "Z1"})


def logs(st, tagged):
    st["logs"].add_response("describe_log_groups", {"logGroups": [
        {"logGroupName": "/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log", "creationTime": ms("2025-01-01"),
         "storedBytes": 5_000_000_000,
         "arn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log:*"},
        {"logGroupName": "/app/new", "creationTime": ms("2026-01-01"), "storedBytes": 1_000},
        {"logGroupName": "/app/brand-new", "creationTime": ms("2026-10-01"), "storedBytes": 0},
    ]})
    st["logs"].add_response("describe_log_streams", {"logStreams": [
        {"logStreamName": "i-eb1", "lastEventTimestamp": ms("2026-08-20")}]},
        {"logGroupName": "/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log", "orderBy": "LastEventTime",
         "descending": True, "limit": 1})
    if tagged:
        st["logs"].add_response("list_tags_for_resource", {"tags": {"stack": "legacy"}}, {"resourceArn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log"})
    st["logs"].add_response("describe_log_streams", {"logStreams": [
        {"logStreamName": "s", "lastEventTimestamp": ms("2026-10-26")}]},
        {"logGroupName": "/app/new", "orderBy": "LastEventTime", "descending": True, "limit": 1})


def scan(clients, session, tags=None, ip_ranges=None):
    return Scanner(session, [R], BEFORE, tags or {}, Prices.load(), ip_ranges, clients=clients).run()


def by_id(result):
    return {i.id: i for i in result["items"]}


def test_full_scan_finds_leftovers_and_skips_live(stubs, session):
    clients, st = stubs
    world(st)
    activate(st)
    res = scan(clients, session)
    for s in st.values():
        s.assert_no_pending_responses()
    items = by_id(res)
    assert res["account"] == ACCT and res["errors"] == []
    assert set(items) == {
        "eipalloc-free", "vol-old", "ami-old", "snap-ami", "snap-old", "snap-backup",
        LB_OLD, TG_EMPTY, "e-old", "legacy", "arn:aws:ecs:us-east-1:123456789012:service/c1/zero",
        "/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log",
        "Z1/api.example.com./A", "Z1/old.example.com./CNAME",
    }
    # live or too new: never listed
    assert not {"vol-new", "ami-used", "snap-kept", "snap-new", LB_LIVE, TG_LIVE, "/app/new"} & set(items)
    # prices
    assert items["vol-old"].monthly_usd == pytest.approx(8.0)
    assert items["eipalloc-free"].monthly_usd == pytest.approx(3.65)
    assert items[LB_OLD].monthly_usd == pytest.approx(0.0225 * 730 + 2 * 3.65)
    assert items["snap-ami"].monthly_usd == pytest.approx(0.2)
    assert items["snap-old"].monthly_usd == pytest.approx(2.5)
    assert items["e-old"].monthly_usd == pytest.approx(0.0208 * 730)
    assert items["/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log"].monthly_usd == pytest.approx(0.15)
    # dependencies and verify flags
    assert items["snap-ami"].depends_on == ["ami-old"]
    assert items["ami-old"].action == "verify"
    assert items["snap-backup"].action == "verify"
    assert items["legacy"].depends_on == ["e-old"]
    assert items["Z1/api.example.com./A"].action == "delete"
    assert "dangling" in items["Z1/api.example.com./A"].reason
    assert items["Z1/old.example.com./CNAME"].action == "verify"
    assert items["Z1/old.example.com./CNAME"].depends_on == ["e-old"]
    # exact commands
    assert items["vol-old"].commands == ["aws ec2 delete-volume --volume-id vol-old --region us-east-1"]
    assert items[TG_EMPTY].commands == [f"aws elbv2 delete-target-group --target-group-arn {TG_EMPTY} --region us-east-1"]
    assert items["e-old"].commands == ["aws elasticbeanstalk terminate-environment --environment-id e-old --region us-east-1"]
    cmd = items["Z1/api.example.com./A"].commands[0]
    assert cmd.startswith("aws route53 change-resource-record-sets --hosted-zone-id Z1 --change-batch '")
    batch = json.loads(cmd.split("--change-batch ", 1)[1].strip("'"))
    assert batch["Changes"][0]["Action"] == "DELETE"
    assert batch["Changes"][0]["ResourceRecordSet"]["AliasTarget"]["DNSName"].startswith("dualstack.gone-lb-999")
    # unscanned region and unchecked IPs are explained, not guessed
    assert any("not scanned" in n for n in res["notes"])
    assert any("--ip-ranges" in n for n in res["notes"])
    # phase order: DNS first, logs last
    phases = [i.phase for i in res["items"]]
    assert phases == sorted(phases) and res["items"][0].kind == "route53_record" and res["items"][-1].kind == "log_group"


def test_ip_ranges_flags_released_eip_and_doomed_eip(stubs, session):
    import ipaddress

    clients, st = stubs
    world(st)
    activate(st)
    res = scan(clients, session, ip_ranges=[ipaddress.ip_network("52.0.0.0/24")])
    items = by_id(res)
    assert items["Z1/ip.example.com./A"].action == "verify"
    assert "released Elastic IP" in items["Z1/ip.example.com./A"].reason


def test_tag_filter_narrows_and_fetches_tags(stubs, session):
    clients, st = stubs
    world(st, tags_on_volume={"Name": "old-db-data", "stack": "legacy"}, tagged=True)
    activate(st)
    res = scan(clients, session, tags=parse_tag_filters(["stack=legacy"]))
    for s in st.values():
        s.assert_no_pending_responses()
    kinds = {i.id: i.kind for i in res["items"]}
    assert "vol-old" in kinds and LB_OLD in kinds and "e-old" in kinds
    assert "/aws/elasticbeanstalk/legacy-prod/var/log/web.stdout.log" in kinds
    assert "eipalloc-free" not in kinds and TG_EMPTY not in kinds and "snap-old" not in kinds
    assert "legacy" not in kinds  # the application itself is not tagged


def test_tag_filter_parsing():
    assert parse_tag_filters(["a=b", "c", "d="]) == {"a": "b", "c": None, "d": ""}
    with pytest.raises(ValueError):
        parse_tag_filters(["=x"])


def test_collector_error_is_reported_and_scan_continues(stubs, session):
    clients, st = stubs
    world(st, logs_error=True)
    activate(st)
    res = scan(clients, session)
    assert {"collector": "log_groups", "region": R, "error_code": "AccessDeniedException"} in res["errors"]
    assert "vol-old" in by_id(res)


def test_guard_refuses_any_write(session):
    for service, op, kw in [("ec2", "delete_volume", {"VolumeId": "vol-1"}),
                            ("elbv2", "delete_load_balancer", {"LoadBalancerArn": LB_OLD}),
                            ("route53", "change_resource_record_sets",
                             {"HostedZoneId": "Z1", "ChangeBatch": {"Changes": []}}),
                            ("logs", "delete_log_group", {"logGroupName": "x"})]:
        c = make_client(session, service, R)
        with pytest.raises(ReadOnlyViolation):
            getattr(c, op)(**kw)


def test_cli_writes_markdown_and_json(stubs, session, tmp_path, capsys):
    clients, st = stubs
    world(st)
    activate(st)
    args = cli.parser().parse_args(["scan", "--before-date", "2026-09-01", "--region", R, "--out", str(tmp_path)])
    assert cli.cmd_scan(args, session=session, clients=clients, now=NOW) == 0
    doc = json.loads((tmp_path / "sweeper-plan.json").read_text())
    md = (tmp_path / "sweeper-plan.md").read_text()
    assert doc["executed"] is False and doc["summary"]["items"] == 14
    assert doc["price_table"]["as_of"] == "2026-10-27"
    assert doc["summary"]["monthly_usd_total"] == pytest.approx(
        8 + 3.65 + 0.0225 * 730 + 7.3 + 0.2 + 2.5 + 0.5 + 0.0208 * 730 + 0.15, abs=0.02)
    assert "**Nothing was deleted.**" in md
    assert "aws ec2 release-address --allocation-id eipalloc-free --region us-east-1" in md
    assert "# VERIFY:" in md and "# backup: aws ec2 create-snapshot" in md
    assert md.index("aws route53") < md.index("aws ecs delete-service") < md.index("aws logs delete-log-group")
    assert "14 items" in capsys.readouterr().err


def test_empty_plan_renders():
    doc = pl.build({"account": ACCT, "items": [], "errors": [], "notes": []}, before=BEFORE, regions=[R], tags={},
                   prices_meta=Prices.load().meta(), now=NOW)
    assert "Clean cutover" in pl.markdown(doc)
    assert doc["summary"]["monthly_usd_total"] == 0
