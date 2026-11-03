"""Requirement to Output composition adapter for exact fixed versions."""
from __future__ import annotations
import uuid
from plm_assistant.modules.output.application.resolve_context import FixedSourceVersion
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService

class RequirementOutputSourceAdapter:
    def __init__(self, reader: RequirementVersionReadService) -> None:
        if reader is None:
            raise ValueError("Requirement source reader is required")
        self._reader = reader

    def read_authorized_fixed_version(self, transaction: object, *, actor_id: uuid.UUID,
                                      project_id: uuid.UUID,
                                      source_version_ref: uuid.UUID) -> FixedSourceVersion | None:
        projection = self._reader.read_output_source(
            transaction, actor_id=actor_id, project_id=project_id,
            requirement_version_id=source_version_ref,
        )
        return FixedSourceVersion(
            project_id=projection.project_id,
            source_version_ref=projection.requirement_version_id,
            source_kind="REQUIREMENT_VERSION",
            review_state=projection.version_state,
            authorized=True,
            fields=projection.fields,
        )
