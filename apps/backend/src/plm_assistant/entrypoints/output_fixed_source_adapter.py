"""Dispatch exact fixed-version sources to their owning modules."""
from __future__ import annotations

import uuid

from plm_assistant.modules.output.application.resolve_context import FixedSourceVersion
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanOutputSourceProjection, PlanVersionReadError, PlanVersionReadService,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementOutputSourceProjection, RequirementVersionReadError,
    RequirementVersionReadService,
)


class FixedOutputSourceAdapter:
    """Use owner-authorized projections and reject missing or ambiguous refs."""

    def __init__(self, *, requirements: RequirementVersionReadService,
                 plans: PlanVersionReadService) -> None:
        if requirements is None or plans is None:
            raise ValueError("Output source readers are required")
        self._requirements = requirements
        self._plans = plans

    def read_authorized_fixed_version(
        self, transaction: object, *, actor_id: uuid.UUID,
        project_id: uuid.UUID, source_version_ref: uuid.UUID,
    ) -> FixedSourceVersion | None:
        found: list[FixedSourceVersion] = []
        denied = []
        try:
            projection = self._requirements.read_output_source(
                transaction, actor_id=actor_id, project_id=project_id,
                requirement_version_id=source_version_ref,
            )
            if type(projection) is RequirementOutputSourceProjection:
                found.append(FixedSourceVersion(
                    project_id=projection.project_id,
                    source_version_ref=projection.requirement_version_id,
                    source_kind="REQUIREMENT_VERSION",
                    review_state=projection.version_state,
                    authorized=True,
                    fields=projection.fields,
                ))
        except RequirementVersionReadError as error:
            if error.code != "RESOURCE_NOT_FOUND":
                denied.append(error)

        try:
            projection = self._plans.read_output_source(
                transaction, actor_id=actor_id, project_id=project_id,
                plan_version_id=source_version_ref,
            )
            if type(projection) is PlanOutputSourceProjection:
                found.append(FixedSourceVersion(
                    project_id=projection.project_id,
                    source_version_ref=projection.plan_version_id,
                    source_kind="PLAN_VERSION",
                    review_state=projection.version_state,
                    authorized=True,
                    fields=projection.fields,
                ))
        except PlanVersionReadError as error:
            if error.code != "RESOURCE_NOT_FOUND":
                denied.append(error)

        if len(found) == 1:
            return found[0]
        if found:
            return None
        if denied:
            raise denied[0]
        return None
