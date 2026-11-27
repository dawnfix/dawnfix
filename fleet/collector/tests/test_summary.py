import copy
import json

import jsonschema
import pytest

from dawnfix_fleet import SCHEMA
from dawnfix_fleet import summary as S

from .conftest import FIXTURE_PATH, schema, schema_validate


@pytest.fixture
def doc():
    return json.loads(FIXTURE_PATH.read_text())


def test_validator_and_schema_file_agree_on_every_key_and_enum():
    s = schema()
    acct = s["properties"]["accounts"]["items"]
    assert s["properties"]["schema"]["const"] == SCHEMA
    assert set(S.TOP_KEYS) == set(s["properties"]) == set(s["required"])
    assert set(S.ACCOUNT_KEYS) == set(acct["properties"]) == set(acct["required"])
    for name, keys in (("alarms", S.ALARM_KEYS), ("spend", S.SPEND_KEYS), ("certs", S.CERT_KEYS),
                       ("orphans", S.ORPHAN_KEYS)):
        assert set(keys) == set(acct["properties"][name]["properties"]) == set(acct["properties"][name]["required"])
    assert list(S.PROVIDERS) == acct["properties"]["provider"]["enum"]
    assert list(S.ENVS) == acct["properties"]["env"]["enum"]
    assert list(S.CREDENTIALS) == acct["properties"]["credential"]["enum"]
    assert list(S.STATUSES) == s["$defs"]["status"]["enum"]
    assert list(S.CURRENCIES) == acct["properties"]["spend"]["properties"]["currency"]["enum"]
    assert s["properties"]["accounts"]["maxItems"] == S.MAX_ACCOUNTS


def test_the_fixture_is_valid_both_ways(doc):
    schema_validate(doc)
    S.validate(doc)


@pytest.mark.parametrize("mutate, path", [
    (lambda d: d.update(note="hello"), ""),
    (lambda d: d["accounts"][0].update(name="Client"), "/accounts/0"),
    (lambda d: d["accounts"][0]["alarms"].update(firing="3"), "/accounts/0/alarms/firing"),
    (lambda d: d["accounts"][0]["alarms"].update(firing=True), "/accounts/0/alarms/firing"),
    (lambda d: d["accounts"][0]["alarms"].update(firing=-1), "/accounts/0/alarms/firing"),
    (lambda d: d["accounts"][0].update(account="111122223333"), "/accounts/0/account"),
    (lambda d: d["accounts"][0].update(env="Production"), "/accounts/0/env"),
    (lambda d: d["accounts"][0]["spend"].update(currency="usd"), "/accounts/0/spend/currency"),
    (lambda d: d["accounts"][0]["spend"].update(as_of="yesterday"), "/accounts/0/spend/as_of"),
    (lambda d: d["accounts"][0]["certs"].update(min_days_left=99999), "/accounts/0/certs/min_days_left"),
    (lambda d: d.update(schema="dawnfix.fleet/2"), "/schema"),
    (lambda d: d.update(generated_at="2026-10-27 06:05"), "/generated_at"),
])
def test_rejects_with_both_validators(doc, mutate, path):
    mutate(doc)
    with pytest.raises(S.SummaryError) as e:
        S.validate(doc)
    assert e.value.path == path
    with pytest.raises(jsonschema.ValidationError):
        schema_validate(doc)


def test_a_repeated_account_is_refused(doc):
    """Also beyond JSON Schema (no uniqueness by field); the board checks it too."""
    doc["accounts"].append(copy.deepcopy(doc["accounts"][0]))
    with pytest.raises(S.SummaryError, match="duplicate"):
        S.validate(doc)


def test_numbers_must_follow_status(doc):
    """The schema cannot say this; the validator can, and the board's does too."""
    bad = copy.deepcopy(doc)
    bad["accounts"][0]["alarms"]["status"] = "denied"
    with pytest.raises(S.SummaryError, match="must be null unless status is ok"):
        S.validate(bad)
    bad = copy.deepcopy(doc)
    bad["accounts"][0]["spend"]["this_week_cents"] = None
    with pytest.raises(S.SummaryError, match="required when status is ok"):
        S.validate(bad)
    ok = copy.deepcopy(doc)
    ok["accounts"][0]["certs"]["min_days_left"] = None  # no certificate in use
    S.validate(ok)


def test_too_many_accounts(doc):
    doc["accounts"] = [dict(doc["accounts"][0], account=f"{i:016x}") for i in range(51)]
    with pytest.raises(S.SummaryError, match="too many"):
        S.validate(doc)
