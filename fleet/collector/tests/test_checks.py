from datetime import timedelta

from botocore.exceptions import ClientError

from dawnfix_fleet import checks as C
from dawnfix_fleet.collect import account_ref, collect, collect_account

from .conftest import (ACCOUNT, EXTERNAL_ID, NOW, SLUG, FakeSession, alarm, assume_ok, ce_days, cert_detail,
                       config, schema_validate)


def opened_with(fake):
    return C.Opened(fake)


# --- getting in ---------------------------------------------------------------------------

def test_assumes_the_client_role_with_the_external_id(env):
    base, target = FakeSession(), FakeSession()
    assume_ok(base)
    acct = config()[SLUG].accounts[0]
    status, opened = C.open_account(acct, base, session_factory=lambda creds: target, environ=env)
    assert status == "ok" and opened.session is target
    base.assert_done()


def test_a_wrong_external_id_is_denied(env):
    base = FakeSession()
    base.stub("sts", "us-east-1").add_client_error("assume_role", "AccessDenied", "User: arn:... is not authorized")
    status, opened = C.open_account(config()[SLUG].accounts[0], base, environ=env)
    assert (status, opened) == ("denied", None)


def test_expired_source_credentials_say_expired(env):
    base = FakeSession()
    base.stub("sts", "us-east-1").add_client_error("assume_role", "ExpiredToken", "The security token included in the request is expired")
    assert C.open_account(config()[SLUG].accounts[0], base, environ=env)[0] == "expired"


def test_a_role_that_lands_in_another_account_is_refused(env):
    base = FakeSession()
    assume_ok(base, account="999999999999")
    assert C.open_account(config()[SLUG].accounts[0], base, session_factory=lambda c: None, environ=env)[0] == "account_mismatch"


def test_no_external_id_in_the_environment_makes_no_call():
    base = FakeSession()
    base.stub("sts", "us-east-1")
    assert C.open_account(config()[SLUG].accounts[0], base, environ={})[0] == "error"
    base.assert_done()


def test_own_ci_checks_whose_credentials_these_are():
    acct = config(role_arn=None, external_id_env=None)[SLUG].accounts[0]
    base = FakeSession()
    base.stub("sts", "us-east-1").add_response("get_caller_identity", {"Account": ACCOUNT, "Arn": f"arn:aws:sts::{ACCOUNT}:assumed-role/r/s", "UserId": "u"})
    status, opened = C.open_account(acct, base)
    assert status == "ok" and opened.session is base
    base.stub("sts", "us-east-1").add_response("get_caller_identity", {"Account": "999999999999", "Arn": f"arn:aws:sts::{ACCOUNT}:assumed-role/r/s", "UserId": "u"})
    assert C.open_account(acct, base)[0] == "account_mismatch"


# --- alarms -------------------------------------------------------------------------------

def test_alarms_counts_firing_and_stuck_across_pages_and_regions():
    t = FakeSession()
    east = t.stub("cloudwatch", "us-east-1")
    east.add_response("describe_alarms", {"MetricAlarms": [alarm("a", NOW - timedelta(hours=2))], "NextToken": "p2"},
                      {"StateValue": "ALARM", "AlarmTypes": ["MetricAlarm", "CompositeAlarm"], "MaxRecords": 100})
    east.add_response("describe_alarms", {"MetricAlarms": [alarm("b", NOW - timedelta(days=3))],
                                          "CompositeAlarms": [alarm("c", NOW - timedelta(minutes=5))]},
                      {"StateValue": "ALARM", "AlarmTypes": ["MetricAlarm", "CompositeAlarm"], "MaxRecords": 100,
                       "NextToken": "p2"})
    t.stub("cloudwatch", "eu-west-1").add_response("describe_alarms", {"MetricAlarms": []})
    assert C.alarms(opened_with(t), ("us-east-1", "eu-west-1"), NOW) == {"status": "ok", "firing": 3, "stuck_24h": 1}
    t.assert_done()


# --- certificates -------------------------------------------------------------------------

def test_certs_count_in_use_expiry_and_manual_renewals():
    t = FakeSession()
    acm = t.stub("acm", "us-east-1")
    arns = [f"arn:aws:acm:us-east-1:{ACCOUNT}:certificate/{i}" for i in range(6)]
    acm.add_response("list_certificates", {"CertificateSummaryList": [{"CertificateArn": a} for a in arns]},
                     {"CertificateStatuses": ["ISSUED", "EXPIRED"], "MaxItems": 100})
    acm.add_response("describe_certificate", cert_detail(arns[0], 200), {"CertificateArn": arns[0]})
    acm.add_response("describe_certificate", cert_detail(arns[1], 10), {"CertificateArn": arns[1]})  # auto-renews
    acm.add_response("describe_certificate", cert_detail(arns[2], 25, type_="IMPORTED", renewal="INELIGIBLE"),
                     {"CertificateArn": arns[2]})
    acm.add_response("describe_certificate", cert_detail(arns[3], -3, type_="IMPORTED"), {"CertificateArn": arns[3]})
    acm.add_response("describe_certificate", cert_detail(arns[4], 2, in_use=False), {"CertificateArn": arns[4]})
    acm.add_response("describe_certificate", cert_detail(arns[5], 40, renewal="INELIGIBLE"), {"CertificateArn": arns[5]})
    assert C.certs(opened_with(t), ("us-east-1",), NOW) == {
        "status": "ok", "total": 6, "in_use": 5, "expired": 1, "expiring_14d": 1, "expiring_30d": 2,
        "manual_renewal_30d": 2, "min_days_left": -3, "truncated": False,
    }
    t.assert_done()


