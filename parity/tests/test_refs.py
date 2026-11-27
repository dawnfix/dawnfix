from dawnfix_parity.refs import (Known, parse_arn, refs_from_lambda, refs_from_task_definition,
                                   refs_from_value, secret_name_candidates, ssm_names_from_arn)
from dawnfix_parity.resolve import target_names
from tests.conftest import DEV, PLANTED, REGION, WORLD, sm_arn, ssm_arn

KNOWN = Known(ssm_names={"/shop/dev/DB_URL", "/shop/prod/DB_URL"}, secret_names={"shop/prod/stripe"},
              ssm_prefixes=["/shop/dev", "/shop/prod"], secret_prefixes=["shop/dev/", "shop/prod/"])


def test_task_definition_secrets_environment_and_registry():
    td = {"family": "f", "revision": 1, "containerDefinitions": [{
        "name": "app",
        "environment": [{"name": "A", "value": "plain"}, {"name": "P", "value": "/shop/prod/"}],
        "secrets": [{"name": "S1", "valueFrom": ssm_arn(DEV, "/shop/dev/DB_URL")},
                    {"name": "S2", "valueFrom": "/shop/prod/DB_URL"},
                    {"name": "S3", "valueFrom": sm_arn(DEV, "shop/dev/x", "AbCdEf") + ":password::"},
                    {"name": "S4", "valueFrom": "bare-name"}],
        "repositoryCredentials": {"credentialsParameter": sm_arn(DEV, "registry", "QwErTy")},
    }, {"name": "sidecar", "environment": [{"name": "B", "value": "x"}]}]}
    entries, refs = refs_from_task_definition("dev", "c/svc", td, KNOWN, REGION)
    assert [(c, v, t) for c, v, t, _ in entries] == [
        ("app", "A", "plain"), ("app", "P", "plain"), ("app", "S1", "secret-ref"), ("app", "S2", "secret-ref"),
        ("app", "S3", "secret-ref"), ("app", "S4", "secret-ref"), ("sidecar", "B", "plain")]
    assert all(v is None for _, _, t, v in entries if t == "secret-ref")
    by_var = {r.var: r for r in refs}
    assert by_var["P"].service == "ssm" and by_var["P"].prefix and by_var["P"].via == "environment"
    assert by_var["S1"].service == "ssm" and by_var["S1"].account == DEV
    assert by_var["S2"].service == "ssm" and by_var["S2"].target == "/shop/prod/DB_URL" and by_var["S2"].account is None
    assert by_var["S3"].service == "secretsmanager"
    assert target_names(by_var["S3"]) == ["shop/dev/x-AbCdEf", "shop/dev/x"]
    assert by_var["S4"].service == "ssm" and by_var["S4"].target == "bare-name"
    assert by_var["(registry)"].via == "repositoryCredentials"
    assert "A" not in by_var and "B" not in by_var


def test_lambda_env_refs_only_for_names():
    fn = {"FunctionName": "f", "Environment": {"Variables": {
        "ARN": "prefix " + sm_arn(DEV, "shop/dev/stripe", "AbCdEf") + " suffix",
        "NAME": "shop/prod/stripe", "PATH_REF": "/shop/dev/DB_URL", "PREFIX": "/shop/prod",
        "UNKNOWN_UNDER_PREFIX": "/shop/prod/NOPE",
        "PW": PLANTED["password"], "URL": "https://example.com/shop/dev/", "N": "42"}}}
    entries, refs = refs_from_lambda("dev", fn, KNOWN, REGION)
    assert len(entries) == 8
    got = {r.var: r for r in refs}
    assert set(got) == {"ARN", "NAME", "PATH_REF", "PREFIX", "UNKNOWN_UNDER_PREFIX"}
    assert got["ARN"].target == sm_arn(DEV, "shop/dev/stripe", "AbCdEf")   # the ARN only, not the whole value
    assert got["PREFIX"].prefix and not got["PATH_REF"].prefix
    assert all(PLANTED["password"] not in r.target for r in refs)


def test_value_that_is_not_a_name_is_dropped():
    for v in [None, "", "hello world", PLANTED["db"], "x" * 5000, "/etc/passwd"]:
        assert refs_from_value("dev", "lambda", "f", "V", v, KNOWN, REGION) == []


def test_arn_parsing_partitions_and_forms():
    assert parse_arn("arn:aws-us-gov:ssm:us-gov-west-1:123456789012:parameter/a/b")["service"] == "ssm"
    assert parse_arn("arn:aws:s3:::bucket") is None
    assert ssm_names_from_arn("parameter/a/b") == ["/a/b", "a/b"]
    assert ssm_names_from_arn("parameter/flat") == ["flat", "/flat"]
    assert secret_name_candidates("db-AbCdEf") == ["db-AbCdEf", "db"]
    assert secret_name_candidates("db") == ["db"]


def test_world_task_defs_parse():
    entries, refs = refs_from_task_definition("prod", "shop-prod/shop-api-prod", WORLD["prod"]["task_def"], KNOWN, REGION)
    assert {r.var for r in refs} == {"DB_URL", "REDIS"}
