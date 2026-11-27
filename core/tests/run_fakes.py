"""Fakes for the dawnfix run engine: HTTP with canned answers, and secret-shaped test values
built at run time (no literal key shape in this file)."""
import json
from urllib.parse import urlsplit

from dawnfix_core.run.web import Http, Response

AI_KEY = "sk-" + "ant-" + "k" * 40
HOST_TOKEN = "gh" + "s_" + "H" * 36
ENTERPRISE = "dp_" + "E" * 43


class FakeHttp(Http):
    """The real Http (https only, the token host check, no Authorization in headers) with a
    canned answer instead of the network: (method, path-prefix or URL-prefix) -> (status, payload)."""

    def __init__(self, answers=None):
        super().__init__()
        self.answers = list((answers or {}).items())
        self.calls = []

    def _send(self, method, url, headers, data):
        u = urlsplit(url)
        path = u.path + (f"?{u.query}" if u.query else "")
        self.calls.append({"method": method, "url": url, "path": path, "headers": dict(headers), "body": data})
        for (m, prefix), answer in self.answers:
            if m == method and (path.startswith(prefix) or url.startswith(prefix)):
                status, payload = answer
                text = payload if isinstance(payload, str) else json.dumps(payload)
                return Response(status, payload, text)
        return Response(404, {"message": "Not Found"}, "")

    def json(self, i):
        return json.loads(self.calls[i]["body"])
