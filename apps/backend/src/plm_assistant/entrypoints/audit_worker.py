"""Explicit owned composition, no CLI, implicit credentials or resource ownership."""
from dataclasses import dataclass
from math import isfinite
from uuid import UUID
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from plm_assistant.modules.platform.infrastructure.worker_database import WorkerDatabaseRuntime
from plm_assistant.modules.platform.infrastructure.migration import MIGRATION_PACKAGE
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthority
from plm_assistant.modules.audit.application.worker_execution import AuditExportWorkerExecution
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.run_export_once import AuditExportRunOnce
from plm_assistant.modules.audit.application.execute_export import AuditExportExecutor
from plm_assistant.modules.audit.application.read_execution_facts import AuditExportExecutionReader
from plm_assistant.modules.audit.application.worker_termination import AuditExportWorkerTermination
from plm_assistant.modules.audit.application.verify_termination import AuditExportTerminationVerification
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.verify_cancel import AuditExportCancelVerification
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.audit.application.verify_retry import AuditExportRetryVerification
from plm_assistant.modules.audit.application.worker_exhaustion import AuditExportWorkerExhaustion
from plm_assistant.modules.audit.application.claim_export import AuditExportClaimAdmission
from plm_assistant.modules.audit.application.sweep_exhausted_export import AuditExportExhaustionSweep
from plm_assistant.modules.audit.application.worker_step import AuditExportWorkerStep
from plm_assistant.modules.audit.application.worker_loop import AuditExportWorkerLoop
from plm_assistant.modules.audit.infrastructure.export_submit_repository import SqlAlchemyAuditExportSubmitRepository
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.capture_repository import SqlAlchemyAuditCaptureRepository
from plm_assistant.modules.audit.infrastructure.render_plan_repository import SqlAlchemyAuditRenderPlans
from plm_assistant.modules.audit.infrastructure.render_source import SqlAlchemyAuditExportRenderSource
from plm_assistant.modules.audit.infrastructure.export_result_repository import SqlAlchemyAuditExportResults
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.infrastructure.export_cancel_proof import SqlAlchemyAuditExportCancelProof
from plm_assistant.modules.audit.infrastructure.export_failure_proof import SqlAlchemyAuditExportFailureProof
from plm_assistant.modules.audit.infrastructure.export_retry_proof import SqlAlchemyAuditExportRetryProof
from plm_assistant.modules.auth.infrastructure.current_user_access import SqlAlchemyCurrentUserAccess
from plm_assistant.modules.document.infrastructure.audit_export_metadata import SqlAlchemyAuditExportFileMetadata
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobQueue
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellation
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims,validate_claim_input
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCandidates
from plm_assistant.modules.jobs.application.lease_checkpoint import JobLeaseCheckpoint
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionRead
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.audit_export_enqueue_repository import SqlAlchemyAuditExportJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.audit_export_cancel_repository import SqlAlchemyAuditExportCancellationRepository
from plm_assistant.modules.jobs.infrastructure.audit_export_claim_repository import SqlAlchemyAuditExportClaimRepository
from plm_assistant.modules.jobs.infrastructure.audit_export_exhaustion_scan_repository import SqlAlchemyAuditExportExhaustionScanRepository


@dataclass(frozen=True,slots=True)
class AuditWorkerSettings:
    worker_ref: str
    lease_seconds: int=60
    heartbeat_seconds: float=10
    stop_timeout_seconds: float=5
    poll_seconds: float=1

    def __post_init__(self):
        validate_claim_input(self.worker_ref,self.lease_seconds)
        for value,minimum,maximum in ((self.heartbeat_seconds,.01,self.lease_seconds/3),(self.stop_timeout_seconds,0,30),(self.poll_seconds,.05,60)):
            if type(value) not in (int,float) or not minimum<=value<=maximum or not isfinite(value):raise ValueError('Bounded worker settings required')


def _schema_current(database):
    config=Config();config.set_main_option('script_location',str(MIGRATION_PACKAGE))
    expected=ScriptDirectory.from_config(config).get_current_head()
    if expected is None:return False
    with database.unit_of_work() as tx:
        return tx.session.execute(text('SELECT version_num FROM plm.alembic_version')).scalars().all()==[expected]


