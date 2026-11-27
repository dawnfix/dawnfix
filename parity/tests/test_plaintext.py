"""Plaintext-secret-looking env vars: reported by name only, never by value."""
import io
import json

import pytest

from dawnfix_parity.cli import run
from dawnfix_parity.refs import Known, plaintext_secret_reason, refs_from_value
from tests.conftest import NOW, PLANTED
from tests.test_diff import run_diff

REGION = "eu-central-1"
KNOWN = Known(ssm_names={"/shop/prod/DB_PASSWORD"}, ssm_prefixes=["/shop/prod"])


def reason(var, value):
    return plaintext_secret_reason(var, value, refs_from_value("prod", "lambda", "fn", var, value, KNOWN, REGION))


@pytest.mark.parametrize("var", ["PASSWORD", "DB_PASSWORD", "dbPassword", "SMTP_PASSWD", "APP_SECRET",
                                 "JWT_SECRET", "GITHUB_TOKEN", "slackBotToken", "API_KEY", "STRIPE_API_KEY",
                                 "APIKEY", "PRIVATE_KEY", "JWT_PRIVATE_KEY", "AWS_SECRET_ACCESS_KEY",
                                 "OAUTH_CLIENT_SECRET", "DB_PWD", "GOOGLE_CREDENTIALS"])
def test_secret_names_with_a_literal_are_flagged(var):
    assert reason(var, "s3cr3t-literal-v4lue") == "name"


@pytest.mark.parametrize("var, value", [
    ("SECRET_ARN", "s3cr3t-literal"),                 # names a secret, does not hold one
    ("TOKEN_TTL", "3600"), ("PASSWORD_MIN_LENGTH", "12"), ("API_KEY_HEADER", "x-api-key"),
    ("SECRET_NAME", "shop/prod/stripe"), ("TOKEN_URL", "https://auth.example.com/token"),
    ("DB_PASSWORD", "/shop/prod/DB_PASSWORD"),         # a known SSM name: a reference
    ("DB_PASSWORD", "arn:aws:secretsmanager:eu-central-1:222222222222:secret:db-AbCdEf"),
    ("DB_PASSWORD", "arn:aws:kms:eu-central-1:222222222222:key/abc"),   # any ARN is not a literal
    ("API_KEY", ""), ("API_KEY", "none"), ("API_KEY", "${API_KEY}"), ("API_KEY", "{{resolve:ssm:/x}}"),
    ("SECRET_ENABLED", "true"), ("TOKENIZER", "word"), ("LOG_LEVEL", "info"), ("QUEUE", "jobs"),
    ("CONFIG_PATH", "/etc/app"), ("SECRET", "123456"),
])
def test_not_flagged(var, value):
    assert reason(var, value) is None


@pytest.mark.parametrize("value", ["sk_live_" + "a1B2" * 6, "AKIA" + "ABCDEFGHIJKLMNOP", "ghp_" + "x" * 36,
                                   "xoxb-1234567890-abcdefghij", "-----BEGIN RSA PRIVATE KEY-----\nMIIE"])
def test_known_credential_shapes_are_flagged_whatever_the_name(value):
    assert reason("STRIPE", value) == "value_shape"
    assert reason("SOMETHING", value) == "value_shape"


def test_url_with_credentials_under_a_secret_name_is_flagged():
    assert reason("DB_PASSWORD", "postgres://admin:pw@db/x") == "name"


def test_diff_reports_name_never_value(world, config_file):
    res, _ = run_diff(world, config_file)
    found = [f for f in res.findings if f.kind == "plaintext_secret"]
    assert [(f.env, f.key, f.details) for f in found] == [
        ("prod", "lambda:shop-{env}-worker/PASSWORD", {"name": "shop-prod-worker/PASSWORD", "reason": "name"})]
    assert found[0].severity == "high" and found[0] in res.active()
    assert res.counts["plaintext_secret"] == 1
    text = json.dumps([f.to_dict() for f in res.findings])
    assert PLANTED["password"] not in text and "hunter2" not in text


def test_reason_is_kept_in_meta_but_not_the_value(world, config_file):
    _, snaps = run_diff(world, config_file)
    it = next(i for i in snaps["prod"].items if i.name == "shop-prod-worker/PASSWORD")
    assert it.meta["plaintext_secret"] == "name"
    assert "hunter2" not in json.dumps(it.to_dict(), default=str)


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_every_format_shows_the_finding_without_the_value(world, config_file, fmt):
    world.queue_env("dev")
    world.queue_env("prod")
    out, err = io.StringIO(), io.StringIO()
    code = run(["-c", str(config_file), "diff", "--left", "dev", "--right", "prod", "--format", fmt],
               aws_factory=world.factory, now=NOW, out=out, err=err)
    assert code == 0, err.getvalue()
    assert "PASSWORD" in out.getvalue() and "hunter2" not in out.getvalue() + err.getvalue()


def test_allow_list_silences_it(world, config_file):
    config_file.write_text(config_file.read_text() + "allow:\n  - {kind: plaintext_secret, key: 'lambda:*/PASSWORD', reason: rotated test creds}\n")
    res, _ = run_diff(world, config_file)
    f = next(f for f in res.findings if f.kind == "plaintext_secret")
    assert f.allowed and f not in res.active()
