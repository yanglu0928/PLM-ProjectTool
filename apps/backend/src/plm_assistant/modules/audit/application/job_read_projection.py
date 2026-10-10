"""Audit Owner proves original task bindings; metadata grants no content access."""
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts,JobOwnerProjection,JobReadError
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from .submit_export import AuditExportIntent,AcceptedAuditExport
from .export_result import AuditExportResult
from .user_retry_source import AuditUserRetrySource
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction, ProjectAuthorizationError

class AuditJobReadProjection:
    def __init__(self,*,repository,queue,results,retry_sources=None,retry_projects=None):
        if any(v is None for v in (repository,queue,results)):raise ValueError('Actual Audit sources required')
        self._repo,self._queue,self._results=repository,queue,results
        if retry_sources is not None and retry_projects is None:raise ValueError('Current retry Project policy required')
        self._retry_sources,self._retry_projects=retry_sources,retry_projects
    def project(self,tx,*,facts,actor_id,project_role):
        if type(facts) is not JobReadFacts:raise JobReadError()
        facts.__post_init__()
        if (facts.owner_module,facts.job_type)!=('audit','AUDIT_EXPORT'):raise JobReadError('RESOURCE_NOT_FOUND')
        intent=self._repo.get_created_for_job(tx,job_id=facts.job_id)
        if intent is None:raise JobReadError('RESOURCE_NOT_FOUND')
        if type(intent) is not AuditExportIntent:raise JobReadError()
        intent.__post_init__()
        if (intent.actor_id,intent.spec.scope,intent.spec.project_id)!=(facts.actor_id,facts.scope,facts.project_id):raise JobReadError()
        accepted=self._repo.get_accepted(tx,intent=intent)
        if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=facts.job_id:raise JobReadError()
        accepted.__post_init__()
        refs=self._queue.find_export(tx,request=AuditExportJobRequest(intent.export_id,intent.actor_id,
            intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version))
        if type(refs) is not AuditExportJobRef or (refs.job_id,refs.event_id)!=(accepted.job_id,accepted.event_id):raise JobReadError()
        refs.__post_init__()
        if facts.state=='SUCCEEDED':
            result=self._results.get(tx,export_id=intent.export_id)
            if type(result) is not AuditExportResult or result.export_id!=intent.export_id:raise JobReadError()
            result.__post_init__()
            # This is a resource reference, never download permission or a file path.
            return JobOwnerProjection(facts.job_id,False,'AUDIT_EXPORT',intent.export_id)
        if self._retry_sources is not None and facts.state=='FAILED':
            if facts.scope=='PROJECT' and project_role!='PROJECT_MANAGER':return JobOwnerProjection(facts.job_id,False)
            try:
                if facts.scope=='PROJECT':
                    proof=self._retry_projects.require_in_transaction(tx,user_id=actor_id,
                        project_id=facts.project_id,operation='AUDIT_PROJECT_EXPORT')
                    if (type(proof) is not AuthorizedProjectAction or
                        (proof.user_id,proof.project_id,proof.operation,proof.project_role)!=
                        (actor_id,facts.project_id,'AUDIT_PROJECT_EXPORT','PROJECT_MANAGER')):raise JobReadError()
                source=self._retry_sources.read(tx,accepted=accepted,expected_version=facts.lock_version)
                if type(source) is not AuditUserRetrySource or source.accepted!=accepted:raise JobReadError()
                source.__post_init__()
                if source.failure.lock_version!=facts.lock_version:raise JobReadError()
                return JobOwnerProjection(facts.job_id,True)
            except ProjectAuthorizationError as exc:
                if exc.code in ('RESOURCE_NOT_FOUND','PROJECT_ARCHIVED'):return JobOwnerProjection(facts.job_id,False)
                raise JobReadError() from None
            except JobLeaseError as exc:
                if exc.code=='JOB_NOT_RETRYABLE':return JobOwnerProjection(facts.job_id,False)
                raise JobReadError() from None
            except JobReadError:raise
            except Exception:raise JobReadError() from None
        return JobOwnerProjection(facts.job_id,False)
