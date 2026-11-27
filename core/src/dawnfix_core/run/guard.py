"""No secret in any text sent to the repo host: issue bodies, comments, draft PR or MR titles
and descriptions, commit subjects, and the files a PR changes.

Each stage that holds secrets writes the SHA-256 (and length) of every secret value in its
environment to secret-hashes.json in its artifact: the read stage's cloud credentials and OIDC
tokens, the agent stage's AI key and CI tokens. Never the values. The publish stage loads those
lists, adds its own secret values (the host token), and before any host call that carries text
redacts (1) every exact value it knows, (2) every substring whose hash is on the lists, and (3)
anything shaped like a credential, then says so in the text. So publish never needs the AI key.
"""
import hashlib
import json
import re
from pathlib import Path

from .hosts.base import LABELS, Change, HostAdapter
from .scrub import CREDENTIAL_SHAPES, say
from .stages import SECRET_NAMES

HASHES_FILE = "secret-hashes.json"
SECRETISH = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL", re.I)
MIN_LEN = 8
SHAPES = re.compile("|".join(CREDENTIAL_SHAPES))
MARK = "[redacted by Dawnfix: looked like a credential]"
# Delimiters a secret's tokens are split on (each token of MIN_LEN or more is recorded too).
DELIMS = re.compile(r"[\s\"'`<>()\[\]{},;:=&?/\\|@#%+*!]+")
# What JSON escaping or line wrapping puts inside a secret: dropped from a second view of the
# text, so a secret split across lines or escaped in JSON is still found.
NOISE = re.compile(r"[\s\\]")
MOD = (1 << 61) - 1
BASE = 1_000_003


def rk(s: str) -> int:
    """Polynomial rolling hash, the prefilter for the sliding window (sha256 confirms)."""
    h = 0
    for c in s:
        h = (h * BASE + ord(c)) % MOD
    return h


def _windows(text: str, n: int, rks: set[int]):
    """Start offsets of every length-n window of text whose rolling hash is in rks."""
    if n > len(text) or n <= 0:
        return
    top = pow(BASE, n - 1, MOD)
    h = rk(text[:n])
    for i in range(len(text) - n + 1):
        if h in rks:
            yield i
        if i + n < len(text):
            h = ((h - ord(text[i]) * top) * BASE + ord(text[i + n])) % MOD


def secret_values(env) -> list[str]:
    names = set(SECRET_NAMES) | {k for k in env if SECRETISH.search(k)}
    return sorted({env[n] for n in names if isinstance(env.get(n), str) and len(env[n]) >= MIN_LEN})


def _entry(v: str) -> dict:
    return {"len": len(v), "sha256": hashlib.sha256(v.encode()).hexdigest(), "rk": rk(v)}


def hashes_of(values) -> list[dict]:
    """Each secret, and each of its delimiter-split tokens of MIN_LEN or more characters."""
    out = []
    for v in values:
        out.append(_entry(v))
        out += [_entry(t) for t in DELIMS.split(v) if len(t) >= MIN_LEN and t != v]
    return out


def write_hashes(path: Path, env, also=()) -> None:
    """This stage's secret hashes, plus those of the stages before it (`also`: their files)."""
    entries = hashes_of(secret_values(env))
    for f in also:
        entries += load_hashes(f)
    uniq = {(e["len"], e["sha256"]): e for e in entries}  # rk follows from the value
    path.write_text(json.dumps({"schema": "dawnfix.secret-hashes/1", "hashes": list(uniq.values())}, indent=2) + "\n")


def load_hashes(path: Path) -> list[dict]:
    try:
        if not path.is_file() or path.is_symlink():
            return []
        doc = json.loads(path.read_text())
        return [{"len": int(e["len"]), "sha256": str(e["sha256"]), "rk": int(e["rk"]) if "rk" in e else None} for e in doc.get("hashes", [])
                if int(e["len"]) >= MIN_LEN and re.match(r"^[0-9a-f]{64}$", str(e["sha256"]))]
    except (OSError, ValueError, KeyError, TypeError):
        return []


