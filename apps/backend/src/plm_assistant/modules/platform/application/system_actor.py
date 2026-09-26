"""Controlled runtime identity is provenance, never business authorization."""

from typing import Protocol
from uuid import UUID


class SystemActorUnavailable(RuntimeError):
    code = "SYSTEM_ACTOR_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("system actor unavailable")


class SystemActorPort(Protocol):
    def assert_current(self) -> UUID:
        """Return the pinned identity only while its controlled source is unchanged."""
        ...
