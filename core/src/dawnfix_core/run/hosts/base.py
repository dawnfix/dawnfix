"""The repo host behind one interface: what the publish stage needs from GitHub, GitLab or
Bitbucket. Tokens come from the environment, are used only in request headers or the push
URL, and never reach a log line (scrub.REDACT holds every secret value)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..context import CiContext
from ..web import Http

LABELS = ("dawnfix", "AI-generated")


class HostError(Exception):
    """A call to the repo host failed; the message never holds a token."""


@dataclass(frozen=True)
class Change:
    kind: str     # "change" (a pull or merge request) | "issue"
    number: int
    state: str    # open | closed | merged
    url: str


@dataclass(frozen=True)
class Existing:
    """What the host already has for a fingerprint: its dawnfix/<fp> pull or merge request (any
    state) and its open dawnfix issue. Either may be None."""
    change: Change | None = None
    issue: Change | None = None


class HostAdapter(ABC):
    name = "host"
    # git push options for the dawnfix branch (GitLab: ci.skip, so no pipeline runs on it).
    push_options: tuple[str, ...] = ()
    # A line added to each commit message (Bitbucket: "[skip ci]", so the push runs no pipeline).
    commit_note: str = ""

    def __init__(self, ctx: CiContext, token: str = "", http: Http | None = None):
        self.ctx = ctx
        self.token = token
        self.http = http or Http()

    def ci_context(self) -> CiContext:
        """The repo, commit and run URL this run is about, from the CI's environment."""
        return self.ctx

    @abstractmethod
    def default_branch(self) -> str: ...

    @abstractmethod
    def find_existing(self, fingerprint: str) -> Existing:
        """Dedupe: the dawnfix/<fingerprint> change in any state, and the open issue whose title
        holds the fingerprint."""

    @abstractmethod
    def open_draft_change(self, branch: str, title: str, body: str) -> Change:
        """A DRAFT pull or merge request from `branch` into the default branch, labelled dawnfix
        and AI-generated. Never merged, never marked ready."""

    @abstractmethod
    def open_issue(self, title: str, body: str, labels: tuple[str, ...] = LABELS) -> Change: ...

    @abstractmethod
    def comment(self, change: Change, body: str) -> None:
        """A comment on an open change or issue (a new analysis of a known fingerprint)."""

    @abstractmethod
    def changes_opened_today(self) -> int:
        """dawnfix/<fingerprint> changes created today (UTC): limits.fix_prs_per_day."""

    def issues_enabled(self) -> bool:
        """False when the repo has no issue tracker: open_issue then writes the text to the log."""
        return True

    @property
    def auth_values(self) -> tuple[str, ...]:
        """Every form of the credential that could end up in text (the publish guard's values)."""
        return (self.token,) if self.token else ()

    def ci_config_path(self) -> str:
        """The repo's CI config path when the host lets a project set its own ("": the default)."""
        return ""

    @abstractmethod
    def push_url(self, token: str) -> str:
        """The explicit HTTPS URL the publish stage pushes to, with the token in it."""


class NotImplementedAdapter(HostAdapter):
    """A repo host this version cannot publish to yet. Every call says so plainly."""

    name = "unknown"
    phase = "phase 2"

    def _no(self, *_a, **_k):
        raise HostError(
            f"publishing to {self.name} repos is not in this version of dawnfix ({self.phase}). "
            "GitHub, GitLab and Bitbucket Cloud repos work today")

    default_branch = find_existing = open_draft_change = open_issue = comment = _no
    changes_opened_today = push_url = _no
