import pytest

from dawnfix_parity.config import ConfigError, Rule, load, parse


def base(**env):
    return {"version": 1, "environments": {"dev": {"region": "eu-central-1", **env}}}


def test_loads_example(config_file):
    cfg = load(config_file)
    assert set(cfg.envs) == {"dev", "prod"}
    dev = cfg.env("dev")
    assert dev.ssm_paths == ["/shop/dev"] and dev.ecs[0].cluster == "shop-dev"
    assert cfg.must_match == ["ecs:*/LOG_FORMAT"]


def test_example_file_in_repo_parses():
    from pathlib import Path

    cfg = load(Path(__file__).resolve().parent.parent / "examples" / ".parity.yml")
    assert {"dev", "prod"} <= set(cfg.envs)


@pytest.mark.parametrize("doc, msg", [
    ({}, "environments"),
    ({"environments": {"dev": {}}}, "region is required"),
    ({"version": 2, "environments": {"dev": {"region": "x"}}}, "version"),
    (base(normalize=[{"bogus": 1}]), "rule needs"),
    (base(normalize=[{"regex": {"pattern": "("}}]), "bad regex"),
    (base(normalize=[{"env_token": "dev", "kinds": ["nope"]}]), "unknown kinds"),
    (base(ecs={"services": ["a"]}), "cluster is required"),
    (base(account_id="123"), "12 digits"),
    ({"environments": {"dev": {"region": "x"}}, "allow": [{"kind": "x"}]}, "needs key"),
])
def test_config_errors(doc, msg):
    with pytest.raises(ConfigError, match=msg):
        parse(doc)


def test_unknown_env():
    cfg = parse(base())
    with pytest.raises(ConfigError, match="unknown environment 'prod'"):
        cfg.env("prod")


def test_normalise_strips_matched_prefix_then_rules():
    cfg = parse(base(ssm={"paths": ["/app/dev"]}, normalize=[{"replace": {"from": "_DEV", "to": ""}}]))
    e = cfg.env("dev")
    assert e.normalise("ssm", "/app/dev/db/URL_DEV", "/app/dev/") == "db/URL"


def test_strip_matched_prefix_can_be_disabled():
    e = parse(base(strip_matched_prefix=False, normalize=[{"strip_prefix": "/app/"}])).env("dev")
    assert e.normalise("ssm", "/app/dev/X", "/app/dev/") == "dev/X"


@pytest.mark.parametrize("name, out", [
    ("shop-api-dev", "shop-api-{env}"),
    ("/shop/dev/X", "/shop/{env}/X"),
    ("dev_db", "{env}_db"),
    ("developer-tools", "developer-tools"),    # not a whole token
    ("mydev-x", "mydev-x"),
])
def test_env_token(name, out):
    assert Rule("env_token", "dev").apply("ecs", name) == out


def test_rule_kinds_scope():
    r = Rule("regex", r"-v\d+$", "", kinds=("lambda",))
    assert r.apply("lambda", "fn-v2") == "fn" and r.apply("ssm", "fn-v2") == "fn-v2"
