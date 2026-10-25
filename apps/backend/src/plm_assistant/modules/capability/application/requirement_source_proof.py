"""Minimal Capability-owned current approved item proof for Requirement."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CapabilityRequirementSourceProof:
    baseline_version_id: uuid.UUID
    baseline_id: uuid.UUID
    capability_item_id: uuid.UUID
    capability_item_row_id: uuid.UUID
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    version_no: int
    content_fingerprint: bytes = field(repr=False)


class CapabilityRequirementSourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, baseline_version_id: uuid.UUID,
        capability_item_id: uuid.UUID,
    ) -> CapabilityRequirementSourceProof | None: ...
