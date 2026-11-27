import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from dawnfix_core.normalize import Event

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)


def schema(name):
    return json.loads((SCHEMA_DIR / name).read_text())


def validate(doc, name):
    jsonschema.Draft202012Validator(schema(name)).validate(doc)


class FakeSource:
    """Stands in for AwsSource/GcpSource: returns canned events, or fails with a code."""

    type = "aws"

    def __init__(self, events=(), id="aws:us-east-1", fail=None):
        self.id = id
        self.type = id.split(":")[0]
        self._events = list(events)
        self.fail = fail
        self.windows = []
        self.truncated = False

    def events(self, window):
        from dawnfix_core.sources import SourceError

        self.windows.append(window)
        if self.fail:
            raise SourceError(self.fail)
        return list(self._events)


def log_event(message="TypeError: x is undefined", route="/users/:id", status=500, count=1, service="my-api-prod",
              method="GET", source="aws", error_class=None):
    from dawnfix_core.normalize import find_error_class

    return Event(
        source=source, source_id=f"{source}:us-east-1" if source == "aws" else "gcp:my-proj", kind="log",
        service=service, route=route, method=method, status=status,
        error_class=error_class or find_error_class(message, status), message=message,
        timestamp=NOW, count=count,
    )


BASE_CONFIG = """
version: 1
sources:
  - aws: { region: us-east-1, log_groups: [my-api-prod], alarms: true }
"""


@pytest.fixture
def write_config(tmp_path):
    def _write(text=BASE_CONFIG):
        p = tmp_path / ".dawnfix.yml"
        p.write_text(text)
        return p

    return _write
