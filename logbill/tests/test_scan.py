import json

import pytest

from logbill.awsread import INSIGHTS_OPERATIONS, READ_OPERATIONS
from logbill.prices import GB
from tests.scenario import EMAIL, scan, stub_account


def test_full_scan(factory, prices):
    stub_account(factory)
    prompts = []
    r = scan(factory, prices, confirm=lambda p: prompts.append(p) or True)
    for s in factory.stubs.values():
        s.assert_no_pending_responses()
    t = r["totals"]
    # api: 60 GB x $0.50 + 500 GB x $0.03; lambda: 30 GB x $0.50 + 5 GB x $0.03; staging: 1 GB x $0.03
    assert t["monthly_usd"] == pytest.approx(30 + 15 + 15 + 0.15 + 0.03)
    assert t["never_expire"] == 1 and r["account"] == "123456789012"
    assert [g["name"] for g in r["groups"]][0] == "/ecs/api-prod"

    # Insights asked once with the estimate, ran within the budget
    assert len(prompts) == 1 and "3.00 GB" in prompts[0] and "budget 5 GB" in prompts[0]
    ins = r["insights"]
    assert ins["ran"] and ins["planned_gb"] == pytest.approx(3.0) and ins["scanned_gb"] == pytest.approx(3.0)
    assert ins["usd"] == pytest.approx(3.0 * 0.005)
    assert {s["group"]: s["reason"] for s in ins["skipped"]} == {"us-east-1:/app/kept-staging": "no ingestion"}

    kinds = {s["kind"] for s in r["suggestions"]}
    assert {"retention", "debug_in_prod", "lambda_platform", "noisy_pattern", "infrequent_access"} <= kinds
    assert 0 < t["savings_usd"] <= t["monthly_usd"]

    # only allowlisted calls were made; Insights only on the Insights client
    assert set(factory.ops) <= READ_OPERATIONS | INSIGHTS_OPERATIONS
    assert factory.ops.count("StartQuery") == 2
    read_client_ops = factory.ops  # recorded across clients
    assert "PutRetentionPolicy" not in read_client_ops

    text = json.dumps(r)
    assert EMAIL not in text and "example.com" not in text


def test_no_confirmation_means_no_insights(factory, prices):
    stub_account(factory, insights=False)
    r = scan(factory, prices, confirm=lambda p: False)
    assert "StartQuery" not in factory.ops
    assert not r["insights"]["ran"] and r["insights"]["est_usd"] > 0
    assert any("Logs Insights skipped" in n for n in r["notes"])
    assert all(not g["patterns"] for g in r["groups"])


def test_budget_zero_never_asks(factory, prices):
    stub_account(factory, insights=False)
    r = scan(factory, prices, confirm=lambda p: pytest.fail("must not ask"), budget_gb=0)
    assert "StartQuery" not in factory.ops and not r["insights"]["ran"]


def test_small_budget_shrinks_the_scan(factory, prices):
    stub_account(factory, insights=False)
    prompts = []
    r = scan(factory, prices, confirm=lambda p: prompts.append(p) or False, budget_gb=0.5)
    assert r["insights"]["planned_gb"] <= 0.5
    assert "budget 0.5 GB" in prompts[0]


def test_all_regions_failing_is_an_error(factory, prices):
    from logbill.scan import ScanFailed

    factory.stub("sts").add_client_error("get_caller_identity", "ExpiredToken")
    factory.stub("logs").add_client_error("describe_log_groups", "AccessDeniedException", "secret detail")
    with pytest.raises(ScanFailed) as e:
        scan(factory, prices)
    assert "AccessDeniedException" in str(e.value) and "secret detail" not in str(e.value)


def test_per_group_ingest_is_window_scaled(factory, prices):
    stub_account(factory)
    r = scan(factory, prices)
    api = r["groups"][0]
    assert api["ingested_bytes"] == pytest.approx(60 * GB)
    assert api["monthly_ingest_gb"] == pytest.approx(60)


def test_cli_scan_writes_html_and_json(factory, tmp_path, capsys, monkeypatch):
    from types import SimpleNamespace

    from logbill import cli

    stub_account(factory)
    monkeypatch.setattr(cli, "_session", lambda profile: SimpleNamespace(region_name="us-east-1"))
    monkeypatch.setattr(cli, "_factory", lambda session: factory)
    out = tmp_path / "bill.html"
    assert cli.main(["scan", "--out", str(out), "--yes"]) == 0
    assert out.read_text().startswith("<!doctype html>")
    doc = json.loads((tmp_path / "bill.json").read_text())
    assert doc["insights"]["ran"]
    printed = capsys.readouterr().out
    assert f"report: {out}" in printed and EMAIL not in printed


def test_cli_scan_rejects_bad_args():
    from logbill import cli

    assert cli.main(["scan", "--days", "0"]) == 2
    assert cli.main(["scan", "--retention-days", "45"]) == 2
