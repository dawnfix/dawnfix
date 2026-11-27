from sample import make_sample


def test_sample_is_current():
    """sample/sample.json is generated; regenerate after a comment change."""
    assert make_sample.main(["--check"]) == 0


def test_sample_comment_and_ingest():
    doc = make_sample.build()
    assert doc["comment_markdown"].startswith("<!-- dawnfix-receipt:sha=")
    assert "+$40.07/day" in doc["comment_markdown"] and "Provisional" in doc["provisional_markdown"]
    assert doc["ingest"]["deploys"][0]["delta_cents_per_day_bucket"] == 2000