def test_certs_with_none_in_use_have_no_minimum():
    t = FakeSession()
    t.stub("acm", "us-east-1").add_response("list_certificates", {"CertificateSummaryList": []})
    assert C.certs(opened_with(t), ("us-east-1",), NOW)["min_days_left"] is None


# --- spend --------------------------------------------------------------------------------

def test_spend_is_two_weeks_in_one_request_and_cached_for_the_day(tmp_path):
    t = FakeSession()
    t.stub("ce", "us-east-1").add_response(
        "get_cost_and_usage", {"ResultsByTime": ce_days(), "DimensionValueAttributes": []},
        {"TimePeriod": {"Start": "2026-10-13", "End": "2026-10-27"}, "Granularity": "DAILY",
         "Metrics": ["UnblendedCost"], "Filter": C.CE_FILTER})
    first = C.spend(opened_with(t), "0123456789abcdef", NOW.date(), tmp_path)
    assert first == {"status": "ok", "cached": False, "currency": "USD", "as_of": "2026-10-26",
                     "this_week_cents": 7004, "last_week_cents": 5600}
    # No response queued now: a second request would raise inside the stubber.
    second = C.spend(opened_with(t), "0123456789abcdef", NOW.date(), tmp_path)
    assert second == {**first, "cached": True}
    t.assert_done()


def test_spend_cache_expires_at_utc_midnight_and_ignores_junk(tmp_path):
    C.write_cache(tmp_path, "r", NOW.date(), {"currency": "USD", "as_of": "2026-10-26", "this_week_cents": 1,
                                              "last_week_cents": 2})
    assert C.read_cache(tmp_path, "r", NOW.date()) is not None
    assert C.read_cache(tmp_path, "r", NOW.date() + timedelta(days=1)) is None
    (tmp_path / "spend-j.json").write_text('{"day": "2026-10-27", "currency": "USD", "as_of": "x", '
                                           '"this_week_cents": "lots", "last_week_cents": 2}')
    assert C.read_cache(tmp_path, "j", NOW.date()) is None
    (tmp_path / "spend-k.json").write_text("not json")
    assert C.read_cache(tmp_path, "k", NOW.date()) is None


def test_spend_in_two_currencies_is_an_error_not_a_sum(env):
    base, t = FakeSession(), FakeSession()
    assume_ok(base)
    days = ce_days()
    days[-1] = {**days[-1], "Total": {"UnblendedCost": {"Amount": "3", "Unit": "EUR"}}}
    t.stub("ce", "us-east-1").add_response("get_cost_and_usage", {"ResultsByTime": days})
    acct = config(checks=["spend"])[SLUG].accounts[0]
    out = collect_account(SLUG, acct, base_session=base, now=NOW, cache_dir=None,
                          session_factory=lambda c: t, environ=env)
    assert out["spend"]["status"] == "error" and out["spend"]["this_week_cents"] is None


def test_a_denied_check_is_reported_and_the_rest_still_run(env):
    base, t = FakeSession(), FakeSession()
    assume_ok(base)
    t.stub("cloudwatch", "us-east-1").add_client_error("describe_alarms", "AccessDenied", "no")
    t.stub("acm", "us-east-1").add_response("list_certificates", {"CertificateSummaryList": []})
    t.stub("ce", "us-east-1").add_client_error("get_cost_and_usage", "ThrottlingException", "slow down")
    acct = config()[SLUG].accounts[0]
    out = collect_account(SLUG, acct, base_session=base, now=NOW, cache_dir=None,
                          session_factory=lambda c: t, environ=env)
    assert out["credential"] == "ok"
    assert out["alarms"] == {"status": "denied", "firing": None, "stuck_24h": None}
    assert out["spend"]["status"] == "throttled"
    assert out["certs"]["status"] == "ok"


def test_no_credentials_skips_every_check_and_still_validates(env):
    base = FakeSession()
    base.stub("sts", "us-east-1").add_client_error("assume_role", "AccessDenied", "no")
    doc = collect(config()[SLUG], base_session=base, now=NOW, environ=env)
    a = doc["accounts"][0]
    assert a["credential"] == "denied"
    assert {a[k]["status"] for k in ("alarms", "spend", "certs")} == {"skipped"}
    assert a["orphans"] == {"status": "not_implemented", "count": None}
    schema_validate(doc)


def test_no_spend_flag_makes_no_cost_explorer_call(env):
    base, t = FakeSession(), FakeSession()
    assume_ok(base)
    acct = config(checks=["spend"])[SLUG].accounts[0]
    out = collect_account(SLUG, acct, base_session=base, now=NOW, cache_dir=None, spend_enabled=False,
                          session_factory=lambda c: t, environ=env)
    assert out["spend"]["status"] == "skipped" and not t.stubs


def test_account_ref_is_stable_and_carries_no_digits_of_the_id():
    acct = config()[SLUG].accounts[0]
    ref = account_ref(SLUG, acct)
    assert ref == account_ref(SLUG, acct) and len(ref) == 16
    assert ACCOUNT not in ref and account_ref("othersl", acct) != ref


def test_nothing_secret_or_named_reaches_the_summary(env):
    base, t = FakeSession(), FakeSession()
    assume_ok(base)
    t.stub("cloudwatch", "us-east-1").add_response("describe_alarms", {"MetricAlarms": [alarm("payments-db-cpu", NOW)]})
    t.stub("acm", "us-east-1").add_response("list_certificates", {"CertificateSummaryList": []})
    t.stub("ce", "us-east-1").add_response("get_cost_and_usage", {"ResultsByTime": ce_days()})
    import json

    text = json.dumps(collect(config()[SLUG], base_session=base, now=NOW, environ=env))
    for needle in (ACCOUNT, EXTERNAL_ID, "payments", "fleet-read", "us-east-1", SLUG, "arn:"):
        assert needle not in text
