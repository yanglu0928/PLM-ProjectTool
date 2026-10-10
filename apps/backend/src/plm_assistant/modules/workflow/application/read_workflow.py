"""Current authorized Workflow snapshot; reads never initialize missing instances."""
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, AuthorizedProjectAction, ProjectAuthorizationError,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition


class WorkflowReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkflowReadQuery:
    session_token: bytes = field(repr=False)
    project_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ChecklistView:
    item_key: str
    required: bool
    state: str


@dataclass(frozen=True, slots=True)
class StageView:
    stage_key: str
    order: int
    state: str
    checklist_items: tuple[ChecklistView, ...]


@dataclass(frozen=True, slots=True)
class WorkflowView:
    workflow_id: uuid.UUID
    project_id: uuid.UUID
    version: int
    state: str
    current_stage: str | None
    stages: tuple[StageView, ...]
    lock_version: int

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'

    def __post_init__(self) -> None:
        if (any(type(v) is not uuid.UUID or v.int == 0 for v in (self.workflow_id, self.project_id))
                or type(self.version) is not int or self.version != 1
                or type(self.lock_version) is not int or self.lock_version < 0
                or type(self.state) is not str or self.state not in ("NOT_STARTED", "ACTIVE", "COMPLETED")
                or type(self.stages) is not tuple or len(self.stages) != 6
                or self.current_stage is not None and type(self.current_stage) is not str):
            raise WorkflowReadError("WORKFLOW_UNAVAILABLE")
        for stage, defined in zip(self.stages, six_stage_definition(1).stages):
            if (type(stage) is not StageView or stage.stage_key != defined.stage_key
                    or type(stage.order) is not int or stage.order != defined.order
                    or type(stage.state) is not str or stage.state not in ("NOT_STARTED", "ACTIVE", "BLOCKED", "COMPLETED")
                    or type(stage.checklist_items) is not tuple or len(stage.checklist_items) != 2):
                raise WorkflowReadError("WORKFLOW_UNAVAILABLE")
            for item, expected in zip(stage.checklist_items, defined.checklist_items):
                if (type(item) is not ChecklistView or item.item_key != expected.item_key
                        or type(item.required) is not bool or item.required != expected.required
                        or type(item.state) is not str or item.state not in ("PENDING", "PASS", "FAIL", "WAIVED")):
                    raise WorkflowReadError("WORKFLOW_UNAVAILABLE")
        keys = tuple(stage.stage_key for stage in self.stages)
        if self.state == "NOT_STARTED":
            valid = self.current_stage is None and all(
                s.state == "NOT_STARTED" and all(i.state == "PENDING" for i in s.checklist_items)
                for s in self.stages)
        elif self.state == "COMPLETED":
            valid = self.current_stage == keys[-1] and all(s.state == "COMPLETED" for s in self.stages)
        else:
            valid = self.current_stage in keys
            if valid:
                index = keys.index(self.current_stage)
                valid = all(s.state == "COMPLETED" if n < index else
                            s.state in ("ACTIVE", "BLOCKED") if n == index else
                            s.state == "NOT_STARTED" for n, s in enumerate(self.stages))
        if not valid:
            raise WorkflowReadError("WORKFLOW_UNAVAILABLE")


class WorkflowReadSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class WorkflowReadProjectPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str) -> AuthorizedProjectAction: ...


class WorkflowReadRepositoryPort(Protocol):
    def get(self, transaction: object, project_id: uuid.UUID) -> WorkflowView | None: ...


class WorkflowReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class WorkflowReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], sessions: WorkflowReadSessionPort,
                 projects: WorkflowReadProjectPort, license_guard: WorkflowReadLicensePort,
                 repository: WorkflowReadRepositoryPort, clock: Callable[[], datetime] | None = None):
        if any(value is None for value in (unit_of_work, sessions, projects, license_guard, repository)):
            raise ValueError("Workflow read dependencies required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._repository = license_guard, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: WorkflowReadQuery) -> WorkflowView:
        if (type(query) is not WorkflowReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (query.project_id, query.trace_id))):
            raise WorkflowReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise WorkflowReadError("WORKFLOW_UNAVAILABLE")
                actor = self._sessions.authenticated_user(tx, session_token=query.session_token, now=now.astimezone(timezone.utc))
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise WorkflowReadError("AUTH_ACCESS_DENIED")
                proof = self._projects.require_in_transaction(tx, user_id=actor, project_id=query.project_id, operation="WORKFLOW_GET")
                if (type(proof) is not AuthorizedProjectAction or proof.user_id != actor
                        or proof.project_id != query.project_id or proof.operation != "WORKFLOW_GET"
                        or proof.project_role not in ALL_MEMBERS):
                    raise WorkflowReadError("RESOURCE_NOT_FOUND")
                view = self._repository.get(tx, query.project_id)
                if view is None:
                    raise WorkflowReadError("RESOURCE_NOT_FOUND")
                if type(view) is not WorkflowView or view.project_id != query.project_id:
                    raise WorkflowReadError("WORKFLOW_UNAVAILABLE")
                return view
        except WorkflowReadError:
            raise
        except ProjectAuthorizationError as exc:
            raise WorkflowReadError(exc.code) from None
        except RuntimeLicenseError:
            raise WorkflowReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise WorkflowReadError("WORKFLOW_UNAVAILABLE") from None
