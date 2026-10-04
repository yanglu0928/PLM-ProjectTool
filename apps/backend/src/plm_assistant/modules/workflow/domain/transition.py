"""Structural preconditions only. Success is not a Gate approval."""

from enum import StrEnum

from .definition import WorkflowDefinition


class WorkflowState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class StageState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class ChecklistState(StrEnum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    WAIVED = "WAIVED"


class WorkflowTransitionError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid Workflow transition")


def validate_forward_structure(
    definition: WorkflowDefinition,
    *,
    workflow_state: WorkflowState,
    current_stage_key: str,
    target_stage_key: str,
    expected_version: int,
    lock_version: int,
    project_archived: bool,
) -> None:
    """Check authoritative current key against the immediately next defined key.

    Versions are optimistic lock versions, not Workflow definition versions.
    This function never changes state or evaluates checklist/Gate evidence.
    Application must also prove current Stage/Gate, authorization and License
    in the same transaction before creating any immutable Transition record.
    BLOCKED Stage recovery and final completion are separate operations.
    """
    if (type(definition) is not WorkflowDefinition
            or type(workflow_state) is not WorkflowState
            or workflow_state is not WorkflowState.ACTIVE
            or type(current_stage_key) is not str
            or type(target_stage_key) is not str
            or type(expected_version) is not int or expected_version < 0
            or type(lock_version) is not int or lock_version < 0
            or expected_version != lock_version
            or type(project_archived) is not bool or project_archived):
        raise WorkflowTransitionError()
    keys = tuple(stage.stage_key for stage in definition.stages)
    if current_stage_key not in keys:
        raise WorkflowTransitionError()
    current_index = keys.index(current_stage_key)
    if (current_index + 1 >= len(keys)
            or target_stage_key != keys[current_index + 1]):
        raise WorkflowTransitionError()
