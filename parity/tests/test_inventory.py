import io
import json
from datetime import timedelta

from dawnfix_parity.cli import run
from dawnfix_parity.cloudtrail import RateLimiter
from tests.conftest import NOW, PROD, REGION, sm_arn


class FakeClock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def ct_event(name, params, principal_role, days_ago=1, error=None):
    ev = {"eventName": name, "requestParameters": params,
          "userIdentity": {"type": "AssumedRole", "arn": f"arn:aws:sts::{PROD}:assumed-role/{principal_role}/i-123",
                           "sessionContext": {"sessionIssuer": {"arn": f"arn:aws:iam::{PROD}:role/{principal_role}"}}}}
    if error:
        ev["errorCode"] = error
    return {"EventId": "e", "EventName": name, "EventTime": NOW - timedelta(days=days_ago),
            "CloudTrailEvent": json.dumps(ev)}


def inventory(world, config_file, *extra, queue_ct=None):
    world.queue_env("dev", lookups=False)
    world.queue_env("prod", lookups=False)
    if queue_ct:
        queue_ct(world.stub("prod", "cloudtrail"))
    out, err = io.StringIO(), io.StringIO()
    fc = FakeClock()
    code = run(["-c", str(config_file), "inventory", "--format", "json", *extra], aws_factory=world.factory,
               now=NOW, out=out, err=err, limiter=RateLimiter(2, fc.clock, fc.sleep))
    assert code == 0, err.getvalue()
    world.assert_done()
    doc = json.loads(out.getvalue())
    rows = {(e, r["name"]): r for e, rs in doc["environments"].items() for r in rs}
    return rows, fc, err.getvalue(), out.getvalue()


def test_inventory_flags(world, config_file):
    rows, *_ = inventory(world, config_file)
    assert rows[("dev", "shop/dev/stripe")]["flags"] == ["unread", "never_rotated"]
    assert "never accessed" in rows[("dev", "shop/dev/stripe")]["notes"]
    assert rows[("prod", "shop/prod/stripe")]["flags"] == ["rotation_overdue"]
    assert rows[("prod", "shop/prod/stripe")]["rotation_age_days"] == 200
    assert "rotation is enabled but has not run" in rows[("prod", "shop/prod/stripe")]["notes"][0]
    assert rows[("prod", "shop/prod/legacy")]["flags"] == ["unread", "never_rotated", "orphaned"]
    assert rows[("prod", "/shop/prod/DB_URL")]["flags"] == ["never_rotated", "orphaned"]   # SecureString v1
    assert rows[("prod", "/shop/prod/NEW_FEATURE")]["flags"] == ["orphaned"]
    assert rows[("dev", "/shop/dev/LOG_LEVEL")]["flags"] == []       # read via CONFIG_PATH prefix


def test_inventory_references(world, config_file):
    rows, *_ = inventory(world, config_file)
    refs = rows[("dev", "/shop/dev/DB_URL")]["referenced_by"]
    assert "ecs:shop-dev/shop-api-dev (shop-api-dev:7)/app DB_URL" in refs
    assert "ecs:shop-prod/shop-api-prod (shop-api-prod:42)/app REDIS [from prod]" in refs
    assert any("CONFIG_PATH (prefix)" in r for r in refs)
    assert sorted(rows[("dev", "shop/dev/stripe")]["referenced_by"]) == [
        "ecs:shop-dev/shop-api-dev (shop-api-dev:7)/app STRIPE", "lambda:shop-dev-worker SECRET_ARN"]
    assert rows[("prod", "shop/prod/stripe")]["last_read_source"] == "secretsmanager"


def test_inventory_env_filter_and_no_values(world, config_file):
    rows, _, _, raw = inventory(world, config_file, "--env", "prod")
    assert {e for e, _ in rows} == {"prod"}
    assert "PLANTED" not in raw


def test_cloudtrail_readers_rate_limited(world, config_file):
    legacy_arn = sm_arn(PROD, "shop/prod/legacy", "LgCy01")

    def queue(ct):
        ct.add_response("lookup_events", {"Events": [ct_event("GetSecretValue", {"secretId": legacy_arn}, "batch")],
                                          "NextToken": "t1"},
                        {"LookupAttributes": [{"AttributeKey": "EventName", "AttributeValue": "GetSecretValue"}],
                         "StartTime": NOW - timedelta(days=90), "EndTime": NOW, "MaxResults": 50})
        ct.add_response("lookup_events", {"Events": [
            ct_event("GetSecretValue", {"secretId": legacy_arn}, "batch", days_ago=3),
            ct_event("GetSecretValue", {"secretId": "shop/prod/stripe"}, "intruder", error="AccessDenied")]},
            {"LookupAttributes": [{"AttributeKey": "EventName", "AttributeValue": "GetSecretValue"}],
             "StartTime": NOW - timedelta(days=90), "EndTime": NOW, "MaxResults": 50, "NextToken": "t1"})
        for name, events in [
            ("GetParameter", [ct_event("GetParameter", {"name": "/shop/prod/NEW_FEATURE"}, "api")]),
            ("GetParameters", [ct_event("GetParameters", {"names": ["/shop/prod/NEW_FEATURE", "/x"]}, "api")]),
            ("GetParametersByPath", [ct_event("GetParametersByPath", {"path": "/shop/prod/DB_URL"}, "api"),
                                     ct_event("GetParametersByPath", {"path": "/shop/prod/NEW_FEATURE"}, "x")]),
        ]:
            ct.add_response("lookup_events", {"Events": events},
                            {"LookupAttributes": [{"AttributeKey": "EventName", "AttributeValue": name}],
                             "StartTime": NOW - timedelta(days=90), "EndTime": NOW, "MaxResults": 50})

    rows, fc, err, _ = inventory(world, config_file, "--env", "prod", "--cloudtrail", "--cloudtrail-days", "365",
                                 queue_ct=queue)
    legacy = rows[("prod", "shop/prod/legacy")]
    assert legacy["readers"] == {f"arn:aws:iam::{PROD}:role/batch": 2}
    assert "orphaned" not in legacy["flags"]
    assert legacy["last_read_source"] == "cloudtrail" and "unread" not in legacy["flags"]
    assert rows[("prod", "/shop/prod/NEW_FEATURE")]["readers"] == {
        f"arn:aws:iam::{PROD}:role/api": 2}   # a path read covers children only
    # the denied read by "intruder" is not counted
    assert rows[("prod", "shop/prod/stripe")]["readers"] == {}
    # days clamped to 90, so an SSM parameter with no reads at all is flagged unread
    assert rows[("prod", "/shop/prod/API_KEY")]["flags"] == ["unread", "orphaned"]
    assert "no reads in 90 days of CloudTrail" in rows[("prod", "/shop/prod/API_KEY")]["notes"]
    # 5 calls at 2/s: 4 waits of 0.5s
    assert fc.slept == [0.5] * 4


def test_cloudtrail_max_pages_truncates(world, config_file):
    def queue(ct):
        for name in ["GetSecretValue", "GetParameter", "GetParameters", "GetParametersByPath"]:
            ct.add_response("lookup_events", {"Events": [], "NextToken": "more"}, None)

    rows, fc, err, _ = inventory(world, config_file, "--env", "prod", "--cloudtrail", "--cloudtrail-max-pages", "1",
                                 queue_ct=queue)
    assert "readers are partial" in err
    # 30-day window is shorter than unread_days=90: SSM parameters are not called unread
    assert not any("unread" in r["flags"] for (e, n), r in rows.items() if n.startswith("/"))
