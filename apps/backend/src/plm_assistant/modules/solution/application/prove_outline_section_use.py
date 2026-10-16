"""Current stable Section identity proof for an OutlineVersion input."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from .read_section import SectionCurrentView


class OutlineSectionUseError(RuntimeError):
    def __init__(self, code: str = "SECTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineSectionUseProof:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_section_id: uuid.UUID


class SectionCurrentPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID) -> SectionCurrentView | None: ...


class OutlineSectionUseProofService:
    def __init__(self, *, sections: SectionCurrentPort) -> None:
        if sections is None:
            raise ValueError("current Section identity port required")
        self._sections = sections

    def prove(self, transaction: object, *, project_id: uuid.UUID,
              outline_id: uuid.UUID,
              section_id: uuid.UUID) -> OutlineSectionUseProof:
        if (transaction is None or any(
                type(value) is not uuid.UUID or value.int == 0
                for value in (project_id, outline_id, section_id))):
            raise OutlineSectionUseError("VALIDATION_FAILED")
        try:
            current = self._sections.get_current(
                transaction, project_id=project_id, section_id=section_id)
            if (type(current) is not SectionCurrentView
                    or current.project_id != project_id
                    or current.solution_outline_id != outline_id
                    or current.solution_section_id != section_id
                    or current.section_state != "ACTIVE"):
                raise OutlineSectionUseError()
            return OutlineSectionUseProof(project_id, outline_id, section_id)
        except OutlineSectionUseError:
            raise
        except Exception:
            raise OutlineSectionUseError() from None
