"""Windows production composition for isolated probe and business AI chains."""

from __future__ import annotations

import sys
import uuid

from plm_assistant.entrypoints.ai_document_content_owner import AIDocumentContentOwner
from plm_assistant.entrypoints.ai_execution_policy import (
    create_deployment_ai_execution_registry,
)
from plm_assistant.entrypoints.ai_probe_policy import create_deployment_ai_probe_registry
from plm_assistant.entrypoints.ai_task_policy import create_deployment_ai_task_policies
from plm_assistant.entrypoints.windows_ai_provider_probe_worker import (
    create_windows_ai_provider_probe_loop,
)
from plm_assistant.entrypoints.windows_license_runtime import (
    create_windows_worker_license_services,
)
from plm_assistant.entrypoints.windows_secret_write import SECRET_MASTER_KEY_REF
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.ai.application.business_task_worker import (
    AIBusinessTaskOneShotWorker,
)
from plm_assistant.modules.ai.application.complete_provider_failure import (
    AITaskProviderFailureService,
)
from plm_assistant.modules.ai.application.complete_provider_success import (
    AITaskProviderSuccessService,
)
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContentOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.provider_combined_worker_loop import (
    AIProviderCombinedWorkerLoop,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AIProviderPreSendService,
)
from plm_assistant.modules.ai.application.provider_probe_worker import (
    ProviderProbeOneShotWorker,
    ProviderProbeWorkerCycle,
)
from plm_assistant.modules.ai.application.provider_response_parser import (
    AIProviderSuggestionParser,
)
from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.provider_test_preflight import (
    ProviderTestPreflightService,
)
from plm_assistant.modules.ai.application.publish_pre_begin_failure import (
    AITaskPreBeginFailurePublisher,
)
from plm_assistant.modules.ai.application.publish_provider_probe_failure import (
    ProviderProbeFailurePublisher,
)
from plm_assistant.modules.ai.application.publish_provider_probe_success import (
    ProviderProbeSuccessPublisher,
)
from plm_assistant.modules.ai.application.publish_suggestion_success import (
    AITaskSuggestionSuccessPublisher,
)
from plm_assistant.modules.ai.application.publish_task_failure import (
    AITaskFailurePublisher,
)
from plm_assistant.modules.ai.application.reconcile_expired_task import (
    ExpiredAITaskReconciler,
)
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeRunner
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantIssuer,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    AITaskInvocationBeginService,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    AITaskInvocationPrepareService,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_content_repository import (
    SqlAlchemyAIExecutionPromptTaskContentRepository,
)
from plm_assistant.modules.ai.infrastructure.expired_task_reconciliation_repository import (
    SqlAlchemyExpiredAITaskReconciliationRepository,
)
from plm_assistant.modules.ai.infrastructure.openai_compatible_adapter import (
    PinnedHttpsOpenAICompatibleAdapter,
)
from plm_assistant.modules.ai.infrastructure.pre_begin_failure_repository import (
    SqlAlchemyAITaskPreBeginFailureRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_execution_route_repository import (
    SqlAlchemyAIProviderExecutionRouteRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_probe_result_repository import (
    SqlAlchemyProviderProbeResultRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_probe_secret_audit import (
    ProviderProbeSecretAccessAudit,
)
from plm_assistant.modules.ai.infrastructure.provider_probe_transport import (
    PinnedHttpsProbeTransport,
)
from plm_assistant.modules.ai.infrastructure.provider_send_fence_repository import (
    SqlAlchemyAITaskProviderSendFenceRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_test_source import (
    SqlAlchemyAIProviderTestSource,
)
from plm_assistant.modules.ai.infrastructure.suggestion_success_repository import (
    SqlAlchemyAITaskSuggestionSuccessRepository,
)
from plm_assistant.modules.ai.infrastructure.task_execution_grant_repository import (
    SqlAlchemyAITaskExecutionGrantRepository,
)
from plm_assistant.modules.ai.infrastructure.task_failure_repository import (
    SqlAlchemyAITaskFailureRepository,
)
from plm_assistant.modules.ai.infrastructure.task_invocation_begin_repository import (
    SqlAlchemyAITaskInvocationBeginRepository,
)
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentService,
)
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.jobs.application.ai_provider_test_claim import (
    AIProviderTestClaims,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import (
    SqlAlchemyAIProviderTestClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.application.secret_access import SecretResolver
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import (
    SqlAlchemyAIProviderSecretProof,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.secret_store_reader import (
    SqlAlchemyEncryptedSecretStore,
)
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    read_database_url,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.platform.infrastructure.worker_database import (
    create_worker_database_runtime,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class WindowsAIProviderWorkerStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI Provider Worker unavailable")


class _IdleProbeWorker:
    def run_once(self, *, worker_ref: str) -> ProviderProbeWorkerCycle:
        JobLeaseService._validate_worker(worker_ref)
        return ProviderProbeWorkerCycle("IDLE")


def create_windows_ai_provider_loop(settings: BootstrapSettings):
    """Build the role without network calls; caller owns loop and database."""
    database = None
    try:
        if sys.platform != "win32" or type(settings) is not BootstrapSettings:
            raise WindowsAIProviderWorkerStartupError()
        has_probe = bool(settings.ai_probe_policies)
        has_tasks = bool(settings.ai_task_policies)
        has_execution = bool(settings.ai_execution_policies)
        if has_tasks != has_execution or not (has_probe or has_tasks):
            raise WindowsAIProviderWorkerStartupError()
        if has_probe and not has_tasks:
            return create_windows_ai_provider_probe_loop(settings)
        if any(item["context_policy_ref"] != "no-retrieval.v1"
               for item in settings.ai_task_policies):
            raise WindowsAIProviderWorkerStartupError()

        probe_policies = (
            create_deployment_ai_probe_registry(settings) if has_probe else None
        )
        _, purposes = create_deployment_ai_task_policies(settings)
        execution_policies = create_deployment_ai_execution_registry(settings)
        database = create_worker_database_runtime(
            read_database_url(), maintenance_admission=True,
        )
        admission = database.maintenance_admission
        if admission is None or not callable(getattr(admission, "admit", None)):
            raise WindowsAIProviderWorkerStartupError()
        guard = create_windows_worker_license_services(database, settings).guard
        actor = create_windows_system_actor()
        identity = actor.assert_current()
        if type(identity) is not uuid.UUID or not identity.int:
            raise WindowsAIProviderWorkerStartupError()
        key_provider = WindowsSecretKeyProvider()
        master_key = key_provider.resolve_key(SECRET_MASTER_KEY_REF)
        if type(master_key) is not bytes or len(master_key) != 32:
            raise WindowsAIProviderWorkerStartupError()
        del master_key
        audit = AuditService(SqlAlchemyAuditRepository())
        jobs = SqlAlchemyJobLeaseRepository()
        claims = AITaskExecutionClaims(
            repository=SqlAlchemyAITaskExecutionClaimRepository(),
        )
        egress = EgressAuthorizationOwner(
            repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
            purposes=purposes,
        )
        plans = AIExecutionContentPlanOwner(
            SqlAlchemyAIExecutionContentPlanRepository(),
        )
        grants = AITaskExecutionGrantIssuer(
            unit_of_work=database.unit_of_work, claims=claims,
            repository=SqlAlchemyAITaskExecutionGrantRepository(),
            egress_owner=egress, license_guard=guard,
        )
        projects = ProjectAuthorizationService(
            unit_of_work=database.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        document_owner = AIDocumentContentOwner(DocumentAIContentService(
            repository=SqlAlchemyDocumentAIContentRepository(),
            storage=LocalParseResultStorage(settings.data_root),
            projects=projects, license_guard=guard,
        ))
        preparer = AITaskInvocationPrepareService(
            unit_of_work=database.unit_of_work, grants=grants, plans=plans,
            prompts=AIExecutionPromptTaskContentOwner(
                SqlAlchemyAIExecutionPromptTaskContentRepository(),
            ),
            source_owners={"DOC-02": document_owner},
            envelopes=AIExecutionEnvelopeBuilder(
                renderer=StrictAIExecutionPromptRenderer(),
                context_policies=AIExecutionContextPolicyRegistry(
                    frozenset({"no-retrieval.v1"}),
                ),
                token_estimators=AIExecutionTokenEstimatorRegistry((
                    Utf8ByteUpperBoundTokenEstimator(),
                )),
            ),
        )
        beginner = AITaskInvocationBeginService(
            unit_of_work=database.unit_of_work, grants=grants,
            repository=SqlAlchemyAITaskInvocationBeginRepository(),
        )
        pre_send = AIProviderPreSendService(
            unit_of_work=database.unit_of_work, claims=claims,
            repository=SqlAlchemyAIProviderExecutionRouteRepository(),
            egress_owner=egress,
            secret_proof=SqlAlchemyAIProviderSecretProof(),
            policies=execution_policies, license_guard=guard,
        )
        task_secret_audit = AITaskProviderSecretAccessAudit(
            unit_of_work=database.unit_of_work, audit=audit,
            system_actor=actor,
        )
        sender = AITaskProviderSendService(
            pre_send=pre_send,
            secrets=SecretResolver(
                SqlAlchemyEncryptedSecretStore(database.unit_of_work),
                AesGcmSecretCrypto(key_provider, key_ref=SECRET_MASTER_KEY_REF),
                task_secret_audit,
            ),
            adapter=PinnedHttpsOpenAICompatibleAdapter(),
            access_audit_scope=task_secret_audit,
            send_fence=AITaskProviderSendFenceService(
                unit_of_work=database.unit_of_work, claims=claims,
                repository=SqlAlchemyAITaskProviderSendFenceRepository(),
            ),
        )
        failure_publisher = AITaskFailurePublisher(
            unit_of_work=database.unit_of_work,
            store=SqlAlchemyAITaskFailureRepository(), jobs=jobs,
            audit=audit, system_actor=actor,
        )
        task_worker = AIBusinessTaskOneShotWorker(
            leases=JobLeaseService(
                unit_of_work=database.unit_of_work, repository=jobs,
            ),
            preparer=preparer, beginner=beginner, sender=sender,
            success=AITaskProviderSuccessService(
                parser=AIProviderSuggestionParser(
                    schemas=default_ai_output_schema_registry(),
                ),
                publisher=AITaskSuggestionSuccessPublisher(
                    unit_of_work=database.unit_of_work, plans=plans,
                    store=SqlAlchemyAITaskSuggestionSuccessRepository(),
                    jobs=jobs, audit=audit, system_actor=actor,
                ),
                failures=failure_publisher,
            ),
            failure=AITaskProviderFailureService(
                publisher=failure_publisher,
            ),
            pre_begin_failure=AITaskPreBeginFailurePublisher(
                unit_of_work=database.unit_of_work,
                store=SqlAlchemyAITaskPreBeginFailureRepository(),
                jobs=jobs, audit=audit, system_actor=actor,
            ),
        )
        reconciler = ExpiredAITaskReconciler(
            unit_of_work=database.unit_of_work,
            store=SqlAlchemyExpiredAITaskReconciliationRepository(),
            audit=audit, system_actor=actor,
        )
        probe_worker = (
            _create_probe_worker(
                database=database, guard=guard, actor=actor, audit=audit,
                key_provider=key_provider, policies=probe_policies, jobs=jobs,
            ) if probe_policies is not None else _IdleProbeWorker()
        )
        loop = AIProviderCombinedWorkerLoop(
            probe_worker=probe_worker,
            probe_worker_ref="ai-probe-" + uuid.uuid4().hex,
            task_worker=task_worker,
            task_worker_ref="ai-task-" + uuid.uuid4().hex,
            reconciler=reconciler, maintenance_admission=admission,
        )
        return database, loop
    except Exception:
        if database is not None:
            try:
                database.dispose()
            except Exception:
                pass
        raise WindowsAIProviderWorkerStartupError() from None


def _create_probe_worker(
    *, database, guard, actor, audit, key_provider, policies, jobs,
) -> ProviderProbeOneShotWorker:
    secret_audit = ProviderProbeSecretAccessAudit(
        unit_of_work=database.unit_of_work, audit=audit, system_actor=actor,
    )
    claims = AIProviderTestClaims(
        unit_of_work=database.unit_of_work,
        repository=SqlAlchemyAIProviderTestClaimRepository(),
    )
    preflight = ProviderTestPreflightService(
        unit_of_work=database.unit_of_work, claims=claims,
        license_guard=guard, source=SqlAlchemyAIProviderTestSource(),
        secret_proof=SqlAlchemyAIProviderSecretProof(),
        probe_registry=policies,
    )
    runner = ProviderProbeRunner(
        preflight=preflight,
        secrets=SecretResolver(
            SqlAlchemyEncryptedSecretStore(database.unit_of_work),
            AesGcmSecretCrypto(key_provider, key_ref=SECRET_MASTER_KEY_REF),
            secret_audit,
        ),
        transport=PinnedHttpsProbeTransport(),
        access_audit_scope=secret_audit,
    )
    probe_audit = ProviderProbeAudit(system_actor=actor, audit=audit)
    results = SqlAlchemyProviderProbeResultRepository()
    return ProviderProbeOneShotWorker(
        claims=claims, runner=runner,
        success=ProviderProbeSuccessPublisher(
            unit_of_work=database.unit_of_work, preflight=preflight,
            store=results, jobs=jobs, audit=probe_audit,
        ),
        failure=ProviderProbeFailurePublisher(
            unit_of_work=database.unit_of_work, claims=claims,
            jobs=jobs, results=results, audit=probe_audit,
        ),
    )
