"""Stable fixed-version input for a SOL-06 validation observation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .structured_spec_input import ValidatedStructuredSpecDraft
from .structured_spec_validation_contract import StructuredSpecValidationSnapshot


class StructuredSpecValidationSourceError(ValueError):
    """The locked fixed snapshot and its reconstructed input disagree."""


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


@dataclass(frozen=True, slots=True)
class StructuredSpecValidationSource:
    snapshot: StructuredSpecValidationSnapshot
    draft: ValidatedStructuredSpecDraft = field(repr=False)
    latest_version_ref: uuid.UUID
    latest_version_no: int

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not StructuredSpecValidationSnapshot
                or type(self.draft) is not ValidatedStructuredSpecDraft
                or not _id(self.latest_version_ref)
                or type(self.latest_version_no) is not int
                or self.latest_version_no < self.snapshot.version_no
                or (self.latest_version_ref
                    == self.snapshot.structured_solution_spec_id)
                != (self.latest_version_no == self.snapshot.version_no)
                or self.draft.project_id != self.snapshot.project_id
                or self.draft.spec_type != self.snapshot.spec_type
                or self.draft.payload_fingerprint
                != self.snapshot.payload_fingerprint
                or type(self.draft.request_fingerprint) is not bytes
                or len(self.draft.request_fingerprint) != 32
                or len(self.draft.requirement_refs)
                != self.snapshot.requirement_count
                or len(self.draft.section_refs) != self.snapshot.section_count
                or len(self.draft.evidence_ids) != self.snapshot.evidence_count
                or len(self.draft.artifact_ids) != self.snapshot.artifact_count):
            raise StructuredSpecValidationSourceError(
                "invalid structured spec validation source")
        if self.snapshot.version_no == 1:
            if (self.draft.spec_series_id is not None
                    or self.draft.supersedes_version_ref is not None):
                raise StructuredSpecValidationSourceError(
                    "invalid initial structured spec source")
        elif (self.draft.spec_series_id != self.snapshot.spec_series_id
              or not _id(self.draft.supersedes_version_ref)):
            raise StructuredSpecValidationSourceError(
                "invalid revision structured spec source")

    @property
    def is_current_version(self) -> bool:
        return (self.latest_version_ref
                == self.snapshot.structured_solution_spec_id
                and self.latest_version_no == self.snapshot.version_no)
