"""Redaction of secrets from everything the engine prints: the values of every secret in the
environment (registered at start), and anything shaped like a credential, a token in a URL or
an Authorization header."""
import re
import sys
from urllib.parse import quote

# Shapes of credentials: the publish stage's scan uses the same list (publish.CREDENTIALS).
CREDENTIAL_SHAPES = [
    r"sk-ant-[A-Za-z0-9_-]{10,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"glpat-[A-Za-z0-9_-]{20,}",
    r"ATBB[A-Za-z0-9_=-]{20,}",
    r"(AKIA|ASIA)[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"dp_[A-Za-z0-9_-]{43}",
]
_PATTERNS = [
    (re.compile(r"(://)[^/\s:@]+:[^/\s@]+@"), r"\1***@"),
    (re.compile(r"(?i)\b((?:authorization:\s*)?(?:bearer|basic|token)\s+)[A-Za-z0-9._~+/=-]{16,}"), r"\1***"),
    (re.compile("|".join(CREDENTIAL_SHAPES)), "***"),
]


class Redactor:
    def __init__(self):
        self._values: set[str] = set()

    def add(self, value: str) -> None:
        if value and len(value) >= 4:
            self._values.add(value)
            self._values.add(quote(value, safe=""))

    def __call__(self, text: str) -> str:
        for v in sorted(self._values, key=len, reverse=True):
            text = text.replace(v, "***")
        for rx, repl in _PATTERNS:
            text = rx.sub(repl, text)
        return text


REDACT = Redactor()


def say(msg: str, stream=None) -> None:
    """Print one line, scrubbed. All engine output goes through here."""
    print(REDACT(str(msg)), file=stream or sys.stderr, flush=True)