class TextGuard:
    def __init__(self, values=(), hashes=()):
        vals = {v for v in values if v and len(v) >= MIN_LEN}
        # Values known here are matched like hashed ones too (tokens, split lines, escapes).
        entries = list(hashes) + hashes_of(vals)
        self.values = sorted(vals, key=len, reverse=True)
        self.by_len: dict[int, tuple[set, set[str]]] = {}
        for e in entries:
            rks, shas = self.by_len.setdefault(e["len"], (set(), set()))
            rks.add(e.get("rk"))  # None: an entry without a rolling hash, every window is hashed
            shas.add(e["sha256"])

    def _spans_in(self, view: str) -> list[tuple[int, int]]:
        spans = []
        for n, (rks, shas) in self.by_len.items():
            starts = range(len(view) - n + 1) if None in rks else _windows(view, n, rks)
            for i in starts:
                if hashlib.sha256(view[i:i + n].encode()).hexdigest() in shas:
                    spans.append((i, i + n))
        return spans

    def spans(self, text: str) -> list[tuple[int, int]]:
        """Spans of text holding a known secret or one of its tokens: on the text itself, and on
        the text without whitespace and backslashes (mapped back), for split or escaped ones."""
        found = self._spans_in(text)
        keep = [i for i, c in enumerate(text) if not NOISE.match(c)]
        view = "".join(text[i] for i in keep)
        if len(view) != len(text):
            found += [(keep[a], keep[b - 1] + 1) for a, b in self._spans_in(view)]
        for v in self.values:
            start = 0
            while (i := text.find(v, start)) >= 0:
                found.append((i, i + len(v)))
                start = i + 1
        return found

    def clean(self, text: str) -> tuple[str, int]:
        """The text with every known secret and credential shape replaced, and how many."""
        spans = sorted(self.spans(text))
        merged: list[list[int]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in reversed(merged):
            text = text[:a] + MARK + text[b:]
        text, k = SHAPES.subn(MARK, text)
        return text, len(merged) + k

    def found(self, data: bytes) -> bool:
        text = data.decode("utf-8", "replace")
        return self.clean(text)[1] > 0

    def body(self, text: str, where: str) -> str:
        cleaned, n = self.clean(text)
        if n:
            say(f"warning: redacted {n} value(s) that looked like credentials from the {where}")
            cleaned += f"\n\n> Dawnfix removed {n} value(s) that looked like credentials from this text.\n"
        return cleaned

    def title(self, text: str) -> str:
        cleaned, n = self.clean(text)
        return cleaned if not n else "dawnfix finding (title redacted)"


class GuardedHost(HostAdapter):
    """Every host call that carries text goes through the guard first."""

    def __init__(self, inner: HostAdapter, guard: TextGuard):
        self.inner, self.guard = inner, guard
        self.ctx, self.token, self.http, self.name = inner.ctx, inner.token, inner.http, inner.name

    def default_branch(self):
        return self.inner.default_branch()

    def find_existing(self, fingerprint):
        return self.inner.find_existing(fingerprint)

    def open_draft_change(self, branch, title, body):
        return self.inner.open_draft_change(branch, self.guard.title(title), self.guard.body(body, "draft PR description"))

    def open_issue(self, title, body, labels=LABELS):
        return self.inner.open_issue(self.guard.title(title), self.guard.body(body, "issue body"), labels)

    def comment(self, change: Change, body):
        return self.inner.comment(change, self.guard.body(body, "comment"))

    def changes_opened_today(self):
        return self.inner.changes_opened_today()

    def push_url(self, token):
        return self.inner.push_url(token)

    def ci_config_path(self):
        return self.inner.ci_config_path()

    @property
    def push_options(self):
        return self.inner.push_options

    @property
    def commit_note(self):
        return self.inner.commit_note

    @property
    def auth_values(self):
        return self.inner.auth_values

    def issues_enabled(self):
        return self.inner.issues_enabled()

    def ci_context(self):
        return self.inner.ci_context()
