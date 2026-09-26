"""Immutable configuration, not an executable Gate or business approval."""

from .definition import (
    ChecklistItemDefinition, StageDefinition, WorkflowDefinition,
    WorkflowDefinitionError,
)


def _stage(key: str, order: int, items: tuple[str, ...]) -> StageDefinition:
    return StageDefinition(
        key, order, f"GATE_{key}_V1",
        tuple(ChecklistItemDefinition(
            item, True, "EVIDENCE_FIXED_PROJECT_V1", f"REVIEW_{key}_V1",
        ) for item in items),
    )


_DEFINITION = WorkflowDefinition(1, (
    _stage("HANDOVER", 1, ("HANDOVER_BASELINE", "HANDOVER_ISSUES")),
    _stage("SURVEY", 2, ("SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION")),
    _stage("REQUIREMENT", 3, ("REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE")),
    _stage("PROTOTYPE", 4, ("PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE")),
    _stage("SOLUTION", 5, ("SOLUTION_APPROVED_SET", "SOLUTION_COVERAGE")),
    _stage("PLAN", 6, ("PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION")),
))


def six_stage_definition(version: int = 1) -> WorkflowDefinition:
    """Return only the explicitly supported historical configuration version.

    No fallback to latest; no project states, Review results or Waivers implied.
    Policy semantics and provenance: docs/workflow/six-stage-definition-v1.md.
    """
    if type(version) is not int or version != 1:
        raise WorkflowDefinitionError()
    return _DEFINITION
