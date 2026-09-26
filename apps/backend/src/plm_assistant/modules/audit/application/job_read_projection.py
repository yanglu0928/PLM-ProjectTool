"""Audit Owner proves original task bindings; metadata grants no content access."""
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts,JobOwnerProjection,JobReadError
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from .submit_export import AuditExportIntent,AcceptedAuditExport
from .export_result import AuditExportResult

class AuditJobReadProjection:
    def __init__(self,*,repository,queue,results):
        if any(v is None for v in (repository,queue,results)):raise ValueError('Actual Audit sources required')
        self._repo,self._queue,self._results=repository,queue,results
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
        return JobOwnerProjection(facts.job_id,False)  # Audit has no public user retry command yet.
