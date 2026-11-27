import json
from datetime import date, datetime, timedelta, timezone

import boto3
import pytest
from botocore.stub import Stubber

from dawnfix_receipt import cli
from dawnfix_receipt import costs as cx
from dawnfix_receipt import github as gh
from dawnfix_receipt import receipt as rc
from dawnfix_receipt.guard import ReadOnlyViolation, make_client

SHA = "abc1234def5678abc1234def5678abc1234def56"
DEPLOYED = "2026-10-20T14:03:00Z"
NAT = ["EC2 - Other", "USE1-NatGateway-Bytes"]
EC2 = ["Amazon Elastic Compute Cloud - Compute", "BoxUsage:t3.medium"]
S3 = ["Amazon Simple Storage Service", "TimedStorage-ByteHrs"]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def ce():
    s = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    c = make_client(s, "ce")
    st = Stubber(c)
    yield c, st
    st.deactivate()


def day_result(day: date, groups: dict, estimated=True, metric="UnblendedCost"):
    return {"TimePeriod": {"Start": day.isoformat(), "End": (day + timedelta(days=1)).isoformat()},
            "Total": {}, "Estimated": estimated,
            "Groups": [{"Keys": list(k), "Metrics": {metric: {"Amount": f"{v:.4f}", "Unit": "USD"}}}
                       for k, v in groups.items()]}


def series(days_before, days_after, deploy_day=date(2026, 10, 20)):
    out = []
    for d in days_before:
        out.append(day_result(d, {tuple(NAT): 2.0, tuple(EC2): 10.0 + (d.day % 2) * 0.2, tuple(S3): 1.0}))
    out.append(day_result(deploy_day, {tuple(NAT): 20.0, tuple(EC2): 12.0, tuple(S3): 1.0}))
    for d in days_after:
        out.append(day_result(d, {tuple(NAT): 37.1, tuple(EC2): 15.1, tuple(S3): 1.0}))
    return out


def args(*extra, cache_dir=""):
    return cli.parser().parse_args(["--deploy-sha", SHA, "--deployed-at", DEPLOYED, "--cache-dir", cache_dir,
                                    *extra])


def expected_req(start, end, group_by=cli.GROUP_SERVICE_USAGE):
    return cx.request_for(date.fromisoformat(start), date.fromisoformat(end), group_by, "UnblendedCost")


B = [date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 19)]
A = [date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 23)]
FINAL_NOW = datetime(2026, 10, 25, 9, tzinfo=timezone.utc)


def test_friendly_labels():
    assert rc.friendly(" | ".join(NAT)) == "NAT Gateway data processing"
    assert rc.friendly(" | ".join(EC2)) == "EC2 t3.medium instance hours"
    assert rc.friendly("AmazonCloudWatch | USE2-DataProcessing-Bytes") == "CloudWatch Logs ingestion"
    assert rc.friendly("Amazon Simple Storage Service | TimedStorage-ByteHrs") == "S3 storage"
    assert rc.friendly("Amazon Relational Database Service | InstanceUsage:db.t4g.micro") == \
        "RDS db.t4g.micro instance hours"
    assert rc.friendly("AWS Lambda | APN1-Request") == "AWS Lambda: Request"


def test_plan_respects_ce_lag():
    p = rc.Plan(cli._when(DEPLOYED), 3, datetime(2026, 10, 23, 6, tzinfo=timezone.utc))
    assert p.before_days == B and p.wanted_after == A
    assert p.after_days == [date(2026, 10, 21)] and not p.final
    assert rc.Plan(cli._when(DEPLOYED), 3, FINAL_NOW).final


def test_window_parsing():
    assert rc.parse_window("3d") == 3 and rc.parse_window("7") == 7
    for bad in ("0d", "31d", "1w"):
        with pytest.raises(ValueError):
            rc.parse_window(bad)


def test_final_receipt_attributes_delta(ce, capsys, tmp_path):
    c, st = ce
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A)}, expected_req("2026-10-17", "2026-10-24"))
    st.activate()
    out = tmp_path / "r.json"
    assert cli.run(args("--json", str(out)), ce=c, now=FINAL_NOW) == 0
    st.assert_no_pending_responses()
    body = capsys.readouterr().out
    doc = json.loads(out.read_text())
    assert doc["headline"] == "deploy abc1234: +$40.07/day (+305%), mostly NAT Gateway data processing (+$35.10/day)"
    assert doc["final"] is True and doc["delta_usd_per_day"] == pytest.approx(40.07, abs=0.01)
    assert body.startswith(f"<!-- dawnfix-receipt:sha={SHA} -->\n### deploy abc1234: +$40.07/day")
    assert "| NAT Gateway data processing | 2.00 | 37.10 | +$35.10 |" in body
    assert "Provisional" not in body
    assert "Cost Explorer requests this run: 1 (≈$0.01)" in body


def test_provisional_then_cached_then_final(ce, capsys, tmp_path):
    c, st = ce
    cache = str(tmp_path / "cache")
    early = datetime(2026, 10, 23, 6, tzinfo=timezone.utc)
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A[:1])},
                    expected_req("2026-10-17", "2026-10-22"))
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A)}, expected_req("2026-10-17", "2026-10-24"))
    st.activate()
    assert cli.run(args(cache_dir=cache), ce=c, now=early) == 0
    first = capsys.readouterr().out
    assert "1 of 3 day(s) after" in first and "Provisional" in first and "Re-run after 2026-10-25T00:00:00Z" in first
    # same run an hour later: served from cache, no CE request (the stubber would hand out the next response)
    assert cli.run(args(cache_dir=cache), ce=c, now=early + timedelta(hours=1)) == 0
    assert "requests this run: 0 (≈$0.00), cache hits: 1" in capsys.readouterr().out
    assert cli.run(args(cache_dir=cache), ce=c, now=FINAL_NOW) == 0
    st.assert_no_pending_responses()
    assert "Provisional" not in capsys.readouterr().out


