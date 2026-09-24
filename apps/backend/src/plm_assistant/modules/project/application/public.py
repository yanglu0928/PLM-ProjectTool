"""Project-owned authorization summary safe for cross-module reads."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectAccessSummary:
    project_id: uuid.UUID
    name: str
    role: str