def create_audit_export_worker(*,database,projects,license_guard,system_actor,storage,settings,
                               maintenance_admission=None):
    if type(database) is not WorkerDatabaseRuntime or type(settings) is not AuditWorkerSettings:raise ValueError('Explicit worker runtime/settings required')
    settings.__post_init__()
    for obj,names in ((projects,('require_in_transaction',)),(license_guard,('require_valid',)),(system_actor,('assert_current',)),
                      (storage,('staging_sink','verify_staged','inspect','promote'))):
        if obj is None or any(not callable(getattr(obj,name,None)) for name in names):raise ValueError('Owned worker dependencies required')
    try:
        if database.is_ready() is not True or not _schema_current(database):raise ValueError()
        identity=system_actor.assert_current()
        if type(identity) is not UUID or not identity.int:raise ValueError()
    except Exception:raise RuntimeError('Audit worker unavailable; startup sources rejected') from None
    uow=database.unit_of_work;repo=SqlAlchemyAuditExportSubmitRepository();audit=AuditService(SqlAlchemyAuditRepository())
    queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository());leases=SqlAlchemyJobLeaseRepository()
    authority=AuditExportCurrentAuthority(users=SqlAlchemyCurrentUserAccess(),projects=projects,license_guard=license_guard)
    deps=dict(unit_of_work=uow,repository=repo,authority=authority,queue=queue,leases=JobLeaseCheckpoint(repository=leases),
        captures=SqlAlchemyAuditCaptureRepository(),plans=SqlAlchemyAuditRenderPlans(),source=SqlAlchemyAuditExportRenderSource(),storage=storage)
    worker=AuditExportWorkerExecution(files=SqlAlchemyAuditExportFileMetadata(),results=SqlAlchemyAuditExportResults(),
        completion=AuditExportJobCompletion(queue=queue,leases=leases),audit=audit,system_actor=system_actor,**deps)
    heartbeat=AuditExportWorkerHeartbeat(renewals=JobLeaseRenewal(repository=leases),**{k:deps[k] for k in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=AuditHeartbeatSupervisor(heartbeats=heartbeat,max_workers=1)
    fd=dict(unit_of_work=uow,repository=repo,queue=queue,failure=AuditExportJobFailure(queue=queue,leases=leases),audit=audit,system_actor=system_actor,supervisor=supervisor)
    cd=dict(unit_of_work=uow,repository=repo,cancellations=AuditExportCancellation(repository=SqlAlchemyAuditExportCancellationRepository()),
        sources=SqlAlchemyAuditExportCancelSources(),audit=audit,system_actor=system_actor,supervisor=supervisor)
    exhaustion=AuditExportWorkerExhaustion(failure_proofs=SqlAlchemyAuditExportFailureProof(),**fd)
    executor=AuditExportExecutor(runner=AuditExportRunOnce(worker=worker,supervisor=supervisor,lease_seconds=settings.lease_seconds,
        interval_seconds=settings.heartbeat_seconds,stop_timeout_seconds=settings.stop_timeout_seconds),
        reader=AuditExportExecutionReader(execution_facts=AuditExportExecutionRead(queue=queue,leases=leases),**cd),
        termination=AuditExportWorkerTermination(**fd),termination_verifier=AuditExportTerminationVerification(failure_proofs=SqlAlchemyAuditExportFailureProof(),**fd),
        cancellation=AuditExportWorkerCancel(**cd),cancellation_verifier=AuditExportCancelVerification(completion_proofs=SqlAlchemyAuditExportCancelProof(),**cd),
        retry=AuditExportWorkerRetry(authority=authority,**fd),retry_verifier=AuditExportRetryVerification(retry_proofs=SqlAlchemyAuditExportRetryProof(),authority=authority,**fd),
        exhaustion=exhaustion,supervisor=supervisor)
    admission=AuditExportClaimAdmission(unit_of_work=uow,repository=repo,claims=AuditExportClaims(repository=SqlAlchemyAuditExportClaimRepository()),queue=queue,system_actor=system_actor,supervisor=supervisor)
    sweep=AuditExportExhaustionSweep(unit_of_work=uow,candidates=AuditExportExhaustionCandidates(repository=SqlAlchemyAuditExportExhaustionScanRepository()),system_actor=system_actor,exhaustion=exhaustion)
    step=AuditExportWorkerStep(admission=admission,executor=executor,sweep=sweep,worker_ref=settings.worker_ref,lease_seconds=settings.lease_seconds)
    return AuditExportWorkerLoop(step=step,poll_seconds=settings.poll_seconds,
                                 maintenance_admission=maintenance_admission)
