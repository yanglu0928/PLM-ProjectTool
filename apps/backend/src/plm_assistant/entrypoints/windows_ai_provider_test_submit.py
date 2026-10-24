"""Closed-by-default Windows Provider Test submission composition."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.entrypoints.ai_probe_policy import create_deployment_ai_probe_registry
from plm_assistant.modules.ai.api.submit_provider_test import create_ai_provider_test_router
from plm_assistant.modules.ai.application.submit_provider_test import AIProviderTestSubmitService
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobQueue
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import SqlAlchemyAIProviderTestJobQueueRepository
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts


class WindowsAIProviderTestSubmitStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI Provider Test submission unavailable")


def create_windows_ai_provider_test_submit_router(
    *, runtime: object, settings: BootstrapSettings, sessions: SessionService,
    origins: LoginOriginPolicy, license_guard: object, audit: AuditService,
) -> APIRouter:
    """Build one trusted submit path; caller must not publish before Worker readiness."""
    try:
        if (type(settings) is not BootstrapSettings
                or any(item is None for item in (runtime, sessions, origins,
                                                  license_guard, audit))):
            raise WindowsAIProviderTestSubmitStartupError()
        registry = create_deployment_ai_probe_registry(settings)
        service = AIProviderTestSubmitService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyLicenseImportAccess(), license_guard=license_guard,
            source=SqlAlchemyAIProviderTestSource(),
            secret_proof=SqlAlchemyAIProviderSecretProof(),
            probe_registry=registry,
            queue=AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository()),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_ai_provider_test_router(
            sessions=sessions, providers=service, origins=origins,
        )
    except Exception:
        raise WindowsAIProviderTestSubmitStartupError() from None
