"""Current-authorized Document Parser Job cancellation Owner."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import DBAPIError

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceError
from plm_assistant.modules.jobs.application.cancel_request import (
    JobCancelError, JobCancelResult, RequestProjectJobCancel,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class DocumentParseJobCancelOwner:
    def __init__(self, *, unit_of_work, queue, sources, project_access, projects,
                 license_guard, cancellations, receipts, audit_sources, audit):
        if any(value is None for value in (unit_of_work, queue, sources, project_access,
                projects, license_guard, cancellations, receipts, audit_sources, audit)):
            raise ValueError("Current Parser cancellation dependencies required")
        self._uow = unit_of_work
        self._queue, self._sources = queue, sources
        self._access, self._projects, self._guard = project_access, projects, license_guard
        self._cancel, self._receipts = cancellations, receipts
        self._audit_sources, self._audit = audit_sources, audit

    @staticmethod
    def _deadlock(error):
        seen = set()
        for _ in range(16):
            if not isinstance(error, BaseException) or id(error) in seen:
                return False
            seen.add(id(error))
            if isinstance(error, DBAPIError) and getattr(error.orig, "sqlstate", None) == "40P01":
                return True
            error = error.__cause__ or error.__context__
        return False

    def _authorize(self, tx, c, original_actor_id):
        self._guard.require_valid(trace_id=c.trace_id)
        actor = self._access.authenticated_user(
            tx, session_token=c.session_token, csrf_token=c.csrf_token,
            now=datetime.now(timezone.utc))
        if actor is None:
            raise JobCancelError("RESOURCE_NOT_FOUND")
        proof = self._projects.require_in_transaction(
            tx, user_id=actor, project_id=c.project_id, operation="JOB_PROJECT_CANCEL")
        if proof.user_id != actor or proof.project_id != c.project_id or (
                actor != original_actor_id and proof.project_role != "PROJECT_MANAGER"):
            raise JobCancelError("RESOURCE_NOT_FOUND")
        return actor

    def cancel(self, c, *, idempotency_key):
        if type(c) is not RequestProjectJobCancel:
            raise JobCancelError("VALIDATION_FAILED")
        c.__post_init__()
        try:
            validate_idempotency_key(idempotency_key)
        except IdempotencyError as exc:
            raise JobCancelError(exc.code) from None
        for attempt in range(3):
            try:
                return self._cancel_once(c, idempotency_key)
            except Exception as exc:
                if self._deadlock(exc):
                    if attempt < 2:
                        continue
                    raise JobCancelError() from None
                if isinstance(exc, JobCancelError):
                    raise
                if isinstance(exc, IdempotencyError):
                    raise JobCancelError(exc.code) from None
                if isinstance(exc, ProjectAuthorizationError):
                    raise JobCancelError("RESOURCE_NOT_FOUND") from None
                if isinstance(exc, RuntimeLicenseError):
                    raise JobCancelError("LICENSE_OPERATION_DENIED") from None
                if isinstance(exc, DocumentParseSourceError) and exc.code == "RESOURCE_NOT_FOUND":
                    raise JobCancelError("RESOURCE_NOT_FOUND") from None
                raise JobCancelError() from None
        raise JobCancelError()

    def _cancel_once(self, c, key):
        with self._uow() as tx:
            binding = self._queue.peek_parse_for_job(tx, job_id=c.job_id)
            if binding is None or (binding.request.scope, binding.request.project_id) != (
                    "PROJECT", c.project_id):
                raise JobCancelError("RESOURCE_NOT_FOUND")
            actor = self._authorize(tx, c, binding.request.actor_id)
            self._sources.read(tx, request=binding.request)
            if self._queue.find_parse(tx, request=binding.request) != binding.refs:
                raise JobCancelError("RESOURCE_NOT_FOUND")
            before = self._cancel.read_facts(tx, binding=binding)
            if before.requested_by is not None:
                self._audit_sources.first_request(
                    tx, job_id=c.job_id, project_id=c.project_id,
                    requested_by=before.requested_by, requested_at=before.requested_at)
            scope = IdempotencyScope.from_key(
                actor_id=actor, project_id=c.project_id,
                operation="V1_DOCUMENT_PARSE_CANCEL", key=key)
            fingerprint = canonical_payload_fingerprint(dict(
                job_id=str(c.job_id), upload_id=str(binding.request.upload_id),
                document_version_id=str(binding.request.document_version_id),
                reason=c.reason, expected_version=c.expected_version))
            replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
            if replay is not None:
                if (type(replay) is not IdempotencyResult
                        or replay.ref_type != "V1_DOCUMENT_PARSE_CANCEL" or replay.status_code != 200):
                    raise JobCancelError()
                state, changed = self._audit_sources.receipt(
                    tx, job_id=c.job_id, project_id=c.project_id,
                    actor_id=actor, event_id=replay.ref_id)
                version = self._cancel.receipt_version(tx, event_id=replay.ref_id)
            else:
                if before.lock_version != c.expected_version:
                    raise JobCancelError("CONFLICT_VERSION")
                mutation = self._cancel.request_cancel(
                    tx, binding=binding, requested_by=actor, reason=c.reason)
                event_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=c.trace_id, event_scope="PROJECT", target_project_id=c.project_id,
                    actor_type="USER", actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None,
                    action="DOCUMENT_PARSE_CANCEL_REQUESTED" if mutation.changed
                           else "DOCUMENT_PARSE_CANCEL_CHECKED",
                    outcome="SUCCESS", target_owner_module="jobs", target_object_type="JOB-01",
                    target_object_id=c.job_id, reason_code="USER_REQUESTED",
                    before_state=before.state, after_state=mutation.state))
                current = self._cancel.read_facts(tx, binding=binding)
                if current.state != mutation.state:
                    raise JobCancelError()
                self._cancel.record_version(tx, event_id=event_id,
                                            lock_version=current.lock_version)
                state, changed = self._audit_sources.receipt(
                    tx, job_id=c.job_id, project_id=c.project_id,
                    actor_id=actor, event_id=event_id)
                version = self._cancel.receipt_version(tx, event_id=event_id)
                if (state, changed, version) != (
                        mutation.state, mutation.changed, current.lock_version):
                    raise JobCancelError()
                self._receipts.complete(tx, scope=scope,
                    result=IdempotencyResult("V1_DOCUMENT_PARSE_CANCEL", event_id, 200))
            if self._authorize(tx, c, binding.request.actor_id) != actor:
                raise JobCancelError("RESOURCE_NOT_FOUND")
            result = JobCancelResult(c.job_id, state, changed, version)
            if replay is None:
                tx.commit()
            return result
