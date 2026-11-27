import json
import re

from logbill import brand
from logbill.report import render_html, render_json, summary_text
from tests.scenario import EMAIL, scan, stub_account


def _report(factory, prices):
    stub_account(factory)
    return scan(factory, prices)


def test_html_renders_the_numbers(factory, prices):
    r = _report(factory, prices)
    html = render_html(r)
    assert html.startswith("<!doctype html>")
    assert "/ecs/api-prod" in html and "never expires" in html
    assert "$60.18" in html  # monthly total
    assert "Biggest savings" in html and "put-retention-policy" in html
    assert brand.PITCH_LINE in html
    assert 'name="viewport"' in html and "prefers-color-scheme:light" in html
    assert '<article class="doc">' in html and "--doc-accent:#1a5e33" in html  # the shared document style


def test_html_has_no_external_assets_or_urls(factory, prices):
    html = render_html(_report(factory, prices))
    low = html.lower()
    for bad in ("<script", "<link", "<img", "<iframe", "src=", "href=", "url(", "@import", "http://", "https://"):
        assert bad not in low, bad
    assert not re.search(r"//[a-z0-9-]+\.[a-z]", low)


def test_html_escapes_and_redacts_pattern_text(factory, prices):
    html = render_html(_report(factory, prices))
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert EMAIL not in html and ":email" in html


def test_html_without_insights(factory, prices):
    stub_account(factory, insights=False)
    r = scan(factory, prices, confirm=lambda p: False)
    html = render_html(r)
    assert "Logs Insights did not run" in html and "No Logs Insights query ran" in html


def test_json_round_trips_and_summary(factory, prices, tmp_path):
    r = _report(factory, prices)
    doc = json.loads(render_json(r))
    assert doc["schema"] == brand.REPORT_SCHEMA and doc["totals"]["groups"] == 3
    assert doc["pitch"] == {"product": brand.PITCH_PRODUCT, "line": brand.PITCH_LINE, "url": brand.PITCH_URL,
                            "install": brand.PITCH_INSTALL}
    s = summary_text(r, "a.html", "a.json")
    assert "report: a.html" in s and EMAIL not in s
