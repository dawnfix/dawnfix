import json
import re

from dawnfix_leastpriv import constants
from sample import make_sample


def test_sample_is_current():
    """sample/sample.json is generated; regenerate after a PR body or patch change."""
    assert make_sample.main(["--check"]) == 0


def test_sample_is_synthetic_and_applies_nothing():
    doc = make_sample.build()
    assert set(re.findall(r"(?<!\d)\d{12}(?!\d)", json.dumps(doc))) == {"123456789012"}
    assert doc["report"]["applied"] is False and "nothing was applied to AWS" in doc["pr_markdown"]
    assert doc["patch"].startswith("--- a/iam/app.json\n+++ b/iam/app.json\n")
    assert doc["report"]["pitch"]["url"] == constants.PITCH_URL
