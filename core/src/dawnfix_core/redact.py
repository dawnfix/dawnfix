"""Redacts PII/PHI and secrets from text before it leaves the process.

Log text is written by outside users and may carry emails, phone numbers,
ids, tokens or injected instructions. Only printable ASCII leaves, with
sensitive values folded. Instruction-like text is not removed: it stays
inert data and the consumer must treat it as such.

Also usable as a stdin -> stdout filter: python -m dawnfix_core.redact
"""
import re
import sys
from urllib.parse import unquote

RULES = [
    (re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I), "Bearer :token"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), ":jwt"),
    (re.compile(r"//[^/\s:@]+:[^/\s@]+@"), "//:userinfo@"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), ":email"),
    (re.compile(r"\?[^\s\"']*"), "?:query"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), ":uuid"),
    (re.compile(r"\b[0-9a-fA-F]{24,}\b"), ":id"),
    (re.compile(r"\b(?=[A-Za-z0-9_]*\d)(?=[A-Za-z0-9_]*[A-Za-z])[A-Za-z0-9_]{20,}\b"), ":id"),
    (re.compile(r"(?<![\w-])\+?(?:1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?![\w-])"), ":phone"),
    (re.compile(r"\b\d{7,}\b"), ":number"),
]

PRINTABLE = re.compile(r"[^ -~]")


def redact(line: str) -> str:
    # Decode %xx until stable (capped) so %40 / %2540 can't hide an email.
    for _ in range(10):
        decoded = unquote(line)
        if decoded == line:
            break
        line = decoded
    line = re.sub(r"%[0-9A-Fa-f]{2}", ":enc", line)  # still encoded after the cap
    # Printable ASCII only, before and after the rules: a decoded newline,
    # tab or control character can't start a fake output line.
    line = PRINTABLE.sub(" ", line)
    for rx, repl in RULES:
        line = rx.sub(repl, line)
    return PRINTABLE.sub(" ", line)


def safe_redact(line: str) -> str:
    try:
        return redact(line)
    except Exception:  # one bad line must not stop the tick
        return ":unparseable-line"


def main() -> None:
    sys.stdin.reconfigure(errors="replace")
    for raw in sys.stdin:
        sys.stdout.write(safe_redact(raw.rstrip("\r\n")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
