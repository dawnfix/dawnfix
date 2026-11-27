import pytest

from logbill.model import Pattern, price_groups
from logbill.suggest import ia_eligible, projected_stored_bytes, retention_saving, suggest
from tests.conftest import NOW_MS, group


def _kinds(sugg, kind):
    return [s for s in sugg if s.kind == kind]


def test_retention_suggested_for_never_expiring_groups_only(prices):
    forever = group("/app/forever", stored_gb=1000, age_days=365)
    kept = group("/app/kept", stored_gb=1000, retention=30)
    price_groups([forever, kept], prices)
    sugg, combined = suggest([forever, kept], prices, NOW_MS, retention_days=30)
    ret = _kinds(sugg, "retention")
    assert {s.group for s in ret} == {"/app/forever"}
    by_days = {int(s.title.split("-")[0].split()[-1]): s for s in ret}
    # 1000 GB over 365 days -> about 82 GB at 30 days, 247 GB at 90
    assert by_days[30].monthly_usd == pytest.approx((1000 - 1000 * 30 / 365) * 0.03)
    assert by_days[90].monthly_usd == pytest.approx((1000 - 1000 * 90 / 365) * 0.03)
    assert "--retention-in-days 30" in by_days[30].command and "/app/forever" in by_days[30].command
    assert combined == pytest.approx(by_days[30].monthly_usd)


def test_young_group_retention_saves_nothing(prices):
    g = group(stored_gb=10, age_days=20)
    assert projected_stored_bytes(g, 30, NOW_MS) == g.stored_bytes
    assert retention_saving(g, 30, NOW_MS, prices) == 0
    assert not _kinds(suggest([g], prices, NOW_MS)[0], "retention")


def test_infrequent_access_needs_no_filters_and_few_queries(prices):
    ok = group("/app/quiet", gb_month=100, subscription_filters=0, recent_queries=0)
    filt = group("/app/metric", gb_month=100, subscription_filters=0, metric_filters=1)
    sub = group("/app/sub", gb_month=100, subscription_filters=1)
    busy = group("/app/busy", gb_month=100, subscription_filters=0, recent_queries=50)
    unknown = group("/app/unchecked", gb_month=100)
    price_groups([ok, filt, sub, busy, unknown], prices)
    assert ia_eligible(ok) == (True, "")
    for g in (filt, sub, busy, unknown):
        assert ia_eligible(g)[0] is False
    sugg, _ = suggest([ok, filt, sub, busy, unknown], prices, NOW_MS)
    ia = _kinds(sugg, "infrequent_access")
    assert [s.group for s in ia] == ["/app/quiet"]
    assert ia[0].monthly_usd == pytest.approx(100 * (0.5 - 0.25))


def test_lambda_platform_lines_and_debug_in_prod(prices):
    lam = group("/aws/lambda/checkout-prod", gb_month=100, vended=True)
    api = group("/ecs/api-prod", gb_month=100)
    stg = group("/ecs/api-staging", gb_month=100)
    price_groups([lam, api, stg], prices)
    lam.patterns = [Pattern("p1", "START RequestId: <UUID-1> Version: $LATEST", 10, 0.3, byte_share=0.2, monthly_usd=10),
                    Pattern("p2", "REPORT RequestId: <UUID-1> Duration: <Number-2> ms", 10, 0.3, byte_share=0.3,
                            monthly_usd=15)]
    api.patterns = [Pattern("p3", '{"level":"debug","msg":"cache lookup took <Number-1> ms"}', 5, 0.5,
                            byte_share=0.5, monthly_usd=25)]
    stg.patterns = [Pattern("p4", "DEBUG cache lookup took <Number-1> ms", 5, 0.5, byte_share=0.5, monthly_usd=25)]
    sugg, combined = suggest([lam, api, stg], prices, NOW_MS)
    (l,) = _kinds(sugg, "lambda_platform")
    assert l.monthly_usd == pytest.approx(25) and set(l.pattern_ids) == {"p1", "p2"}
    assert "--function-name checkout-prod" in l.command and "SystemLogLevel=WARN" in l.command
    (d,) = _kinds(sugg, "debug_in_prod")
    assert d.group == "/ecs/api-prod" and d.monthly_usd == pytest.approx(25)
    assert "debug_in_prod" in api.patterns[0].flags and "debug_in_prod" not in stg.patterns[0].flags
    # a line that is both DEBUG and noisy is counted once in the total
    assert combined == pytest.approx(25 + 25 + 25)


def test_container_insights_flagged(prices):
    g = group("/aws/ecs/containerinsights/prod-cluster/performance", gb_month=40)
    price_groups([g], prices)
    (c,) = _kinds(suggest([g], prices, NOW_MS)[0], "container_insights")
    assert c.monthly_usd == pytest.approx(20)


def test_combined_never_exceeds_group_cost(prices):
    g = group("/app/x", gb_month=10, stored_gb=100, age_days=1000, subscription_filters=0, recent_queries=0)
    price_groups([g], prices)
    g.patterns = [Pattern(f"p{i}", f"line number {i} here", 1, 0.3, byte_share=0.4, monthly_usd=g.ingest_usd * 0.4)
                  for i in range(5)]  # overlapping estimates adding up to 200%
    _, combined = suggest([g], prices, NOW_MS)
    assert combined <= g.monthly_usd + 1e-9
