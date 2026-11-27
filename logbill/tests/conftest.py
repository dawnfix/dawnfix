from datetime import datetime, timezone
from pathlib import Path

import boto3
import pytest
from botocore.stub import Stubber

from logbill.awsread import READ_OPERATIONS, make_client
from logbill.model import Group
from logbill.prices import GB, Prices

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
NOW_MS = int(NOW.timestamp() * 1000)
DAY_MS = 86_400_000
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session():
    return boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")


@pytest.fixture
def prices():
    return Prices.load()


class StubFactory:
    """Stands in for the CLI's client factory: one stubbed client per (service, region,
    allowlist), every operation name recorded before the request is built."""

    def __init__(self, session):
        self.session = session
        self.clients, self.stubs = {}, {}
        self.ops = []

    def __call__(self, service, region, allowed=READ_OPERATIONS):
        k = (service, region, frozenset(allowed))
        if k not in self.clients:
            c = make_client(self.session, service, region, allowed)
            s = Stubber(c)
            s.activate()
            # Ahead of the Stubber, so even a refused or unstubbed attempt is recorded.
            c.meta.events.register_first("before-parameter-build", self._record)
            self.clients[k], self.stubs[k] = c, s
        return self.clients[k]

    def _record(self, model=None, **_):
        if model is not None:
            self.ops.append(model.name)

    def stub(self, service, region="us-east-1", allowed=READ_OPERATIONS):
        self(service, region, allowed)
        return self.stubs[(service, region, frozenset(allowed))]


@pytest.fixture
def factory(session):
    return StubFactory(session)


def group(name="/app/api", region="us-east-1", gb_month=0.0, stored_gb=0.0, retention=None,
          age_days=365, **kw) -> Group:
    return Group(name=name, region=region, retention_days=retention, stored_bytes=int(stored_gb * GB),
                 created_ms=NOW_MS - age_days * DAY_MS, ingested_bytes=gb_month * GB, days=30, **kw)
