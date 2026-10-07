"""Authorized current-fact preview for a supported Checklist PASS request."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
)

from .read_workflow import WorkflowView
from .checklist_qualification import (
    ChecklistQualificationError,
    CurrentChecklistQualification,
    CurrentChecklistQualificationQuery,
)


_ITEM_STAGES = {
    "HANDOVER_BASELINE": "HANDOVER",
    "HANDOVER_ISSUES": "HANDOVER",
    "SURVEY_ACTUAL_SOURCES": "SURVEY",
    "SURVEY_CONCLUSION": "SURVEY",
}


class WorkflowChecklistQualificationPreviewError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkflowChecklistQualificationPreviewQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    item_key: str


@dataclass(frozen=True, slots=True)
class WorkflowChecklistQualificationPreview:
    workflow_id: uuid.UUID
    project_id: uuid.UUID
    definition_version: int
    stage_key: str
    item_key: str
    current_item_state: str
    workflow_lock_version: int
    handover_analysis_version_id: uuid.UUID | None
    review_round_ref: uuid.UUID
    evidence_refs: tuple[uuid.UUID, ...]
    survey_conclusion_id: uuid.UUID | None = None

    @property
    def workflow_etag(self) -> str:
        return f'"v{self.workflow_lock_version}"'

    def __post_init__(self) -> None:
        identities = (self.workflow_id, self.project_id, self.review_round_ref)
        subject_id = (self.handover_analysis_version_id
                      if self.stage_key == "HANDOVER"
                      else self.survey_conclusion_id)
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in identities)
                or type(subject_id) is not uuid.UUID or subject_id.int == 0
                or self.definition_version != 1
                or self.item_key not in _ITEM_STAGES
                or self.stage_key != _ITEM_STAGES.get(self.item_key)
                or (self.stage_key == "HANDOVER"
                    and self.survey_conclusion_id is not None)
                or (self.stage_key == "SURVEY"
                    and self.handover_analysis_version_id is not None)
                or self.current_item_state not in {
                    "PENDING", "PASS", "FAIL", "WAIVED",
                }
                or type(self.workflow_lock_version) is not int
                or not 1 <= self.workflow_lock_version < 2**63 - 1
                or type(self.evidence_refs) is not tuple
                or not self.evidence_refs
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in self.evidence_refs)
                or len(set(self.evidence_refs)) != len(self.evidence_refs)):
            raise WorkflowChecklistQualificationPreviewError(
                "WORKFLOW_UNAVAILABLE",
            )


class PreviewSessionPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class PreviewProjectPort(Protocol):
    def require_in_transaction(
        self, transaction: object, *, user_id: uuid.UUID,
        project_id: uuid.UUID, operation: str,
    ) -> AuthorizedProjectAction: ...


class PreviewLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PreviewWorkflowPort(Protocol):
    def get(
        self, transaction: object, project_id: uuid.UUID,
    ) -> WorkflowView | None: ...


class PreviewQualificationPort(Protocol):
    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> CurrentChecklistQualification: ...


class WorkflowChecklistQualificationPreviewService:
    """Return only the exact evidence set needed by the frozen write DTO."""

    def __init__(
        self, *, unit_of_work: Callable[[], object], sessions: PreviewSessionPort,
        projects: PreviewProjectPort, license_guard: PreviewLicensePort,
        workflows: PreviewWorkflowPort,
        qualification: PreviewQualificationPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, sessions, projects, license_guard,
                workflows, qualification)):
            raise ValueError("Checklist qualification preview dependencies required")
        self._uow, self._sessions, self._projects = (
            unit_of_work, sessions, projects,
        )
        self._guard, self._workflows = license_guard, workflows
        self._qualification = qualification
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(
        self, query: WorkflowChecklistQualificationPreviewQuery,
    ) -> WorkflowChecklistQualificationPreview:
        self._validate_query(query)
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, query)
                proof = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="WORKFLOW_CHECKLIST_RECORD",
                )
                if (type(proof) is not AuthorizedProjectAction
                        or proof.user_id != actor
                        or proof.project_id != query.project_id
                        or proof.operation != "WORKFLOW_CHECKLIST_RECORD"
                        or proof.project_role != "PROJECT_MANAGER"):
                    raise WorkflowChecklistQualificationPreviewError(
                        "RESOURCE_NOT_FOUND",
                    )
                before = self._workflows.get(tx, query.project_id)
                item_state = self._item_state(before, query)
                result = self._qualification.qualify_only_current_in_transaction(
                    tx, CurrentChecklistQualificationQuery(
                        query.session_token, query.trace_id,
                        query.project_id, query.item_key,
                    ),
                )
                after = self._workflows.get(tx, query.project_id)
                if after != before:
                    raise WorkflowChecklistQualificationPreviewError(
                        "CONFLICT_VERSION",
                    )
                if (type(result) is not CurrentChecklistQualification
                        or result.project_id != query.project_id
                        or result.item_key != query.item_key):
                    raise WorkflowChecklistQualificationPreviewError(
                        "WORKFLOW_UNAVAILABLE",
                    )
                result.__post_init__()
                preview = WorkflowChecklistQualificationPreview(
                    before.workflow_id, before.project_id, before.version,
                    result.stage_key, query.item_key, item_state,
                    before.lock_version,
                    (result.subject_version_id
                     if result.stage_key == "HANDOVER" else None),
                    result.review.review_round_id,
                    tuple(value.evidence_id for value in result.evidence),
                    (result.subject_version_id
                     if result.stage_key == "SURVEY" else None),
                )
                preview.__post_init__()
                return preview
        except WorkflowChecklistQualificationPreviewError:
            raise
        except ChecklistQualificationError:
            raise WorkflowChecklistQualificationPreviewError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            ) from None
        except ProjectAuthorizationError as error:
            raise WorkflowChecklistQualificationPreviewError(
                error.code,
            ) from None
        except RuntimeLicenseError:
            raise WorkflowChecklistQualificationPreviewError(
                "LICENSE_OPERATION_DENIED",
            ) from None
        except Exception:
            raise WorkflowChecklistQualificationPreviewError(
                "WORKFLOW_UNAVAILABLE",
            ) from None

    @staticmethod
    def _validate_query(
        query: WorkflowChecklistQualificationPreviewQuery,
    ) -> None:
        if (type(query) is not WorkflowChecklistQualificationPreviewQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (query.trace_id, query.project_id))
                or query.item_key not in _ITEM_STAGES):
            raise WorkflowChecklistQualificationPreviewError(
                "VALIDATION_FAILED",
            )

    def _actor(
        self, tx: object,
        query: WorkflowChecklistQualificationPreviewQuery,
    ) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise WorkflowChecklistQualificationPreviewError(
                "WORKFLOW_UNAVAILABLE",
            )
        actor = self._sessions.authenticated_user(
            tx, session_token=query.session_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise WorkflowChecklistQualificationPreviewError(
                "AUTH_ACCESS_DENIED",
            )
        return actor

    @staticmethod
    def _item_state(
        workflow: WorkflowView | None,
        query: WorkflowChecklistQualificationPreviewQuery,
    ) -> str:
        if workflow is None:
            raise WorkflowChecklistQualificationPreviewError(
                "RESOURCE_NOT_FOUND",
            )
        if type(workflow) is not WorkflowView:
            raise WorkflowChecklistQualificationPreviewError(
                "WORKFLOW_UNAVAILABLE",
            )
        workflow.__post_init__()
        if (workflow.project_id != query.project_id
                or workflow.state != "ACTIVE"
                or workflow.current_stage != _ITEM_STAGES[query.item_key]):
            raise WorkflowChecklistQualificationPreviewError(
                "CONFLICT_STATE",
            )
        stage = next(
            (value for value in workflow.stages
             if value.stage_key == workflow.current_stage),
            None,
        )
        if (stage is None or stage.stage_key != workflow.current_stage
                or stage.state not in {"ACTIVE", "BLOCKED"}):
            raise WorkflowChecklistQualificationPreviewError(
                "CONFLICT_STATE",
            )
        item = next(
            (value for value in stage.checklist_items
             if value.item_key == query.item_key),
            None,
        )
        if item is None:
            raise WorkflowChecklistQualificationPreviewError(
                "WORKFLOW_UNAVAILABLE",
            )
        return item.state
