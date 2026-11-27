"""Map log patterns back to source lines by searching for their literal fragments."""
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .suggest import LAMBDA_PLATFORM

EXCLUDE_DIRS = ("node_modules", ".git", "dist", "build", ".venv", "venv", "vendor", "coverage",
                "__pycache__", ".next", "target", ".terraform", "cdk.out", ".serverless")
EXCLUDE_GLOBS = ("*.min.js", "*.map", "*.lock", "package-lock.json", "*.log", "*.svg", "*.snap")
MIN_FRAGMENT = 8
MAX_FRAGMENTS = 4
MAX_CANDIDATES = 10
MAX_HITS_PER_FRAGMENT = 200

TOKEN = re.compile(r"<[^<>\s]{1,60}>")
# Placeholders the core redactor leaves behind.
REDACTED = re.compile(r"\?:query|:userinfo@|Bearer :token|:(email|uuid|id|jwt|phone|number|enc)\b")
JSON_PAIR = re.compile(r'"([A-Za-z_@][\w.@-]{0,40})"\s*:\s*"((?:[^"\\]|\\.)*)"')
MESSAGE_KEYS = {"msg", "message", "err", "error", "event", "description", "reason", "text", "detail"}
LEVEL_PREFIX = re.compile(
    r"^\W*(?:\d{4}-\d\d-\d\d[T ][\d:.]+Z?\s*)?\[?(?:TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\]?\s*[:-]?\s*",
    re.I)
BORING = {"requestid", "version", "duration", "billed duration", "memory size", "max memory used",
          "init duration", "timestamp", "level", "info", "debug", "error", "warn"}


@dataclass
class Candidate:
    file: str
    line: int
    text: str
    score: int
    fragments: list


def _clean(piece: str) -> str:
    piece = LEVEL_PREFIX.sub("", piece.strip())
    piece = piece.strip(" \t[](){}<>:,;=|\"'`")
    return re.sub(r"\s{2,}", " ", piece)


def fragments(pattern: str) -> list[str]:
    """Longest literal pieces of a pattern, without tokens or redaction placeholders.
    Lambda platform lines (START/END/REPORT) come from AWS, not from the code: none."""
    if LAMBDA_PLATFORM.search(pattern):
        return []
    text = TOKEN.sub("\x00", pattern)
    text = REDACTED.sub("\x00", text)
    pieces = []
    if text.lstrip().startswith("{"):
        pairs = JSON_PAIR.findall(text)
        msg = [v for k, v in pairs if k.lower() in MESSAGE_KEYS]
        pieces = msg or [v for _, v in pairs]
        pieces = [p.replace('\\"', '"') for p in pieces]
        pieces = [x for p in pieces for x in p.split("\x00")]
    else:
        pieces = text.split("\x00")
    out = []
    for p in pieces:
        p = _clean(p)
        letters = sum(c.isalpha() for c in p)
        if len(p) < MIN_FRAGMENT or letters < 5 or p.lower() in BORING:
            continue
        if p not in out:
            out.append(p)
    out.sort(key=len, reverse=True)
    return out[:MAX_FRAGMENTS]


def _search(repo: Path, fragment: str) -> list[tuple[str, int, str]]:
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "--fixed-strings", "--line-number", "--no-heading", "--color", "never",
               "--max-count", "20", "--max-columns", "300"]
        for d in EXCLUDE_DIRS:
            cmd += ["--glob", f"!{d}/"]
        for g in EXCLUDE_GLOBS:
            cmd += ["--glob", f"!{g}"]
        cmd += ["-e", fragment, "--", str(repo)]
    else:
        cmd = ["grep", "-rnIF"]
        cmd += [f"--exclude-dir={d}" for d in EXCLUDE_DIRS]
        cmd += [f"--exclude={g}" for g in EXCLUDE_GLOBS]
        cmd += ["-e", fragment, "--", str(repo)]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=120)
    hits = []
    for line in res.stdout.splitlines()[:MAX_HITS_PER_FRAGMENT]:
        parts = line.split(":", 2)
        if len(parts) < 3 or not parts[1].isdigit():
            continue
        hits.append((parts[0], int(parts[1]), parts[2].strip()[:200]))
    return hits


def locate_pattern(repo: Path, pattern: str) -> list[Candidate]:
    repo = repo.resolve()
    by_line: dict[tuple, Candidate] = {}
    for frag in fragments(pattern):
        for path, line, text in _search(repo, frag):
            rel = str(Path(path).resolve().relative_to(repo)) if Path(path).is_absolute() else path
            c = by_line.setdefault((rel, line), Candidate(rel, line, text, 0, []))
            c.score += len(frag)
            c.fragments.append(frag)
    return sorted(by_line.values(), key=lambda c: (-c.score, c.file, c.line))[:MAX_CANDIDATES]


def patterns_from_report(report: dict, top: int) -> list[dict]:
    pats = []
    for g in report.get("groups", []):
        for p in g.get("patterns", []):
            pats.append({"id": p["id"], "text": p["text"], "monthly_usd": p.get("monthly_usd", 0.0),
                         "group": g["name"], "region": g["region"], "flags": p.get("flags", [])})
    pats.sort(key=lambda p: p["monthly_usd"], reverse=True)
    return pats[:top]


def locate(repo: str | Path, report_path: str | Path, top: int = 10) -> list[dict]:
    report = json.loads(Path(report_path).read_text())
    out = []
    for p in patterns_from_report(report, top):
        cands = locate_pattern(Path(repo), p["text"])
        out.append({**p, "fragments": fragments(p["text"]), "candidates": [asdict(c) for c in cands]})
    return out
