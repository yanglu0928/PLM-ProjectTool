"""Internal current-authorized decision/withdrawal with immutable event replay."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS, AuthorizedProjectAction, ProjectAuthorizationError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyScope, IdempotencyResult, canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from .persist_transition import ReviewTransitionPersistenceService, AppliedReviewTransitionRef
from .persist_round import ReviewRoundPersistError
from .read_snapshot import FixedReviewRoundSnapshot
from .subject_start import ReviewSubjectAccessDenied
from ..domain.round_progress import ReviewDecisionKind, _uuid, _utc


class ReviewTransitionCommandError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


class _RetryTransitionDeadlock(RuntimeError):
    pass


@dataclass(frozen=True,slots=True)
class DecideReviewRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    project_id: UUID
    review_id: UUID
    round_id: UUID
    trace_id: UUID
    decision: ReviewDecisionKind
    comment: str | None = field(default=None,repr=False)


@dataclass(frozen=True,slots=True)
class WithdrawReviewRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    project_id: UUID
    review_id: UUID
    round_id: UUID
    trace_id: UUID
    expected_version: int
    reason: str | None = field(default=None,repr=False)


class ReviewTransitionCommandService:
    def __init__(self,*,unit_of_work,access,projects,license_guard,repository,receipts,audit,subjects=None,clock=None):
        if any(v is None for v in (unit_of_work,access,projects,license_guard,repository,receipts,audit)):
            raise ValueError("Review command dependencies required")
        self._uow,self._access,self._projects=unit_of_work,access,projects
        self._guard,self._repository,self._receipts,self._subjects=license_guard,repository,receipts,subjects
        self._clock=clock or (lambda:datetime.now(timezone.utc))
        self._persist=ReviewTransitionPersistenceService(repository=repository,audit=audit,subjects=subjects,clock=self._clock)

    def decide_idempotent(self,command,*,idempotency_key):
        if type(command) is not DecideReviewRound:
            raise ReviewTransitionCommandError("VALIDATION_FAILED")
        return self._execute(command,idempotency_key)

    def withdraw_idempotent(self,command,*,idempotency_key):
        if type(command) is not WithdrawReviewRound:
            raise ReviewTransitionCommandError("VALIDATION_FAILED")
        return self._execute(command,idempotency_key)

    def _execute(self,command,key):
        for attempt in range(3):
            try: return self._once(command,key)
            except _RetryTransitionDeadlock:
                if attempt==2: raise ReviewTransitionCommandError("REVIEW_UNAVAILABLE") from None

    def _once(self,c,key):
        withdrawing=type(c) is WithdrawReviewRound
        if (any(type(v) is not bytes or len(v)!=32 for v in (c.session_token,c.csrf_token))
                or not all(_uuid(v) for v in (c.project_id,c.review_id,c.round_id,c.trace_id))):
            raise ReviewTransitionCommandError("VALIDATION_FAILED")
        body=c.reason if withdrawing else c.comment
        if body is not None and (type(body) is not str or "\x00" in body or withdrawing and not body.strip()):
            raise ReviewTransitionCommandError("VALIDATION_FAILED")
        if withdrawing:
            if type(c.expected_version) is not int or not 0<=c.expected_version<2**63-1:
                raise ReviewTransitionCommandError("VALIDATION_FAILED")
        else:
            if type(c.decision) is not ReviewDecisionKind:
                raise ReviewTransitionCommandError("VALIDATION_FAILED")
            if c.decision is ReviewDecisionKind.RETURN and (body is None or not body.strip()):
                raise ReviewTransitionCommandError("REVIEW_COMMENT_REQUIRED")
        operation="REVIEW_WITHDRAW" if withdrawing else "REVIEW_DECIDE"
        action="WITHDRAW" if withdrawing else "DECIDE"
        try:
            validate_idempotency_key(key)
            payload=dict(review_id=str(c.review_id),round_id=str(c.round_id))
            payload.update(dict(expected_version=c.expected_version,reason=body) if withdrawing else dict(decision=c.decision.value,comment=body))
            fingerprint=canonical_payload_fingerprint(payload)
            self._guard.require_valid(trace_id=c.trace_id)
            with self._uow() as tx:
                now=self._clock()
                if not _utc(now): raise ReviewTransitionCommandError("REVIEW_UNAVAILABLE")
                actor=self._access.authenticated_user(tx,session_token=c.session_token,csrf_token=c.csrf_token,now=now)
                if not _uuid(actor): raise ReviewTransitionCommandError("AUTH_ACCESS_DENIED")
                proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=c.project_id,operation=operation)
                if (type(proof) is not AuthorizedProjectAction or proof.user_id!=actor or proof.project_id!=c.project_id
                        or proof.operation!=operation or proof.project_role not in ALL_MEMBERS
                        or withdrawing and proof.project_role!="PROJECT_MANAGER"):
                    raise ReviewTransitionCommandError("RESOURCE_NOT_FOUND")
                if self._subjects is None: raise ReviewTransitionCommandError("RESOURCE_NOT_FOUND")
                fixed=self._repository.lock_transition_context(tx,project_id=c.project_id,review_id=c.review_id,round_id=c.round_id)
                if fixed is None: raise ReviewTransitionCommandError("RESOURCE_NOT_FOUND")
                if (type(fixed) is not FixedReviewRoundSnapshot or fixed.review.scope!="PROJECT"
                        or fixed.review.project_id!=c.project_id or fixed.review.review_id!=c.review_id or fixed.progress.round_id!=c.round_id):
                    raise ReviewTransitionCommandError("REVIEW_UNAVAILABLE")
                fixed.__post_init__()
                if not withdrawing and actor not in fixed.progress.reviewer_ids:
                    raise ReviewTransitionCommandError("RESOURCE_NOT_FOUND")
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=c.project_id,operation="V1_"+operation,key=key)
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if type(replay) is not IdempotencyResult or replay.ref_type!="V1_REVIEW_TRANSITION" or replay.status_code!=200:
                        raise ReviewTransitionCommandError("REVIEW_UNAVAILABLE")
                    result=self._repository.get_transition_ref(tx,project_id=c.project_id,review_id=c.review_id,
                        round_id=c.round_id,event_id=replay.ref_id)
                    if (type(result) is not AppliedReviewTransitionRef or result.event_id!=replay.ref_id
                            or result.project_id!=c.project_id or result.review_id!=c.review_id or result.round_id!=c.round_id
                            or result.subject_version_id!=fixed.subject_version_id or result.actor_id!=actor or result.action!=action):
                        raise ReviewTransitionCommandError("REVIEW_UNAVAILABLE")
                    result.__post_init__()
                    if self._subjects.require_transition_replay_access_in_transaction(tx,actor_id=actor,review=fixed.review,result=result) is not None:
                        raise ReviewTransitionCommandError("RESOURCE_NOT_FOUND")
                    return result
                args=dict(actor_id=actor,project_id=c.project_id,review_id=c.review_id,round_id=c.round_id,trace_id=c.trace_id)
                result=self._persist.withdraw_in_transaction(tx,**args,expected_version=c.expected_version,reason=body) if withdrawing else self._persist.decide_in_transaction(
                    tx,**args,decision=c.decision,comment=body)
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult("V1_REVIEW_TRANSITION",result.event_id,200))
                tx.commit()
                return result
        except ReviewTransitionCommandError: raise
        except ReviewSubjectAccessDenied:
            raise ReviewTransitionCommandError("RESOURCE_NOT_FOUND") from None
        except (IdempotencyError,ReviewRoundPersistError) as exc:
            raise ReviewTransitionCommandError(exc.code) from None
        except ProjectAuthorizationError as exc:
            raise ReviewTransitionCommandError("PROJECT_ARCHIVED" if exc.code=="PROJECT_ARCHIVED" else "RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise ReviewTransitionCommandError("LICENSE_OPERATION_DENIED") from None
        except Exception as exc:
            classifier=getattr(self._repository,"is_retryable_deadlock",None)
            if callable(classifier) and classifier(exc) is True:
                raise _RetryTransitionDeadlock() from None
            raise ReviewTransitionCommandError("REVIEW_UNAVAILABLE") from None
