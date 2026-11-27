import pytest

from dawnfix_fleet.config import ConfigError, load, parse

from .conftest import ACCOUNT, ROLE, SLUG, config


def test_a_full_account_parses():
    c = config(regions=["us-east-1", "eu-west-1"], checks=["alarms", "certs"])[SLUG]
    a = c.accounts[0]
    assert a.assume and a.role_arn == ROLE and a.external_id_env == "FLEET_EXTERNAL_ID"
    assert a.regions == ("us-east-1", "eu-west-1")
    assert a.checks == {"alarms", "certs"}


def test_checks_default_to_all_three():
    assert config()[SLUG].accounts[0].checks == {"alarms", "spend", "certs"}


def test_own_ci_needs_no_role():
    a = config(role_arn=None, external_id_env=None)[SLUG].accounts[0]
    assert not a.assume


@pytest.mark.parametrize("change, message", [
    ({"external_id_env": None}, "required with role_arn"),
    ({"role_arn": "arn:aws:iam::999999999999:role/fleet-read"}, "account differs"),
    ({"role_arn": "not-an-arn"}, "not an IAM role ARN"),
    ({"provider": "gcp"}, "not implemented"),
    ({"provider": "azure"}, "must be aws"),
    ({"env": "production"}, "one of"),
    ({"account_id": "12345"}, "twelve digits"),
    ({"regions": []}, "1 to 20"),
    ({"regions": ["us-east-1", "us-east-1"]}, "duplicates"),
    ({"regions": ["US East"]}, "not a region"),
    ({"checks": ["orphans"]}, "one of"),
    ({"external_id_env": "lower-case"}, "environment variable"),
    ({"name": "Some Client"}, "unknown key"),
])
def test_rejects(change, message):
    with pytest.raises(ConfigError, match=message):
        config(**change)


def test_external_id_without_role_is_refused():
    with pytest.raises(ConfigError, match="only meaningful"):
        config(role_arn=None)


def test_client_keys_are_slugs_and_accounts_unique():
    acct = {"provider": "aws", "env": "prod", "account_id": ACCOUNT, "regions": ["us-east-1"]}
    with pytest.raises(ConfigError, match="board slugs"):
        parse({"version": 1, "clients": {"Big Client Inc": {"accounts": [acct]}}})
    with pytest.raises(ConfigError, match="same account twice"):
        parse({"version": 1, "clients": {SLUG: {"accounts": [acct, dict(acct)]}}})
    with pytest.raises(ConfigError, match="version"):
        parse({"version": 2, "clients": {SLUG: {"accounts": [acct]}}})


def test_example_config_loads():
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "examples" / "fleet.yml"
    clients = load(str(example))
    assert len(clients) == 2


def test_unreadable_and_invalid_yaml(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load(str(tmp_path / "missing.yml"))
    bad = tmp_path / "bad.yml"
    bad.write_text("clients: [")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load(str(bad))
