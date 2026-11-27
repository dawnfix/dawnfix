"""Known fingerprints between ticks, in a JSON file (kept by the workflow, e.g. actions/cache)."""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

VERSION = 1


class StateError(Exception):
    pass


def empty() -> dict:
    return {"version": VERSION, "windows": {}, "fingerprints": {}}


def load(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return empty()
    try:
        data = json.loads(p.read_text() or "{}")
    except ValueError:
        raise StateError(f"{p}: not valid JSON; delete it to start fresh") from None
    if not data:
        return empty()
    if data.get("version") != VERSION or not isinstance(data.get("fingerprints"), dict):
        raise StateError(f"{p}: unknown state format; delete it to start fresh")
    data.setdefault("windows", {})
    return data


def save(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".state-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def baseline(entry: dict) -> float:
    """Mean count per tick in which the fingerprint was seen."""
    return entry["total"] / max(entry["ticks"], 1)


def classify(state: dict, fp: str, count: int, factor: float, min_count: int) -> tuple[str, float | None]:
    """'new' if never seen, 'spike' if count >= factor x baseline (and >= min_count), else 'known'."""
    entry = state["fingerprints"].get(fp)
    if entry is None:
        return "new", None
    base = baseline(entry)
    if count >= min_count and count >= factor * base:
        return "spike", round(base, 2)
    return "known", round(base, 2)


def record(state: dict, fp: str, count: int, now: datetime, first_seen: datetime | None = None) -> dict:
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = state["fingerprints"].get(fp)
    if entry is None:
        first = (first_seen or now).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = state["fingerprints"][fp] = {"first_seen": first, "last_seen": ts, "total": 0, "ticks": 0}
    entry["last_seen"] = ts
    entry["total"] += count
    entry["ticks"] += 1
    return entry
