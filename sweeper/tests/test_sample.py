import json
import re

from dawnfix_sweeper import constants
from sample import make_sample


def test_sample_is_current():
    """sample/sample.json is generated; regenerate after a plan change."""
    assert make_sample.main(["--check"]) == 0


def test_sample_is_synthetic():
    doc = make_sample.build()
    text = json.dumps(doc)
    assert set(re.findall(r"(?<!\d)\d{12}(?!\d)", text)) == {"123456789012"}
    assert doc["plan"]["executed"] is False and "**Nothing was deleted.**" in doc["markdown"]
    kinds = set(doc["plan"]["summary"]["by_kind"])
    assert {"nat_gateway", "classic_elb", "ec2_instance", "rds_instance", "rds_snapshot", "route53_record"} <= kinds
    assert doc["plan"]["pitch"]["url"] == constants.PITCH_URL
