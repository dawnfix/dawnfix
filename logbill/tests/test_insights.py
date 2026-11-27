from datetime import timedelta

import pytest

from logbill.awsread import INSIGHTS_OPERATIONS, READ_OPERATIONS
from logbill.insights import QUERY, BudgetExceeded, Plan, PlanItem, check_budget, parse_results, plan_queries, run_plan
from logbill.model import price_groups
from logbill.prices import GB
from tests.conftest import NOW, group

INS = READ_OPERATIONS | INSIGHTS_OPERATIONS


def row(pattern, count, ratio, sev="Info"):
    return [{"field": "@pattern", "value": pattern}, {"field": "@sampleCount", "value": str(count)},
            {"field": "@ratio", "value": str(ratio)}, {"field": "@severityLabel", "value": sev}]


# --- pattern parsing -------------------------------------------------------

def test_parse_results_shares_and_dollars(prices):
    g = group(gb_month=100)  # $50/month ingestion
    price_groups([g], prices)
    rows = [row("polling queue <Token-1> for new messages", 600, 0.6),
            row("short <Token-1>", 300, 0.3)]
    pats = parse_results(rows, g)
    assert [p.count for p in pats] == [600, 300]
    # 1000 events in the window; the long line weighs more than its event share
    long_, short = pats
    assert long_.byte_share > 0.6 > short.byte_share
    assert long_.byte_share + short.byte_share == pytest.approx(0.9)  # covers 90% of events
    assert long_.monthly_usd == pytest.approx(long_.byte_share * 50)
    assert long_.severity == "Info"


def test_parse_results_skips_junk_rows(prices):
    g = group(gb_month=1)
    price_groups([g], prices)
    rows = [[{"field": "@sampleCount", "value": "3"}], row("x", "nope", 0.1), row("ok line here", 2, 1.0)]
    pats = parse_results(rows, g)
    assert [p.text for p in pats] == ["ok line here"]
    assert pats[0].byte_share == pytest.approx(1.0)


def test_pattern_text_is_redacted_before_it_is_kept(prices):
    g = group(gb_month=1)
    price_groups([g], prices)
    raw = ("user jane.doe@example.com token Bearer abc.def.ghi id 3f2b8c1e-9a4d-4b7e-8f00-1234567890ab "
           "card 4111111111111111 phone +1 415-555-0100 <Token-1>")
    p = parse_results([row(raw, 5, 1.0)], g)[0]
    for secret in ("jane.doe", "example.com", "abc.def", "3f2b8c1e", "4111111111111111", "555-0100"):
        assert secret not in p.text
    assert ":email" in p.text and ":uuid" in p.text and "<Token-1>" in p.text


def test_pattern_ids_are_stable_and_distinct(prices):
    g = group(gb_month=1)
    price_groups([g], prices)
    a = parse_results([row("alpha line one", 1, 0.5), row("beta line two", 1, 0.5)], g)
    b = parse_results([row("alpha line one", 9, 0.9)], g)
    assert a[0].id != a[1].id
    assert {p.id for p in a if p.text == "alpha line one"} == {b[0].id}


# --- budget ------------------------------------------------------------------

def _groups(*gb_per_day):
    gs = []
    for i, d in enumerate(gb_per_day):
        g = group(f"/app/{i}", gb_month=d * 30)
        g.last_day_bytes = d * GB
        gs.append(g)
    return gs


def test_plan_fits_the_budget_and_shrinks_windows():
    gs = _groups(48, 48, 48)  # 2 GB/hour each
    plan = plan_queries(gs, budget_gb=5, hours=24, end=NOW)
    assert plan.total_bytes <= 5 * GB
    assert [round(i.hours, 2) for i in plan.items] == [2.5]  # the first group eats the budget
    assert [r for _, r in plan.skipped] == ["budget", "budget"]


def test_plan_gives_full_window_when_cheap():
    gs = _groups(0.024, 0.024)  # 1 MB/hour
    plan = plan_queries(gs, budget_gb=5, hours=24, end=NOW)
    assert [i.hours for i in plan.items] == [24, 24]
    assert plan.items[0].start == NOW - timedelta(hours=24)


def test_plan_uses_the_busier_of_mean_and_newest_day():
    g = _groups(1)[0]
    g.last_day_bytes = 48 * GB  # yesterday was a spike
    plan = plan_queries([g], budget_gb=1, hours=24, end=NOW)
    assert plan.total_bytes <= 1 * GB
    assert plan.items[0].hours == pytest.approx(0.5)


def test_zero_budget_plans_nothing():
    plan = plan_queries(_groups(1), budget_gb=0, hours=24, end=NOW)
    assert plan.items == [] and plan.total_bytes == 0


def test_budget_guard_refuses_an_oversized_plan():
    g = _groups(1)[0]
    plan = Plan(items=[PlanItem(g, NOW - timedelta(hours=1), NOW, 6 * GB)], budget_bytes=5 * GB)
    with pytest.raises(BudgetExceeded):
        check_budget(plan)
    with pytest.raises(BudgetExceeded):
        run_plan(lambda r: pytest.fail("no client may be built"), plan)


def test_run_plan_stops_when_aws_reports_more_scanned_than_estimated(factory, prices):
    gs = _groups(0.024, 0.024)
    price_groups(gs, prices)
    plan = plan_queries(gs, budget_gb=0.05, hours=24, end=NOW)
    assert len(plan.items) == 2
    stub = factory.stub("logs", allowed=INS)
    stub.add_response("start_query", {"queryId": "q1"},
                      {"logGroupNames": ["/app/0"], "startTime": int(plan.items[0].start.timestamp()),
                       "endTime": int(NOW.timestamp()), "queryString": QUERY, "limit": 25})
    stub.add_response("get_query_results", {"status": "Running"}, {"queryId": "q1"})
    stub.add_response("get_query_results", {
        "status": "Complete", "statistics": {"bytesScanned": 0.05 * GB, "recordsScanned": 10, "recordsMatched": 10},
        "results": [row("polling queue for new messages", 10, 1.0)]}, {"queryId": "q1"})
    sleeps = []
    res = run_plan(lambda r: factory("logs", r, INS), plan, sleep=sleeps.append)
    stub.assert_no_pending_responses()
    assert [q["status"] for q in res["queries"]] == ["Complete", "skipped_budget"]
    assert factory.ops.count("StartQuery") == 1
    assert sleeps == [2.0]
    assert gs[0].patterns and gs[0].patterns[0].text == "polling queue for new messages"


def test_run_plan_stops_a_slow_query(factory):
    g = _groups(0.024)[0]
    plan = plan_queries([g], budget_gb=1, hours=1, end=NOW)
    stub = factory.stub("logs", allowed=INS)
    stub.add_response("start_query", {"queryId": "q1"})
    for _ in range(3):
        stub.add_response("get_query_results", {"status": "Running"})
    stub.add_response("stop_query", {"success": True}, {"queryId": "q1"})
    res = run_plan(lambda r: factory("logs", r, INS), plan, sleep=lambda s: None, timeout_s=4, poll_s=2)
    stub.assert_no_pending_responses()
    assert res["queries"][0]["status"] == "StoppedByLogbill"
