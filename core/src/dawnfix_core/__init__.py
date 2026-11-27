"""dawnfix-core: deterministic, read-only tick over prod logs (no LLM)."""

__version__ = "0.3.0"

# The read-only AWS guard is public API (other Dawnfix tools build their clients with it).
from .awsguard import ReadOnlyViolation, make_client  # noqa: E402,F401

__all__ = ["ReadOnlyViolation", "__version__", "make_client"]
