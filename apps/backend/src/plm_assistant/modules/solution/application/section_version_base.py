"""Same-transaction identity and version-sequence base for a SectionVersion draft."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CurrentSectionVersionBase:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_section_id: uuid.UUID
    next_version_no: int
    supersedes_version_id: uuid.UUID | None
    outline_lock_version: int
    section_lock_version: int


class CurrentSectionVersionBasePort(Protocol):
    def current(self, transaction: object, *, project_id: uuid.UUID,
                section_id: uuid.UUID) -> CurrentSectionVersionBase | None: ...
