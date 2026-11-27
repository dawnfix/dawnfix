"""A two-account world (dev 111..., prod 222...) served by botocore Stubbers.

No request leaves the process: every client is a real boto3 client wrapped by the
read-only guard with a Stubber activated, and the session has dummy credentials.
"""
from __future__ import annotations

import textwrap
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from botocore.stub import Stubber

from dawnfix_parity.aws import EnvAws, make_client

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
REGION = "eu-central-1"
DEV, PROD = "111111111111", "222222222222"

# Values that must never appear in any output.
PLANTED = {
    "db": "postgres://admin:PLANTED-db-pass@db.internal/shop",
    "stripe_dev": "sk_test_PLANTED_dev",
    "stripe_prod": "sk_live_PLANTED_prod",
    "password": "hunter2-PLANTED",
    "api_key_dev": "PLANTED-api-key-dev",
    "api_key_prod": "PLANTED-api-key-prod",
}

CONFIG = textwrap.dedent(f"""
    version: 1
    environments:
      dev:
        region: {REGION}
        account_id: "{DEV}"
        ssm: {{paths: [/shop/dev]}}
        secrets: {{prefixes: [shop/dev/]}}
        ecs: {{cluster: shop-dev, services: ["shop-api-*"]}}
        lambda: {{functions: ["shop-dev-*"]}}
        normalize:
          - env_token: dev
      prod:
        region: {REGION}
        account_id: "{PROD}"
        ssm: {{paths: [/shop/prod]}}
        secrets: {{prefixes: [shop/prod/]}}
        ecs: {{cluster: shop-prod, services: ["shop-api-*"]}}
        lambda: {{functions: ["shop-prod-*"]}}
        normalize:
          - env_token: prod
    hashes:
      must_match: ["ecs:*/LOG_FORMAT"]
    inventory:
      unread_days: 90
      rotation_max_age_days: 90
""")


def ssm_arn(acct, name):
    return f"arn:aws:ssm:{REGION}:{acct}:parameter{name}"


def sm_arn(acct, name, suffix):
    return f"arn:aws:secretsmanager:{REGION}:{acct}:secret:{name}-{suffix}"


def param(acct, name, typ="String", version=3, days_ago=10):
    return {"Name": name, "ARN": ssm_arn(acct, name), "Type": typ, "Version": version,
            "LastModifiedDate": NOW - timedelta(days=days_ago), "LastModifiedUser": f"arn:aws:iam::{acct}:user/ops"}


def secret(acct, name, suffix, rotation=False, rotated_days=None, accessed_days=None, created_days=400):
    s = {"ARN": sm_arn(acct, name, suffix), "Name": name, "RotationEnabled": rotation,
         "LastChangedDate": NOW - timedelta(days=30), "CreatedDate": NOW - timedelta(days=created_days)}
    if rotated_days is not None:
        s["LastRotatedDate"] = NOW - timedelta(days=rotated_days)
    if accessed_days is not None:
        s["LastAccessedDate"] = NOW - timedelta(days=accessed_days)
    return s


WORLD = {
    "dev": {
        "params": [param(DEV, "/shop/dev/DB_URL", "SecureString"), param(DEV, "/shop/dev/LOG_LEVEL"),
                   param(DEV, "/shop/dev/DEBUG_TOOLBAR"), param(DEV, "/shop/dev/API_KEY")],
        "values": {"/shop/dev/DB_URL": PLANTED["db"], "/shop/dev/LOG_LEVEL": "info",
                   "/shop/dev/DEBUG_TOOLBAR": "on", "/shop/dev/API_KEY": PLANTED["api_key_dev"]},
        "secrets": [secret(DEV, "shop/dev/stripe", "AbCdEf")],
        "secret_values": {"shop/dev/stripe": PLANTED["stripe_dev"]},
        "service": "shop-api-dev",
        "task_def": {
            "family": "shop-api-dev", "revision": 7,
            "containerDefinitions": [{
                "name": "app",
                "environment": [{"name": "LOG_FORMAT", "value": "json"},
                                {"name": "CONFIG_PATH", "value": "/shop/dev/"}],
                "secrets": [{"name": "DB_URL", "valueFrom": ssm_arn(DEV, "/shop/dev/DB_URL")},
                            {"name": "STRIPE", "valueFrom": sm_arn(DEV, "shop/dev/stripe", "AbCdEf")}],
            }],
        },
        "functions": [{"FunctionName": "shop-dev-worker", "LastModified": "2026-10-01T00:00:00.000+0000",
                       "Environment": {"Variables": {"QUEUE": "shop-dev-jobs",
                                                     "SECRET_ARN": sm_arn(DEV, "shop/dev/stripe", "AbCdEf")}}}],
    },
    "prod": {
        "params": [param(PROD, "/shop/prod/DB_URL", "SecureString", version=1, days_ago=300),
                   param(PROD, "/shop/prod/LOG_LEVEL"), param(PROD, "/shop/prod/API_KEY", "SecureString"),
                   param(PROD, "/shop/prod/NEW_FEATURE")],
        "values": {"/shop/prod/DB_URL": PLANTED["db"], "/shop/prod/LOG_LEVEL": "info",
                   "/shop/prod/API_KEY": PLANTED["api_key_prod"], "/shop/prod/NEW_FEATURE": "true"},
        "secrets": [secret(PROD, "shop/prod/stripe", "XyZ123", rotation=True, rotated_days=200, accessed_days=1),
                    secret(PROD, "shop/prod/legacy", "LgCy01", accessed_days=120)],
        "secret_values": {"shop/prod/stripe": PLANTED["stripe_prod"], "shop/prod/legacy": "PLANTED-legacy"},
        "service": "shop-api-prod",
        "task_def": {
            "family": "shop-api-prod", "revision": 42,
            "containerDefinitions": [{
                "name": "app",
                "environment": [{"name": "LOG_FORMAT", "value": "text"},
                                {"name": "STRIPE", "value": PLANTED["stripe_prod"]}],
                "secrets": [{"name": "DB_URL", "valueFrom": "/shop/prod/DB_URL_OLD"},
                            {"name": "REDIS", "valueFrom": ssm_arn(DEV, "/shop/dev/DB_URL")}],
            }],
        },
        "functions": [{"FunctionName": "shop-prod-worker", "LastModified": "2026-10-01T00:00:00.000+0000",
                       "Environment": {"Variables": {"SECRET_ARN": sm_arn(PROD, "shop/prod/stripe", "XyZ123"),
                                                     "CONFIG_PREFIX": "/shop/dev/",
                                                     "PASSWORD": PLANTED["password"]}}},
                      {"FunctionName": "unrelated-fn", "Environment": {"Variables": {"X": "1"}}}],
    },
}


