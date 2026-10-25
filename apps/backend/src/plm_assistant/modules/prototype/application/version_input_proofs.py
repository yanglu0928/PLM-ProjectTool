"""Prototype-owned fixed TemplateVersion proof for PrototypeVersion inputs."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PrototypeVersionTemplateProof:
    prototype_template_id: uuid.UUID
    prototype_template_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    version_no: int
    content_fingerprint: str

    def __post_init__(self) -> None:
        project_shape = (
            self.scope == "GLOBAL" and self.project_id is None
            or self.scope == "PROJECT" and type(self.project_id) is uuid.UUID
            and self.project_id.int != 0
        )
        if (
            any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.prototype_template_id, self.prototype_template_version_id,
            ))
            or not project_shape
            or type(self.version_no) is not int or self.version_no < 1
            or re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint) is None
        ):
            raise ValueError("invalid PrototypeTemplateVersion proof")


class PrototypeVersionTemplateProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_template_id: uuid.UUID,
        prototype_template_version_id: uuid.UUID,
    ) -> PrototypeVersionTemplateProof | None: ...
