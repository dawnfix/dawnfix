"""Read-only sources. Each yields normalized Events for a time window."""
import re
from dataclasses import dataclass
from datetime import datetime


class SourceError(Exception):
    """A source failed. `code` is a short identifier, never log or message text."""

    def __init__(self, code: str, hint: str = ""):
        super().__init__(f"{code}{': ' + hint if hint else ''}")
        self.code = re.sub(r"[^A-Za-z0-9_.-]", "", code)[:64] or "error"
        self.hint = hint


@dataclass
class Window:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)