def test_settled_cache_is_reused_forever(tmp_path):
    cache = cx.Cache(tmp_path)
    cache.put("k", [{"x": 1}], datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert cache.get("k", date(2026, 9, 20), datetime(2027, 1, 1, tzinfo=timezone.utc)) == [{"x": 1}]
    # not settled when fetched, and the TTL has passed: refetch
    assert cache.get("k", date(2026, 10, 1), datetime(2026, 10, 1, 7, tzinfo=timezone.utc)) is None


def test_pagination_and_tag_breakdown(ce, capsys):
    c, st = ce
    allpages = series(B, A)
    st.add_response("get_cost_and_usage", {"ResultsByTime": allpages[:4], "NextPageToken": "p2"},
                    expected_req("2026-10-17", "2026-10-24"))
    st.add_response("get_cost_and_usage", {"ResultsByTime": allpages[4:]},
                    {**expected_req("2026-10-17", "2026-10-24"), "NextPageToken": "p2"})
    tag_days = [day_result(d, {("team$payments",): 5.0, ("team$",): 8.0}) for d in B] + \
               [day_result(d, {("team$payments",): 44.0, ("team$",): 9.0}) for d in A]
    st.add_response("get_cost_and_usage", {"ResultsByTime": tag_days},
                    expected_req("2026-10-17", "2026-10-24", [{"Type": "TAG", "Key": "team"}]))
    st.activate()
    assert cli.run(args("--tag-key", "team"), ce=c, now=FINAL_NOW) == 0
    st.assert_no_pending_responses()
    body = capsys.readouterr().out
    assert "By tag `team`:" in body
    assert "| payments | 5.00 | 44.00 | +$39.00 |" in body and "| (untagged) | 8.00 | 9.00 | +$1.00 |" in body


def test_small_change_is_noise(ce, capsys):
    c, st = ce
    flat = [day_result(d, {tuple(EC2): 100.0 + (0.5 if d in A else 0)}) for d in B + A]
    st.add_response("get_cost_and_usage", {"ResultsByTime": flat})
    st.activate()
    cli.run(args(), ce=c, now=FINAL_NOW)
    assert "no material cost change (+$0.50/day" in capsys.readouterr().out


def test_no_after_days_makes_no_ce_request(ce, capsys):
    c, st = ce
    st.activate()  # no responses queued: any CE call would fail the test
    assert cli.run(args(), ce=c, now=datetime(2026, 10, 21, 6, tzinfo=timezone.utc)) == 0
    assert "waiting for Cost Explorer data" in capsys.readouterr().out


def test_ce_error_exit_code(ce, capsys):
    c, st = ce
    st.add_client_error("get_cost_and_usage", "AccessDeniedException", "no")
    st.activate()
    assert cli.run(args(), ce=c, now=FINAL_NOW) == 2
    assert "AccessDeniedException" in capsys.readouterr().err


def test_guard_refuses_non_read(ce):
    c, _ = ce
    with pytest.raises(ReadOnlyViolation):
        c.create_anomaly_monitor(AnomalyMonitor={"MonitorName": "x", "MonitorType": "DIMENSIONAL",
                                                 "MonitorDimension": "SERVICE"})


class FakeGitHub:
    def __init__(self, comments=None):
        self.comments = list(comments or [])
        self.calls = []

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url))
        assert token == "t"
        if method == "GET":
            return 200, self.comments if "page=1" in url else []
        if method == "POST":
            c = {"id": 99, "body": body["body"]}
            self.comments.append(c)
            return 201, c
        if method == "PATCH":
            cid = int(url.rsplit("/", 1)[1])
            for c in self.comments:
                if c["id"] == cid:
                    c["body"] = body["body"]
            return 200, {}
        raise AssertionError(method)


def test_upsert_creates_updates_and_skips_unchanged():
    m = rc.marker(SHA)
    fake = FakeGitHub([{"id": 1, "body": "unrelated"}])
    assert gh.upsert_comment("o/r", "t", m, f"{m}\nv1\n<sub>a</sub>", pr=7, http=fake) == ("created", 99)
    assert fake.calls[-1] == ("POST", "https://api.github.com/repos/o/r/issues/7/comments")
    assert gh.upsert_comment("o/r", "t", m, f"{m}\nv1\n<sub>b</sub>", pr=7, http=fake) == ("unchanged", 99)
    assert gh.upsert_comment("o/r", "t", m, f"{m}\nv2\n<sub>b</sub>", pr=7, http=fake) == ("updated", 99)
    assert fake.calls[-1] == ("PATCH", "https://api.github.com/repos/o/r/issues/comments/99")
    assert sum(1 for c in fake.comments if m in c["body"]) == 1


def test_cli_posts_commit_comment(ce, capsys):
    c, st = ce
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A)})
    st.activate()
    fake = FakeGitHub()
    rcode = cli.run(args("--post", "--repo", "o/r"), ce=c, now=FINAL_NOW, http=fake,
                    env={"GITHUB_TOKEN": "t"})
    assert rcode == 0
    assert fake.calls[0][1].startswith(f"https://api.github.com/repos/o/r/commits/{SHA}/comments?")
    assert fake.calls[-1] == ("POST", f"https://api.github.com/repos/o/r/commits/{SHA}/comments")
    assert "comment created" in capsys.readouterr().err


def test_cli_post_without_token_fails(ce, capsys):
    c, st = ce
    st.activate()
    assert cli.run(args("--post", "--repo", "o/r"), ce=c, now=datetime(2026, 10, 21, tzinfo=timezone.utc),
                   env={}) == 2
