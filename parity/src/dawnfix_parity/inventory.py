"""Per secret/parameter: age, last read, rotation, who references it; flags."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .cloudtrail import Reads
from .config import Config
from .model import Item, Snapshot
from .resolve import Resolver

INVENTORY_FLAGS = ("unread", "never_rotated", "rotation_overdue", "orphaned")


@dataclass
class Row:
    item: Item
    referenced_by: list[str] = field(default_factory=list)
    readers: dict[str, int] = field(default_factory=dict)
    last_read: datetime | None = None
    last_read_source: str | None = None      # secretsmanager | cloudtrail
    rotation_age_days: int | None = None
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        m = self.item.meta
        return {
            "env": self.item.env, "kind": self.item.kind, "name": self.item.name, "type": self.item.type,
            "arn": self.item.arn,
            "last_changed": _iso(m.get("last_changed")),
            "last_read": _iso(self.last_read), "last_read_source": self.last_read_source,
            "rotation_enabled": m.get("rotation_enabled"), "last_rotated": _iso(m.get("last_rotated")),
            "rotation_age_days": self.rotation_age_days,
            "referenced_by": self.referenced_by, "readers": self.readers,
            "flags": self.flags, "notes": self.notes,
        }


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _aware(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


def _days(now, v) -> int | None:
    v = _aware(v)
    return (now - v).days if isinstance(v, datetime) else None


def build(cfg: Config, snap: Snapshot, resolver: Resolver, now: datetime,
          reads: Reads | None = None) -> list[Row]:
    rows = {id(i): Row(i) for i in snap.by_kind("ssm", "secret")}
    # references from every snapshot count: a dev Lambda reading a prod secret still reads it
    for s in resolver.snaps.values():
        for ref in s.references:
            res = resolver.resolve(ref, lookup=False)
            if res.owner_env != snap.env:
                continue
            for it in res.items:
                r = rows.get(id(it))
                if r is not None:
                    label = f"{ref.source_kind}:{ref.source} {ref.var}" + (" (prefix)" if ref.prefix else "")
                    if s.env != snap.env:
                        label += f" [from {s.env}]"
                    if label not in r.referenced_by:
                        r.referenced_by.append(label)

    for r in rows.values():
        it, m = r.item, r.item.meta
        if it.kind == "secret":
            r.last_read, r.last_read_source = _aware(m.get("last_accessed")), "secretsmanager"
        if reads is not None:
            r.readers = reads.readers_of(it.name, it.arn)
            ct_last = _aware(reads.last_read(it.name, it.arn))
            if ct_last and (r.last_read is None or ct_last > r.last_read):
                r.last_read, r.last_read_source = ct_last, "cloudtrail"

        # unread
        if it.kind == "secret":
            age = _days(now, r.last_read)
            if age is None or age >= cfg.unread_days:
                r.flags.append("unread")
                if age is None:
                    r.notes.append("never accessed")
        elif reads is not None and reads.days >= cfg.unread_days and not r.readers:
            r.flags.append("unread")
            r.notes.append(f"no reads in {reads.days} days of CloudTrail")

        # rotation
        if it.kind == "secret":
            rotated = _aware(m.get("last_rotated"))
            r.rotation_age_days = _days(now, rotated or m.get("created"))
            if not m.get("rotation_enabled") and rotated is None:
                r.flags.append("never_rotated")
            elif r.rotation_age_days is not None and r.rotation_age_days > cfg.rotation_max_age_days:
                r.flags.append("rotation_overdue")
                if m.get("rotation_enabled"):
                    r.notes.append("rotation is enabled but has not run: check the rotation Lambda")
        elif it.type == "SecureString":
            r.rotation_age_days = _days(now, m.get("last_changed"))
            if m.get("version") == 1:
                r.flags.append("never_rotated")
            elif r.rotation_age_days is not None and r.rotation_age_days > cfg.rotation_max_age_days:
                r.flags.append("rotation_overdue")

        if not r.referenced_by and not r.readers:
            r.flags.append("orphaned")
    return sorted(rows.values(), key=lambda r: (r.item.kind, r.item.name))
