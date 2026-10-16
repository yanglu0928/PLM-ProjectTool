"""Unpublished Windows Provider Test one-shot Worker composition."""

from __future__ import annotations

import sys
import uuid

from plm_assistant.entrypoints.ai_probe_policy import create_deployment_ai_probe_registry
from plm_assistant.entrypoints.windows_license_runtime import create_windows_worker_license_services
from plm_assistant.entrypoints.windows_secret_write import SECRET_MASTER_KEY_REF
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.provider_probe_worker import ProviderProbeOneShotWorker
from plm_assistant.modules.ai.application.provider_probe_worker_loop import ProviderProbeWorkerLoop
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightService
from plm_assistant.modules.ai.application.publish_provider_probe_failure import ProviderProbeFailurePublisher
from plm_assistant.modules.ai.application.publish_provider_probe_success import ProviderProbeSuccessPublisher
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeRunner
from plm_assistant.modules.ai.infrastructure.provider_probe_result_repository import SqlAlchemyProviderProbeResultRepository
from plm_assistant.modules.ai.infrastructure.provider_probe_secret_audit import ProviderProbeSecretAccessAudit
from plm_assistant.modules.ai.infrastructure.provider_probe_transport import PinnedHttpsProbeTransport
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaims
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import SqlAlchemyAIProviderTestClaimRepository
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.platform.application.secret_access import SecretResolver
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime


class WindowsAIProviderProbeWorkerStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI Provider probe Worker unavailable")


def create_windows_ai_provider_probe_worker(settings: BootstrapSettings):
    """Build but do not run/register a Worker; validate the Vault master key only."""
    if sys.platform != "win32" or type(settings) is not BootstrapSettings:
        raise WindowsAIProviderProbeWorkerStartupError()
    database = None
    try:
        policies = create_deployment_ai_probe_registry(settings)
        database = create_worker_database_runtime(read_database_url(),
                                                  maintenance_admission=True)
        if database.maintenance_admission is None:
            raise WindowsAIProviderProbeWorkerStartupError()
        guard = create_windows_worker_license_services(database, settings).guard
        actor = create_windows_system_actor()
        identity = actor.assert_current()
        if type(identity) is not uuid.UUID or not identity.int:
            raise WindowsAIProviderProbeWorkerStartupError()
        key_provider = WindowsSecretKeyProvider()
        master_key = key_provider.resolve_key(SECRET_MASTER_KEY_REF)
        if type(master_key) is not bytes or len(master_key) != 32:
            raise WindowsAIProviderProbeWorkerStartupError()
        del master_key
        audit = AuditService(SqlAlchemyAuditRepository())
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
            secret_proof=SqlAlchemyAIProviderSecretProof(), probe_registry=policies,
        )
        runner = ProviderProbeRunner(
            preflight=preflight,
            secrets=SecretResolver(
                SqlAlchemyEncryptedSecretStore(database.unit_of_work),
                AesGcmSecretCrypto(key_provider, key_ref=SECRET_MASTER_KEY_REF),
                secret_audit,
            ),
            transport=PinnedHttpsProbeTransport(), access_audit_scope=secret_audit,
        )
        probe_audit = ProviderProbeAudit(system_actor=actor, audit=audit)
        results = SqlAlchemyProviderProbeResultRepository()
        jobs = SqlAlchemyJobLeaseRepository()
        worker = ProviderProbeOneShotWorker(
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
        return database, worker
    except Exception:
        if database is not None:
            try:
                database.dispose()
            except Exception:
                pass
        raise WindowsAIProviderProbeWorkerStartupError() from None


def create_windows_ai_provider_probe_loop(settings: BootstrapSettings):
    """Compose a dormant, maintenance-admitted loop; caller owns lifecycle."""
    database = None
    try:
        database, worker = create_windows_ai_provider_probe_worker(settings)
        admission = database.maintenance_admission
        if admission is None or not callable(getattr(admission, "admit", None)):
            raise WindowsAIProviderProbeWorkerStartupError()
        loop = ProviderProbeWorkerLoop(
            worker=worker, worker_ref="ai-probe-" + uuid.uuid4().hex,
            maintenance_admission=admission,
        )
        return database, loop
    except Exception:
        if database is not None:
            try:
                database.dispose()
            except Exception:
                pass
        raise WindowsAIProviderProbeWorkerStartupError() from None
