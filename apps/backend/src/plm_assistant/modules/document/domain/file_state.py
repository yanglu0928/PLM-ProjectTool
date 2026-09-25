"""Frozen DM-03 FileObject transition graph, without persistence or I/O.

This policy is necessary but not sufficient for a state command: callers must
enforce authorization, expected version, content/reference proofs and audit in
one database transaction before exposing any resulting DocumentVersion.
"""

from __future__ import annotations

from dataclasses import dataclass


FILE_STATES = frozenset({
    "STAGED", "AVAILABLE", "FAILED", "CLEANUP_PENDING", "REMOVED", "RESTRICTED",
})
STORAGE_CLASSES = frozenset({"TEMPORARY", "PERSISTENT"})

_TRANSITIONS = frozenset({
    ("STAGED", "AVAILABLE"),
    ("STAGED", "FAILED"),
    ("FAILED", "CLEANUP_PENDING"),
    ("CLEANUP_PENDING", "REMOVED"),
    ("AVAILABLE", "RESTRICTED"),
    ("AVAILABLE", "CLEANUP_PENDING"),
})


class FileStateTransitionError(ValueError):
    """An unregistered or forbidden FileObject transition was requested."""


@dataclass(frozen=True, slots=True)
class FileTransitionRequirements:
    verify_final_content: bool
    verify_cleanup_eligibility: bool
    record_reason: bool


def transition_requirements(*, from_state: str, to_state: str,
                            storage_class: str) -> FileTransitionRequirements:
    """Describe mandatory external checks, never grant permission to transition."""
    if (type(from_state) is not str or type(to_state) is not str
            or type(storage_class) is not str
            or from_state not in FILE_STATES or to_state not in FILE_STATES
            or storage_class not in STORAGE_CLASSES
            or (from_state, to_state) not in _TRANSITIONS
            or ((from_state, to_state) == ("AVAILABLE", "CLEANUP_PENDING")
                and storage_class != "TEMPORARY")):
        raise FileStateTransitionError("file state transition unavailable")
    return FileTransitionRequirements(
        verify_final_content=to_state == "AVAILABLE",
        verify_cleanup_eligibility=to_state in ("CLEANUP_PENDING", "REMOVED"),
        record_reason=to_state in ("FAILED", "CLEANUP_PENDING", "REMOVED", "RESTRICTED"),
    )
