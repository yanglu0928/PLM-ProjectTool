"""Owner-private DocumentVersion identity lookup, not an authorization proof."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ReferenceVersionIdentity:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None


class ReferenceVersionIdentityPort(Protocol):
    def get(self, transaction: object, *, scope: str,
            project_id: uuid.UUID | None,
            document_version_id: uuid.UUID) -> ReferenceVersionIdentity | None: ...
