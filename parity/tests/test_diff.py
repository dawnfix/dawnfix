import io
import json

import pytest

from dawnfix_parity.cli import run
from dawnfix_parity.collect import collect
from dawnfix_parity.config import load
from dawnfix_parity.diff import diff
from dawnfix_parity.model import ValueHasher
from dawnfix_parity.resolve import Resolver
from tests.conftest import DEV, NOW, PLANTED, WORLD


def run_diff(world, config_file, hashes=False, salt=None):
    cfg = load(config_file)
    world.queue_env("dev", hashes)
    world.queue_env("prod", hashes)
    envs = [cfg.env("dev"), cfg.env("prod")]
    awss = {e.name: world.factory(e) for e in envs}
    snaps = collect(envs, awss, ValueHasher(salt) if hashes else None)
    res = diff(cfg, snaps["dev"], snaps["prod"], Resolver(snaps, cfg.envs, awss))
    world.assert_done()
    return res, snaps


def kinds(res):
    return {(f.kind, f.key) for f in res.findings}


def test_diff_findings(world, config_file):
    res, _ = run_diff(world, config_file)
    k = kinds(res)
    # normalised: /shop/dev/X and /shop/prod/X both become ssm:X
    assert ("missing_in_right", "ssm:DEBUG_TOOLBAR") in k
    assert ("missing_in_left", "ssm:NEW_FEATURE") in k
    assert ("missing_in_left", "secret:legacy") in k
    assert ("type_mismatch", "ssm:API_KEY") in k
    # env_token normalises shop-api-dev / shop-api-prod
    assert ("missing_in_right", "ecs:shop-api-{env}/app/CONFIG_PATH") in k
    assert ("missing_in_left", "ecs:shop-api-{env}/app/REDIS") in k
    assert ("missing_in_right", "lambda:shop-{env}-worker/QUEUE") in k
    assert ("missing_in_left", "lambda:shop-{env}-worker/PASSWORD") in k
    # nothing reported for keys that match
    assert not any(key in ("ssm:DB_URL", "ssm:LOG_LEVEL", "secret:stripe") for _, key in k)
    assert not any("unrelated-fn" in key for _, key in k)


def test_plain_vs_secret_ref_is_high_severity(world, config_file):
    res, _ = run_diff(world, config_file)
    f = next(f for f in res.findings if f.key == "ecs:shop-api-{env}/app/STRIPE")
    assert f.kind == "type_mismatch" and f.severity == "high"
    assert f.message == "secret-ref in dev, plain in prod"


def test_dangling_and_cross_env_references(world, config_file):
    res, _ = run_diff(world, config_file)
    dang = {f.details["target"] for f in res.findings if f.kind == "dangling_reference"}
    assert dang == {"/shop/prod/DB_URL_OLD", "/shop/dev/"}
    cross = {(f.env, f.details["var"], f.details["other_env"]) for f in res.findings if f.kind == "cross_env_reference"}
    assert cross == {("prod", "REDIS", "dev"), ("prod", "CONFIG_PREFIX", "dev")}
    # dev's own references (ARN with -AbCdEf suffix, prefix CONFIG_PATH) all resolve
    assert not any(f.env == "dev" and "reference" in f.kind for f in res.findings)


def test_findings_sorted_high_first(world, config_file):
    res, _ = run_diff(world, config_file)
    sev = [f.severity for f in res.findings]
    assert sev == sorted(sev, key=["high", "medium", "low", "info"].index)


def test_whole_function_missing_collapses(world, config_file, session):
    from dawnfix_parity.config import parse
    import yaml

    doc = yaml.safe_load(config_file.read_text())
    doc["environments"]["prod"]["lambda"]["functions"] = ["shop-prod-*", "unrelated-fn"]
    config_file.write_text(yaml.safe_dump(doc))
    res, _ = run_diff(world, config_file)
    f = [f for f in res.findings if "unrelated-fn" in f.key]
    assert len(f) == 1 and f[0].key == "lambda:unrelated-fn/*" and f[0].message == "whole function missing in dev"


def test_allow_list_marks_findings(world, config_file):
    config_file.write_text(config_file.read_text() + "allow:\n  - {kind: missing_in_right, key: 'ssm:DEBUG_*', reason: dev only}\n")
    res, _ = run_diff(world, config_file)
    f = next(f for f in res.findings if f.key == "ssm:DEBUG_TOOLBAR")
    assert f.allowed and f.allow_reason == "dev only" and f not in res.active()


def test_duplicate_key_after_normalisation(world, config_file):
    config_file.write_text(config_file.read_text().replace(
        "      - env_token: dev\n", "      - env_token: dev\n      - regex: {pattern: '^(DEBUG_TOOLBAR|LOG_LEVEL)$', to: SAME}\n        kinds: [ssm]\n"))
    res, _ = run_diff(world, config_file)
    dup = [f for f in res.findings if f.kind == "duplicate_key"]
    assert dup and dup[0].details["names"] == ["/shop/dev/DEBUG_TOOLBAR", "/shop/dev/LOG_LEVEL"]


def test_hashes_compare_without_exposing_values(world, config_file):
    salt = b"s" * 32
    res, snaps = run_diff(world, config_file, hashes=True, salt=salt)
    k = kinds(res)
    assert ("value_shared", "ssm:DB_URL") in k            # SecureString identical in dev and prod
    assert ("value_differs", "ecs:shop-api-{env}/app/LOG_FORMAT") in k   # must_match
    assert not any(key == "ssm:LOG_LEVEL" for kind, key in k)           # equal String: fine
    assert res.counts["values_equal"] >= 2 and res.counts["values_differ"] >= 1
    digests = {i.digest for s in snaps.values() for i in s.items if i.digest}
    assert digests
    from dawnfix_parity import report
    for render in (report.diff_text, report.diff_markdown, report.diff_json):
        out = render(res, ("value_shared",))
        for v in list(PLANTED.values()) + ["PLANTED-legacy"]:
            assert v not in out
        assert not any(d in out for d in digests)
        assert "PLANTED" not in out
    # the digests are not in any serialised form of the items either
    dumped = json.dumps([i.to_dict() for s in snaps.values() for i in s.items], default=str)
    assert "PLANTED" not in dumped and not any(d in dumped for d in digests)
    assert "digest" not in repr(snaps["dev"].items[0])
    assert "salt" in repr(ValueHasher()) and "sss" not in repr(ValueHasher(salt))


def test_without_hashes_no_value_calls(world, config_file):
    # Stubber would fail on an unexpected get_parameters / get_secret_value call
    res, snaps = run_diff(world, config_file, hashes=False)
    assert not res.hashed and all(i.digest is None for s in snaps.values() for i in s.items)


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_cli_output_never_has_values(world, config_file, fmt):
    world.queue_env("dev", True)
    world.queue_env("prod", True)
    out, err = io.StringIO(), io.StringIO()
    code = run(["-c", str(config_file), "diff", "--left", "dev", "--right", "prod", "--compare-hashes",
                "--format", fmt], aws_factory=world.factory, now=NOW, out=out, err=err)
    assert code == 0, err.getvalue()
    text = out.getvalue() + err.getvalue()
    assert "PLANTED" not in text and "hunter2" not in text
    assert "ssm:API_KEY" in text


def test_hasher_is_salted_per_run():
    a, b = ValueHasher(), ValueHasher()
    assert a.digest("x") != b.digest("x") and a.digest("x") == a.digest("x")
    import hashlib
    assert a.digest("x") != hashlib.sha256(b"x").hexdigest()
