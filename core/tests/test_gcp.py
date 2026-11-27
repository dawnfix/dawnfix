from datetime import timedelta
from types import SimpleNamespace

import pytest

from dawnfix_core.config import GcpSourceConfig
from dawnfix_core.sources import SourceError, Window
from dawnfix_core.sources.gcp import GcpSource
from tests.conftest import NOW

WINDOW = Window(NOW - timedelta(minutes=60), NOW)


def entry(payload, labels=None, http=None, rtype="cloud_run_revision"):
    return SimpleNamespace(payload=payload, http_request=http, timestamp=NOW, severity="ERROR",
                           resource=SimpleNamespace(type=rtype, labels=labels or {}))


class FakeClient:
    def __init__(self, entries=(), error=None):
        self.entries, self.error, self.calls = list(entries), error, []

    def list_entries(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return iter(self.entries)


def test_entries_normalized():
    client = FakeClient([
        entry("Traceback (most recent call last): KeyError: 'user'", {"service_name": "my-api"}),
        entry({"message": "upstream failed", "error": {"name": "FetchError", "message": "timeout"}},
              {"function_name": "send-report"}),
        entry("boom", http={"requestMethod": "POST", "requestUrl": "https://example.com/orders/77?x=1", "status": 503},
              rtype="gae_app"),
    ])
    s = GcpSource(GcpSourceConfig(project="my-proj"), {"max_events_per_source": 100}, client=client)
    a, b, c = s.events(WINDOW)
    assert (a.service, a.error_class) == ("my-api", "KeyError")
    assert (b.service, b.error_class, b.message) == ("send-report", "FetchError", "timeout")
    assert (c.service, c.method, c.route, c.status) == ("gae_app", "POST", "/orders/:id", 503)
    f = client.calls[0]["filter_"]
    assert f.startswith("(severity>=ERROR) AND timestamp>=\"2026-10-27T09:00:00Z\"")
    assert 'timestamp<"2026-10-27T10:00:00Z"' in f
    assert client.calls[0]["resource_names"] == ["projects/my-proj"]


def test_cap():
    client = FakeClient([entry("x Error") for _ in range(10)])
    s = GcpSource(GcpSourceConfig(project="my-proj"), {"max_events_per_source": 4}, client=client)
    assert len(s.events(WINDOW)) == 4 and s.truncated


def test_api_error_code_only():
    class PermissionDenied(Exception):
        code = 403

    s = GcpSource(GcpSourceConfig(project="my-proj"), {}, client=FakeClient(error=PermissionDenied("jane@x.com")))
    with pytest.raises(SourceError) as e:
        s.events(WINDOW)
    assert e.value.code == "PermissionDenied_403"


def test_missing_dependency_is_clear(monkeypatch):
    import builtins

    real = builtins.__import__

    def fake(name, *a, **kw):
        if name.startswith("google"):
            raise ImportError(name)
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake)
    s = GcpSource(GcpSourceConfig(project="my-proj"), {})
    with pytest.raises(SourceError) as e:
        s.events(WINDOW)
    assert e.value.code == "gcp_dependency_missing" and "dawnfix-core[gcp]" in e.value.hint


def test_aws_only_import_does_not_need_google():
    import sys

    import dawnfix_core.cli  # noqa: F401
    import dawnfix_core.sources.gcp  # noqa: F401
    assert "google.cloud.logging" not in sys.modules
