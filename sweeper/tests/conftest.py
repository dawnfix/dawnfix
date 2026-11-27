import boto3
import pytest
from botocore.stub import Stubber

from dawnfix_sweeper.guard import make_client
from dawnfix_sweeper.scan import Scanner

SERVICES = ["sts", "ec2", "elbv2", "elb", "elasticbeanstalk", "ecs", "rds", "cloudwatch", "logs", "route53"]


@pytest.fixture(autouse=True)
def no_real_aws(monkeypatch):
    """A client the test did not stub would hit AWS: refuse it."""
    def client(self, service, region):
        if (service, region) not in self._clients:
            raise AssertionError(f"unstubbed AWS client {service} {region}")
        return self._clients[(service, region)]

    monkeypatch.setattr(Scanner, "client", client)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def session():
    return boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")


@pytest.fixture
def stubs(session):
    clients, stubs = {}, {}
    for s in SERVICES:
        c = make_client(session, s, "us-east-1")
        clients[(s, "us-east-1")] = c
        stubs[s] = Stubber(c)
    yield clients, stubs
    for st in stubs.values():
        st.deactivate()


def activate(stubs):
    for st in stubs.values():
        st.activate()