@pytest.fixture
def session():
    return boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name=REGION)


@pytest.fixture
def config_file(tmp_path):
    p = tmp_path / ".parity.yml"
    p.write_text(CONFIG)
    return p


class World:
    """Builds stubbed clients per environment and queues the responses collect() needs."""

    def __init__(self, session):
        self.session = session
        self.stubs: dict[tuple, Stubber] = {}
        self.clients: dict[str, dict] = {"dev": {}, "prod": {}}

    def stub(self, env, service) -> Stubber:
        key = (env, service)
        if key not in self.stubs:
            c = make_client(self.session, service, REGION)
            self.clients[env][(service, REGION)] = c
            self.stubs[key] = Stubber(c)
            self.stubs[key].activate()
        return self.stubs[key]

    def factory(self, env_conf):
        return EnvAws(env_conf, session=self.session, clients=self.clients[env_conf.name])

    def queue_env(self, env, hashes=False, lookups=True):
        w = WORLD[env]
        ssm, sm = self.stub(env, "ssm"), self.stub(env, "secretsmanager")
        ecs, lam = self.stub(env, "ecs"), self.stub(env, "lambda")
        ssm.add_response("describe_parameters", {"Parameters": w["params"]},
                         {"ParameterFilters": [{"Key": "Path", "Option": "Recursive", "Values": [f"/shop/{env}"]}],
                          "MaxResults": 50})
        sm.add_response("list_secrets", {"SecretList": w["secrets"]},
                        {"Filters": [{"Key": "name", "Values": [f"shop/{env}/"]}], "MaxResults": 100})
        if hashes:
            names = [p["Name"] for p in w["params"]]
            ssm.add_response("get_parameters", {"Parameters": [
                {"Name": n, "Type": "String", "Value": w["values"][n], "Version": 1} for n in names]},
                {"Names": names, "WithDecryption": True})
            for s in w["secrets"]:
                sm.add_response("get_secret_value", {"ARN": s["ARN"], "Name": s["Name"],
                                                     "SecretString": w["secret_values"][s["Name"]]},
                                {"SecretId": s["ARN"]})
        svc_arn = f"arn:aws:ecs:{REGION}:{DEV if env == 'dev' else PROD}:service/shop-{env}/{w['service']}"
        td_arn = f"arn:aws:ecs:{REGION}:{DEV if env == 'dev' else PROD}:task-definition/{w['task_def']['family']}:{w['task_def']['revision']}"
        ecs.add_response("list_services", {"serviceArns": [svc_arn]}, {"cluster": f"shop-{env}", "maxResults": 100})
        ecs.add_response("describe_services", {"services": [{"serviceName": w["service"], "taskDefinition": td_arn}]},
                         {"cluster": f"shop-{env}", "services": [svc_arn]})
        ecs.add_response("describe_task_definition", {"taskDefinition": w["task_def"]}, {"taskDefinition": td_arn})
        lam.add_response("list_functions", {"Functions": w["functions"]}, {"MaxItems": 50})
        if env == "prod" and lookups:
            # dangling bare valueFrom, then the /shop/dev/ prefix that prod's Lambda points at
            ssm.add_response("describe_parameters", {"Parameters": []},
                             {"ParameterFilters": [{"Key": "Name", "Option": "Equals",
                                                    "Values": ["/shop/prod/DB_URL_OLD"]}], "MaxResults": 10})
            ssm.add_response("describe_parameters", {"Parameters": []},
                             {"ParameterFilters": [{"Key": "Path", "Option": "Recursive", "Values": ["/shop/dev"]}],
                              "MaxResults": 1})

    def assert_done(self):
        for s in self.stubs.values():
            s.assert_no_pending_responses()


@pytest.fixture
def world(session):
    return World(session)
