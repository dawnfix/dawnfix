import json

import pytest

from logbill.model import from_api, price_groups
from logbill.prices import GB, Prices, default_path, tiered_cost
from tests.conftest import group


def test_price_table_is_the_bundled_file_and_has_sources():
    doc = json.loads(default_path().read_text())
    assert doc["source"]["publication_date"] and doc["source"]["retrieved"]
    assert doc["uncertain"]
    r = doc["regions"]["us-east-1"]
    assert (r["ingest_standard_gb"], r["ingest_ia_gb"], r["storage_gb_month"], r["insights_scanned_gb"]) == \
        (0.5, 0.25, 0.03, 0.005)
    for name, rates in doc["regions"].items():
        assert rates["ingest_ia_gb"] < rates["ingest_standard_gb"], name
        assert rates["vended_standard_tiers"][-1][0] is None, name


def test_unknown_region_falls_back_and_is_marked(prices):
    rates, approx = prices.region("xx-moon-1")
    assert approx and rates == prices.regions["us-east-1"]
    assert prices.region("eu-central-1")[1] is False


def test_tiered_cost():
    tiers = [[10, 1.0], [30, 0.5], [None, 0.1]]
    assert tiered_cost(tiers, 0) == 0
    assert tiered_cost(tiers, 5) == 5
    assert tiered_cost(tiers, 10) == 10
    assert tiered_cost(tiers, 20) == 10 + 5
    assert tiered_cost(tiers, 130) == pytest.approx(10 + 10 + 10)


def test_standard_ia_and_storage(prices):
    std = group("/app/api", gb_month=30, stored_gb=100)
    ia = group("/app/ia", gb_month=30, log_class="INFREQUENT_ACCESS")
    eu = group("/app/eu", region="eu-central-1", gb_month=10)
    price_groups([std, ia, eu], prices)
    assert std.monthly_ingest_gb == pytest.approx(30)
    assert std.ingest_usd == pytest.approx(15.0)
    assert std.storage_usd == pytest.approx(3.0)
    assert std.monthly_usd == pytest.approx(18.0)
    assert ia.ingest_usd == pytest.approx(7.5)
    assert eu.ingest_usd == pytest.approx(6.3)


def test_short_window_is_projected_to_a_month(prices):
    g = group(gb_month=0)
    g.days, g.ingested_bytes = 7, 7 * GB  # 1 GB/day
    price_groups([g], prices)
    assert g.monthly_ingest_gb == pytest.approx(30)
    assert g.ingest_usd == pytest.approx(15.0)


def test_vended_groups_share_the_region_tier():
    doc = Prices.load().doc
    doc = json.loads(json.dumps(doc))
    doc["regions"]["us-east-1"]["vended_standard_tiers"] = [[10, 1.0], [None, 0.1]]
    p = Prices(doc)
    a = group("/aws/lambda/a", gb_month=15, vended=True)
    b = group("/aws/lambda/b", gb_month=5, vended=True)
    price_groups([a, b], p)
    total = 10 * 1.0 + 10 * 0.1
    assert a.ingest_usd + b.ingest_usd == pytest.approx(total)
    assert a.ingest_usd == pytest.approx(total * 0.75)


def test_delivery_class_is_not_priced(prices):
    g = group(gb_month=50, stored_gb=10, log_class="DELIVERY")
    price_groups([g], prices)
    assert g.monthly_usd == 0
    assert not g.never_expires


def test_from_api_reads_describe_log_groups_fields(prices):
    g = from_api({"logGroupName": "/aws/lambda/x", "storedBytes": 123, "metricFilterCount": 2,
                  "logGroupClass": "INFREQUENT_ACCESS", "creationTime": 1, "retentionInDays": 14},
                 "us-east-1", prices)
    assert (g.stored_bytes, g.metric_filters, g.log_class, g.retention_days, g.vended) == \
        (123, 2, "INFREQUENT_ACCESS", 14, True)
    assert not from_api({"logGroupName": "/app"}, "us-east-1", prices).retention_days
