"""Physical promotion outside UOW; metadata/result/Audit/Job success in ONE UOW."""
from uuid import UUID

from .worker_render import AuditExportWorkerRender, StagedAuditExport
from .worker_capture import AuditExportWorkerError
from .export_result import RecordAuditExportResult, AuditExportResultMutation, AuditExportResultRepositoryPort
from .public import AuditEventDraft
from plm_assistant.modules.document.application.audit_export_metadata import (
    RegisterAuditFile, AuditFileMetadata, AuditFileMutation, AuditExportFileMetadataPort,
)
from plm_assistant.modules.document.application.audit_export_storage import AuditFileContent
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.platform.application.system_actor import SystemActorUnavailable, SystemActorPort
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletionPort


class AuditExportWorkerPublish(AuditExportWorkerRender):
    def __init__(self, *, files: AuditExportFileMetadataPort, results: AuditExportResultRepositoryPort,
                 completion: AuditExportJobCompletionPort, audit, system_actor: SystemActorPort, **dependencies):
        if any(v is None for v in (files, results, completion, audit, system_actor)):
            raise ValueError('Publication dependencies required')
        super().__init__(**dependencies)
        self._files, self._results, self._completion = files, results, completion
        self._audit, self._system_actor = audit, system_actor

    def _identity(self):
        try:
            identity = self._system_actor.assert_current()
            if type(identity) is not UUID or not identity.int:
                raise SystemActorUnavailable()
            return identity
        except Exception:
            raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE') from None

    def _bound(self, tx, c, staged):
        intent, request, claim = self._authorized(tx, c, 'PUBLISH')
        capture = self._captures.read_capture(tx, request=request)
        self._result(capture, intent)
        plan = self._plans.register(tx, intent=intent, capture=capture, claim=claim, worker_ref=c.worker_ref)
        context = staged.context
        if (intent, capture, plan) != (context.intent, context.capture, context.plan):
            raise AuditExportWorkerError()
        if self._results.get(tx, export_id=intent.export_id) is not None:
            raise AuditExportWorkerError()  # No terminal re-finish or guessed success replay.
        accepted = self._repository.get_accepted(tx, intent=intent)
        return intent, request, claim, accepted

    @staticmethod
    def _file_request(staged):
        intent = staged.context.intent
        return RegisterAuditFile(intent.export_id, intent.actor_id, intent.trace_id, staged.content)

    @staticmethod
    def _metadata(value, request, state):
        if type(value) is not AuditFileMetadata:
            raise AuditExportWorkerError()
        value.__post_init__()
        if ((value.content, value.export_id, value.actor_id, value.registration_trace_id, value.state)
                != (request.content, request.export_id, request.actor_id, request.trace_id, state)):
            raise AuditExportWorkerError()

    def _register(self, c, staged, identity):
        with self._uow() as tx:
            intent, request, claim, _ = self._bound(tx, c, staged)
            file_request = self._file_request(staged)
            mutation = self._files.register_staged(tx, request=file_request)
            if type(mutation) is not AuditFileMutation:
                raise AuditExportWorkerError()
            mutation.__post_init__()
            self._metadata(mutation.metadata, file_request, 'STAGED')
            if self._authority.assert_current(tx, request=request) is not None:
                raise AuditExportWorkerError()
            if self._identity() != identity or self._lease(tx, c, intent) != claim:
                raise AuditExportWorkerError()
            tx.commit()

    def _preflight(self, c, staged, identity):
        with self._uow() as tx:
            intent, request, claim, _ = self._bound(tx, c, staged)
            if self._authority.assert_current(tx, request=request) is not None:
                raise AuditExportWorkerError()
            if self._identity() != identity or self._lease(tx, c, intent) != claim:
                raise AuditExportWorkerError()
            tx.commit()

    def _publish(self, c, staged, identity):
        with self._uow() as tx:
            intent, request, claim, accepted = self._bound(tx, c, staged)
            file_request = self._file_request(staged)
            self._metadata(self._files.get(tx, request=file_request), file_request, 'STAGED')
            mutation = self._files.mark_available(tx, request=file_request, expected_version=0)
            if type(mutation) is not AuditFileMutation or mutation.changed is not True:
                raise AuditExportWorkerError()
            mutation.__post_init__()
            self._metadata(mutation.metadata, file_request, 'AVAILABLE')
            if self._identity() != identity:
                raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            event_id = self._audit.append(tx, AuditEventDraft(
                trace_id=intent.trace_id, event_scope=intent.spec.scope,
                target_project_id=intent.spec.project_id, actor_type='SYSTEM', actor_id=identity,
                original_actor_id=intent.actor_id, actor_hint_digest=None,
                action='AUDIT_EXPORT_PUBLISHED', outcome='SUCCESS', target_owner_module='jobs',
                target_object_type='JOB-01', target_object_id=c.job_id,
                reason_code=intent.spec.purpose, before_state='RUNNING', after_state='SUCCEEDED',
            ))
            result = self._results.record(tx, request=RecordAuditExportResult(
                staged.context.plan, staged.rendered, event_id,
            ))
            if type(result) is not AuditExportResultMutation or result.changed is not True:
                raise AuditExportWorkerError()
            result.__post_init__()
            value = result.result
            if ((value.export_id, value.render_attempt_id, value.file_id, value.file_sha256,
                 value.byte_count, value.manifest_bytes, value.publish_audit_event_id)
                    != (intent.export_id, staged.context.plan.render_attempt_id, staged.context.plan.file_id,
                        staged.content.sha256, staged.content.size_bytes, staged.rendered.manifest_bytes, event_id)):
                raise AuditExportWorkerError()
            if self._authority.assert_current(tx, request=request) is not None:
                raise AuditExportWorkerError()
            if self._identity() != identity:
                raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            finished = self._completion.complete_current(tx,
                request=AuditExportJobRequest(intent.export_id, intent.actor_id, intent.spec.scope,
                    intent.spec.project_id, intent.trace_id, intent.policy_version),
                refs=AuditExportJobRef(accepted.job_id, accepted.event_id),
                fencing_token=c.fencing_token, worker_ref=c.worker_ref,
            )
            if finished != claim:
                raise AuditExportWorkerError()
            tx.commit()  # No long work, callbacks or file I/O after lease completion.
            return value

    def publish(self, command, staged):
        """One physical attempt; failures retain private staged metadata/content.

        A stable result is never inferred from a promoted file. Recovery and
        authorized success replay require separate source-based Owner paths.
        """
        if type(staged) is not StagedAuditExport:
            raise AuditExportWorkerError('VALIDATION_FAILED')
        staged.__post_init__()
        identity = self._identity()
        try:
            self._run(command, lambda c: self._preflight(c, staged, identity))
            proof = self._storage.verify_staged(staged.content)
            if type(proof) is not AuditFileContent or proof != staged.content:
                raise AuditExportWorkerError()
            self._run(command, lambda c: self._register(c, staged, identity))
            promoted = self._storage.promote(staged.content)  # Hash/promotion outside every UOW.
            if type(promoted) is not AuditFileContent or promoted != staged.content:
                raise AuditExportWorkerError()
            return self._run(command, lambda c: self._publish(c, staged, identity))
        except AuditExportWorkerError:
            raise
        except Exception:
            raise AuditExportWorkerError('AUDIT_EXPORT_PUBLISH_FAILED') from None
