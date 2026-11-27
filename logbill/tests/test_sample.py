import json
import re

from logbill import brand
from sample import make_sample


def test_sample_files_are_current():
    """sample/report.html and sample.json are generated; regenerate after a report change."""
    assert make_sample.main(["--check"]) == 0


def test_sample_is_synthetic_and_inert():
    html, doc = make_sample.build()
    d = json.loads(doc)
    assert d["schema"] == make_sample.SCHEMA and d["html"] == html
    assert d["report"]["account"] == "123456789012" and d["report"]["sample"] is True
    assert "Sample report." in html and "<title>Sample: " in html
    low = html.lower()
    for bad in ("<script", "href=", "src=", "https://", "@example.com", "alert(1)"):
        assert bad not in low, bad
    assert set(re.findall(r"(?<!\d)\d{12}(?!\d)", html)) == {"123456789012"}


def test_sample_ends_with_the_pitch():
    html, doc = make_sample.build()
    assert brand.PITCH_LINE in html and brand.PITCH_TEXT in html
    assert json.loads(doc)["report"]["pitch"]["url"] == brand.PITCH_URL
