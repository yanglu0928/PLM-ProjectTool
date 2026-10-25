"""Internal identity creation, not start/approval; unknown Subject Owner fails closed."""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Protocol
from uuid import UUID

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction, ProjectAuthorizationError
from ..domain.round_progress import _utc, _uuid


class ReviewCreateError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _code(value, *, subject=False):
    return type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_-]{0,63}" if subject else r"[A-Z][A-Z0-9_]{0,63}", value) is not None


@dataclass(frozen=True, slots=True)
class CreateReview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: UUID
    project_id: UUID
    subject_type: str
    subject_id: UUID
    subject_version_id: UUID


@dataclass(frozen=True, slots=True)
class AuthorizedReviewCreation:
    user_id: UUID
    project_id: UUID
    subject_type: str
    subject_id: UUID
    subject_version_id: UUID
    policy_code: str


@dataclass(frozen=True, slots=True)
class CreatedReviewRef:
    review_id: UUID
    project_id: UUID
    subject_type: str
    subject_id: UUID
    policy_code: str
    created_by: UUID
    created_at: datetime

    def __post_init__(self):
        if (not all(_uuid(v) for v in (self.review_id, self.project_id, self.subject_id, self.created_by))
                or not _code(self.subject_type, subject=True) or not _code(self.policy_code) or not _utc(self.created_at)):
            raise ReviewCreateError("REVIEW_UNAVAILABLE")


class ReviewCreationOwnerPort(Protocol):
    def authorize_create(self, tx: object, *, user_id: UUID, project_id: UUID, subject_type: str,
                         subject_id: UUID, subject_version_id: UUID) -> AuthorizedReviewCreation | None: ...
    def authorize_replay(self, tx: object, *, user_id: UUID, review: CreatedReviewRef) -> bool: ...


class ReviewCreationRepositoryPort(Protocol):
    def create(self, tx: object, *, proof: AuthorizedReviewCreation) -> CreatedReviewRef: ...
    def get_created(self, tx: object, *, project_id: UUID, review_id: UUID) -> CreatedReviewRef | None: ...


class ReviewCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access, projects, license_guard,
                 repository: ReviewCreationRepositoryPort, receipts, audit: AuditService,
                 subjects: ReviewCreationOwnerPort | None = None, clock: Callable[[], datetime] | None = None):
        if any(v is None for v in (unit_of_work, access, projects, license_guard, repository, receipts, audit)):
            raise ValueError("Review creation dependencies required")
        self._uow, self._access, self._projects = unit_of_work, access, projects
        self._guard, self._repository, self._receipts = license_guard, repository, receipts
        self._audit, self._subjects = audit, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create_idempotent(self, command: CreateReview, *, idempotency_key: str) -> CreatedReviewRef:
        if (type(command) is not CreateReview or not _code(command.subject_type, subject=True)
                or not all(_uuid(v) for v in (command.trace_id, command.project_id, command.subject_id, command.subject_version_id))
                or any(type(v) is not bytes or len(v) != 32 for v in (command.session_token, command.csrf_token))):
            raise ReviewCreateError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint(dict(project_id=str(command.project_id), subject_type=command.subject_type,
                subject_id=str(command.subject_id), subject_version_id=str(command.subject_version_id)))
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise ReviewCreateError("REVIEW_UNAVAILABLE")
                actor = self._access.authenticated_user(tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now.astimezone(timezone.utc))
                if not _uuid(actor):
                    raise ReviewCreateError("AUTH_ACCESS_DENIED")
                authorized = self._projects.require_in_transaction(tx, user_id=actor, project_id=command.project_id, operation="REVIEW_CREATE")
                if (type(authorized) is not AuthorizedProjectAction or authorized.user_id != actor
                        or authorized.project_id != command.project_id or authorized.operation != "REVIEW_CREATE"
                        or authorized.project_role != "PROJECT_MANAGER"):
                    raise ReviewCreateError("RESOURCE_NOT_FOUND")
                if self._subjects is None:
                    raise ReviewCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(actor_id=actor, project_id=command.project_id, operation="V1_REVIEW_CREATE", key=idempotency_key)
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if type(replay) is not IdempotencyResult or replay.ref_type != "V1_REVIEW" or replay.status_code != 201:
                        raise ReviewCreateError("REVIEW_UNAVAILABLE")
                    result = self._repository.get_created(tx, project_id=command.project_id, review_id=replay.ref_id)
                    self._validate_result(result, command, actor)
                    if result.review_id != replay.ref_id or self._subjects.authorize_replay(tx, user_id=actor, review=result) is not True:
                        raise ReviewCreateError("RESOURCE_NOT_FOUND")
                    return result
                proof = self._subjects.authorize_create(tx, user_id=actor, project_id=command.project_id,
                    subject_type=command.subject_type, subject_id=command.subject_id, subject_version_id=command.subject_version_id)
                if (type(proof) is not AuthorizedReviewCreation or proof.user_id != actor or proof.project_id != command.project_id
                        or proof.subject_type != command.subject_type or proof.subject_id != command.subject_id
                        or proof.subject_version_id != command.subject_version_id or not _code(proof.policy_code)):
                    raise ReviewCreateError("RESOURCE_NOT_FOUND")
                result = self._repository.create(tx, proof=proof)
                self._validate_result(result, command, actor)
                if result.policy_code != proof.policy_code:
                    raise ReviewCreateError("REVIEW_UNAVAILABLE")
                self._audit.append(tx, AuditEventDraft(trace_id=command.trace_id, event_scope="PROJECT", target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="REVIEW_CREATED", outcome="SUCCESS", target_owner_module="review", target_object_type="RVW-01",
                    target_object_id=result.review_id, after_state="DRAFT"))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult("V1_REVIEW", result.review_id, 201))
                tx.commit()
                return result
        except ReviewCreateError:
            raise
        except IdempotencyError as exc:
            raise ReviewCreateError(exc.code) from None
        except ProjectAuthorizationError as exc:
            raise ReviewCreateError("PROJECT_ARCHIVED" if exc.code == "PROJECT_ARCHIVED" else "RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise ReviewCreateError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReviewCreateError("REVIEW_UNAVAILABLE") from None

    @staticmethod
    def _validate_result(result, command, actor):
        if (type(result) is not CreatedReviewRef or result.project_id != command.project_id
                or result.subject_type != command.subject_type or result.subject_id != command.subject_id or result.created_by != actor):
            raise ReviewCreateError("REVIEW_UNAVAILABLE")
        result.__post_init__()
