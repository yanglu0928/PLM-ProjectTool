"""Versioned streaming membership digest; no authority or database snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Iterable
from uuid import UUID

MEMBERSHIP_VERSION = "CAPTURE-MEMBERSHIP-V1"
_DOMAIN = b"PLM-AUDIT-CAPTURE-MEMBERSHIP-V1\x00"


@dataclass(frozen=True, slots=True)
class CaptureMember:
    event_id: UUID
    occurred_at: datetime

    def __post_init__(self) -> None:
        if (type(self.event_id) is not UUID or self.event_id.int == 0
                or type(self.occurred_at) is not datetime
                or self.occurred_at.tzinfo is None
                or self.occurred_at.utcoffset() is None):
            raise ValueError("invalid Audit capture member")

    def canonical_line(self) -> bytes:
        self.__post_init__()
        stamp = self.occurred_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds").replace("+00:00", "Z")
        return f"{self.event_id}|{stamp}\n".encode("ascii")


@dataclass(frozen=True, slots=True)
class MembershipDigest:
    count: int
    sha256: str
    version: str = MEMBERSHIP_VERSION


def digest_members(members: Iterable[CaptureMember]) -> MembershipDigest:
    """Hash ordered coordinates, not events, auth, file bytes or capture time.

    The actual repository must establish genuine immutable event membership.
    Strict descending (time,UUID) makes duplicate identical coordinates invalid.
    A repeated UUID at a different time must also be rejected. UUID uniqueness
    requires O(n) identifier memory here; SQL uniqueness remains mandatory.
    Event bodies are never loaded or copied by this function.
    """
    digest = hashlib.sha256(_DOMAIN)
    previous = None
    seen: set[UUID] = set()
    count = 0
    for member in members:
        if type(member) is not CaptureMember:
            raise ValueError("invalid Audit capture member")
        line = member.canonical_line()
        position = (member.occurred_at.astimezone(timezone.utc), member.event_id.int)
        if member.event_id in seen or previous is not None and position >= previous:
            raise ValueError("invalid Audit capture membership order")
        digest.update(line)
        seen.add(member.event_id)
        previous = position
        count += 1
    return MembershipDigest(count, digest.hexdigest())
