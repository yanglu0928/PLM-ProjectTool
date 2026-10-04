"""Bounded candidate pagination; positions private until protected by an opaque codec."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from .authorized_read import JobReadFacts, JobDetail, JobReadError, _id, _time
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction, ProjectAuthorizationError, ALL_MEMBERS
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


def _position(value):
    return type(value) is tuple and len(value) == 2 and _time(value[0]) and _id(value[1])


@dataclass(frozen=True, slots=True)
class JobListQuery:
    session_token: bytes = field(repr=False)
    project_id: UUID | None
    trace_id: UUID
    page_size: int = 50
    before: tuple[datetime, UUID] | None = None
    scope: str | None = None

    def __post_init__(self):
        if (type(self.session_token) is not bytes or len(self.session_token) != 32 or not _id(self.trace_id)
            or self.project_id is not None and not _id(self.project_id)
            or type(self.page_size) is not int or not 1 <= self.page_size <= 200
            or self.before is not None and not _position(self.before)
            or self.scope is not None and (type(self.scope) is not str or self.scope not in ('PROJECT', 'GLOBAL', 'DEPLOYMENT'))
            or self.project_id is not None and self.scope not in (None, 'PROJECT')
            or self.project_id is None and self.scope == 'PROJECT'):
            raise JobReadError('VALIDATION_FAILED')


@dataclass(frozen=True, slots=True)
class JobListCandidates:
    items: tuple[JobReadFacts, ...]
    has_more: bool

    def __post_init__(self):
        if type(self.items) is not tuple or type(self.has_more) is not bool or len(self.items) > 200:
            raise JobReadError()
        for item in self.items:
            if type(item) is not JobReadFacts: raise JobReadError()
            item.__post_init__()
        positions = [(item.created_at, item.job_id) for item in self.items]
        if len(set(item.job_id for item in self.items)) != len(self.items) or any(a <= b for a, b in zip(positions, positions[1:])):
            raise JobReadError()
        if self.has_more and not self.items: raise JobReadError()


@dataclass(frozen=True, slots=True)
class JobListPage:
    items: tuple[JobDetail, ...]
    next_position: tuple[datetime, UUID] | None = field(repr=False)
    has_more: bool

    def __post_init__(self):
        if (type(self.items) is not tuple or type(self.has_more) is not bool or len(self.items) > 200
            or self.has_more != (self.next_position is not None)
            or self.next_position is not None and not _position(self.next_position)):
            raise JobReadError()
        for item in self.items:
            if type(item) is not JobDetail: raise JobReadError()
            item.__post_init__()


class AuthorizedJobListService:
    def __init__(self, *, unit_of_work, project_access, deployment_access, projects, license_guard, repository, owners, clock=None):
        if any(v is None for v in (unit_of_work, project_access, deployment_access, projects, license_guard, repository)):
            raise ValueError('Actual current list dependencies required')
        if type(owners) is not dict or not owners or any(type(k) is not tuple or len(k) != 2
            or any(type(x) is not str or not x for x in k) or not callable(getattr(v, 'project', None)) for k, v in owners.items()):
            raise ValueError('Explicit list Owner registry required')
        self._uow, self._project, self._admin, self._projects, self._guard, self._repo = unit_of_work, project_access, deployment_access, projects, license_guard, repository
        self._owners = dict(owners); self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list(self, q):
        if type(q) is not JobListQuery: raise JobReadError('VALIDATION_FAILED')
        q.__post_init__()
        try:
            self._guard.require_valid(trace_id=q.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if not _time(now): raise JobReadError()
                actor = (self._admin.authorized_admin if q.project_id is None else self._project.authenticated_user)(tx, session_token=q.session_token, now=now)
                if not _id(actor): raise JobReadError('AUTH_ACCESS_DENIED')
                role = None
                if q.project_id is not None:
                    proof = self._projects.require_in_transaction(tx, user_id=actor, project_id=q.project_id, operation='JOB_PROJECT_LIST')
                    if (type(proof) is not AuthorizedProjectAction or (proof.user_id, proof.project_id, proof.operation) != (actor, q.project_id, 'JOB_PROJECT_LIST')
                        or proof.project_role not in ALL_MEMBERS): raise JobReadError('RESOURCE_NOT_FOUND')
                    role = proof.project_role
                creator = actor if role in ('CUSTOMER_MANAGER', 'CUSTOMER_MEMBER') else None
                page = self._repo.list(tx, project_id=q.project_id, scope=q.scope, actor_id=creator,
                    owner_types=tuple(sorted(self._owners)), before=q.before, limit=q.page_size)
                if type(page) is not JobListCandidates: raise JobReadError()
                page.__post_init__()
                if len(page.items) > q.page_size: raise JobReadError()
                visible = []
                for facts in page.items:
                    if (facts.project_id != q.project_id or (q.project_id is None and facts.scope == 'PROJECT')
                        or q.scope is not None and facts.scope != q.scope
                        or creator is not None and facts.actor_id != creator
                        or q.before is not None and (facts.created_at, facts.job_id) >= q.before): raise JobReadError()
                    owner = self._owners.get((facts.owner_module, facts.job_type))
                    if owner is None: raise JobReadError()
                    try:
                        detail = JobDetail(facts, owner.project(tx, facts=facts, actor_id=actor, project_role=role))
                    except JobReadError as exc:
                        if exc.code == 'RESOURCE_NOT_FOUND': continue
                        raise
                    detail.__post_init__()
                    if self._repo.get(tx, job_id=facts.job_id) != facts: raise JobReadError()
                    visible.append(detail)
                self._guard.require_valid(trace_id=q.trace_id)
                position = (page.items[-1].created_at, page.items[-1].job_id) if page.has_more else None
                return JobListPage(tuple(visible), position, page.has_more)
        except JobReadError: raise
        except ProjectAuthorizationError: raise JobReadError('RESOURCE_NOT_FOUND') from None
        except RuntimeLicenseError: raise JobReadError('LICENSE_OPERATION_DENIED') from None
        except Exception: raise JobReadError() from None
