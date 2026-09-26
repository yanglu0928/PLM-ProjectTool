"""Internal licensed/authorized PROJECT start with same-tx immutable replay."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS, AuthorizedProjectAction, ProjectAuthorizationError
from plm_assistant.modules.project.application.reviewers import ProjectReviewerFacts, ReviewReviewerEligibilityError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,IdempotencyScope,IdempotencyResult,canonical_payload_fingerprint,validate_idempotency_key,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from .create_review import _code
from .persist_round import ReviewRoundPersistenceService, ReviewRoundPersistError, StartedReviewRoundRef
from .read_snapshot import ReviewIdentitySnapshot
from .subject_start import ReviewSubjectAccessDenied
from ..domain.round_progress import _uuid,_utc


class ReviewStartError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


class _RetryReviewDeadlock(RuntimeError):
    pass


@dataclass(frozen=True,slots=True)
class StartReviewRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    project_id: UUID
    review_id: UUID
    subject_version_id: UUID
    reviewer_ids: tuple[UUID,...]
    policy_code: str
    expected_version: int
    trace_id: UUID


class ReviewStartService:
    def __init__(self,*,unit_of_work,access,projects,reviewers,license_guard,repository,receipts,audit,subjects=None,clock=None):
        if any(v is None for v in (unit_of_work,access,projects,reviewers,license_guard,repository,receipts,audit)):
            raise ValueError("Review start dependencies required")
        self._uow,self._access,self._projects,self._reviewers=unit_of_work,access,projects,reviewers
        self._guard,self._repository,self._receipts,self._subjects=license_guard,repository,receipts,subjects
        self._clock=clock or (lambda:datetime.now(timezone.utc))
        self._persist=ReviewRoundPersistenceService(repository=repository,audit=audit,subjects=subjects,clock=self._clock)

    def start_idempotent(self,command,*,idempotency_key):
        for attempt in range(3):
            try:
                return self._start_once(command,idempotency_key=idempotency_key)
            except _RetryReviewDeadlock:
                if attempt==2: raise ReviewStartError("REVIEW_UNAVAILABLE") from None

    def _start_once(self,command,*,idempotency_key):
        if (type(command) is not StartReviewRound or any(type(v) is not bytes or len(v)!=32 for v in (command.session_token,command.csrf_token))
                or not all(_uuid(v) for v in (command.project_id,command.review_id,command.subject_version_id,command.trace_id))
                or type(command.reviewer_ids) is not tuple or not command.reviewer_ids or not all(_uuid(v) for v in command.reviewer_ids)
                or len(set(command.reviewer_ids))!=len(command.reviewer_ids) or not _code(command.policy_code)
                or type(command.expected_version) is not int or not 0<=command.expected_version<2**63-1):
            raise ReviewStartError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(idempotency_key)
            ordered=tuple(sorted(command.reviewer_ids))
            fingerprint=canonical_payload_fingerprint(dict(review_id=str(command.review_id),subject_version_id=str(command.subject_version_id),
                reviewer_ids=[str(v) for v in ordered],policy_code=command.policy_code,expected_version=command.expected_version))
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now=self._clock()
                if not _utc(now): raise ReviewStartError("REVIEW_UNAVAILABLE")
                actor=self._access.authenticated_user(tx,session_token=command.session_token,csrf_token=command.csrf_token,now=now)
                if not _uuid(actor): raise ReviewStartError("AUTH_ACCESS_DENIED")
                # Prelock may observe missing/disabled candidates, but does not
                # reveal eligibility errors until current PM permission passes.
                locked=self._reviewers.lock_users_in_transaction(tx,reviewer_ids=ordered)
                proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=command.project_id,operation="REVIEW_START_ROUND")
                if (type(proof) is not AuthorizedProjectAction or proof.user_id!=actor or proof.project_id!=command.project_id
                        or proof.operation!="REVIEW_START_ROUND" or proof.project_role!="PROJECT_MANAGER"):
                    raise ReviewStartError("RESOURCE_NOT_FOUND")
                if self._subjects is None: raise ReviewStartError("RESOURCE_NOT_FOUND")
                root,_=self._repository.lock_start_context(tx,project_id=command.project_id,review_id=command.review_id)
                if root is None: raise ReviewStartError("RESOURCE_NOT_FOUND")
                if (type(root) is not ReviewIdentitySnapshot or root.project_id!=command.project_id or root.scope!="PROJECT" or root.review_id!=command.review_id):
                    raise ReviewStartError("REVIEW_UNAVAILABLE")
                if root.policy_code!=command.policy_code: raise ReviewStartError("VALIDATION_FAILED")
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=command.project_id,operation="V1_REVIEW_START_ROUND",key=idempotency_key)
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if type(replay) is not IdempotencyResult or replay.ref_type!="V1_REVIEW_ROUND" or replay.status_code!=201:
                        raise ReviewStartError("REVIEW_UNAVAILABLE")
                    data=self._repository.get_started_ref(tx,project_id=command.project_id,review_id=command.review_id,round_id=replay.ref_id)
                    if type(data) is not tuple or len(data)!=2: raise ReviewStartError("REVIEW_UNAVAILABLE")
                    result,original_reviewers=data
                    if (type(result) is not StartedReviewRoundRef or result.round_id!=replay.ref_id or result.review_id!=command.review_id
                            or result.project_id!=command.project_id or result.subject_version_id!=command.subject_version_id
                            or result.started_by!=actor or original_reviewers!=ordered): raise ReviewStartError("REVIEW_UNAVAILABLE")
                    result.__post_init__()
                    if self._subjects.require_start_replay_access_in_transaction(tx,actor_id=actor,review=root,round_ref=result) is not None:
                        raise ReviewStartError("RESOURCE_NOT_FOUND")
                    return result
                facts=self._reviewers.qualify_locked_in_transaction(tx,project_id=command.project_id,locked=locked,allowed_roles=ALL_MEMBERS,reviewer_ids=ordered)
                if (type(facts) is not tuple or len(facts)!=len(ordered) or any(type(f) is not ProjectReviewerFacts
                        or f.user_id!=user or f.project_id!=command.project_id or f.project_role not in ALL_MEMBERS for f,user in zip(facts,ordered))):
                    raise ReviewStartError("REVIEW_REVIEWER_INELIGIBLE")
                result=self._persist.start_in_transaction(tx,actor_id=actor,project_id=command.project_id,review_id=command.review_id,
                    subject_version_id=command.subject_version_id,reviewer_ids=ordered,expected_version=command.expected_version,trace_id=command.trace_id)
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult("V1_REVIEW_ROUND",result.round_id,201))
                tx.commit()
                return result
        except ReviewStartError: raise
        except ReviewSubjectAccessDenied:
            raise ReviewStartError("RESOURCE_NOT_FOUND") from None
        except (IdempotencyError,ReviewRoundPersistError,ReviewReviewerEligibilityError) as exc:
            raise ReviewStartError(exc.code) from None
        except ProjectAuthorizationError as exc:
            raise ReviewStartError("PROJECT_ARCHIVED" if exc.code=="PROJECT_ARCHIVED" else "RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise ReviewStartError("LICENSE_OPERATION_DENIED") from None
        except Exception as exc:
            classifier=getattr(self._repository,"is_retryable_deadlock",None)
            if callable(classifier) and classifier(exc) is True:
                raise _RetryReviewDeadlock() from None
            raise ReviewStartError("REVIEW_UNAVAILABLE") from None
