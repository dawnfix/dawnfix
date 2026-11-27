"""HTTPS JSON calls with urllib, and the one place an Authorization header is added.

- https only; no redirect is ever followed (a 3xx comes back as the response);
- a token is attached only through `token=` (in Authorization, or GitLab's PRIVATE-TOKEN), and only when the request's host (and port)
  is exactly one of the caller's `allowed_hosts`: an adapter's API host, or the configured
  hosted-service host. Otherwise the call is refused before anything is sent;
- an Authorization or PRIVATE-TOKEN header passed in `headers` is refused, so nothing bypasses that check;
- never raises for an HTTP status, never logs headers.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass
class Response:
    status: int       # 0: no answer (network error or timeout)
    data: Any         # parsed JSON, or the text, or None
    text: str = ""


class TokenRefused(Exception):
    """A token was about to go to a host it is not for; nothing was sent."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def host_of(url: str) -> str:
    """host[:port] of a URL, lower-case; the default https port is dropped."""
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    return host if u.port in (None, 443) else f"{host}:{u.port}"


class Http:
    def __init__(self, opener=None, timeout: float = 20.0):
        self._open = opener or urllib.request.build_opener(_NoRedirect).open
        self.timeout = timeout

    def request(self, method: str, url: str, *, headers: dict | None = None, body: Any = None,
                token: str | None = None, scheme: str = "Bearer", allowed_hosts=(),
                token_header: str = "Authorization") -> Response:
        if not url.startswith("https://"):
            raise ValueError("only https URLs are called")
        hdrs = {"User-Agent": "dawnfix", **(headers or {})}
        if any(k.lower() in ("authorization", "private-token") for k in hdrs):
            raise ValueError("credentials go through token=, never in headers")
        if token is not None:
            allowed = {h.lower() for h in allowed_hosts}
            if not token or host_of(url) not in allowed:
                raise TokenRefused(f"refusing to send a token to {host_of(url) or '?'}: "
                                   f"it is only for {', '.join(sorted(allowed)) or 'no host'}")
            if token_header == "Authorization":
                hdrs["Authorization"] = f"{scheme} {token}"
            elif token_header == "PRIVATE-TOKEN":  # GitLab: the token alone, no scheme
                hdrs["PRIVATE-TOKEN"] = token
            else:
                raise ValueError("a token goes in Authorization or PRIVATE-TOKEN only")
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        return self._send(method, url, hdrs, data)

    def _send(self, method: str, url: str, headers: dict, data: bytes | None) -> Response:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._open(req, timeout=self.timeout) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, (e.read() or b"")
        except (urllib.error.URLError, OSError, ValueError):
            return Response(0, None)
        text = raw.decode("utf-8", "replace")
        try:
            parsed = json.loads(text) if text else None
        except ValueError:
            parsed = text
        return Response(status, parsed, text)
