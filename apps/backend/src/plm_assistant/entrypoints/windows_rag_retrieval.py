"""Fail-closed Windows composition for the first local Retrieval strategy."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.routing import APIRouter

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.jobs.application.rag_retrieval_claim import (
    RAGRetrievalClaims,
)
from plm_assistant.modules.jobs.infrastructure.rag_retrieval_claim_repository import (
    SqlAlchemyRAGRetrievalClaimRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.rag.api.retrieval_cancel import (
    create_rag_retrieval_cancel_router,
)
from plm_assistant.modules.rag.api.retrieval_runs import create_rag_retrieval_router
from plm_assistant.modules.rag.application.create_retrieval import (
    RAGRetrievalCreateService,
)
from plm_assistant.modules.rag.application.fts_retrieval_merge import (
    FTSRetrievalMergePlanner,
)
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalQueryPreparationService,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidatePlanner,
)
from plm_assistant.modules.rag.application.retrieval_cancel import (
    RAGRetrievalCancelOwner,
    RAGRetrievalCancelReconciler,
)
from plm_assistant.modules.rag.application.retrieval_read import (
    RAGRetrievalReadService,
)
from plm_assistant.modules.rag.application.retrieval_terminal import (
    RAGRetrievalTerminalService,
)
from plm_assistant.modules.rag.application.retrieval_worker import (
    RAGRetrievalOneShotWorker,
)
from plm_assistant.modules.rag.infrastructure.project_fts_candidate_repository import (
    SqlAlchemyProjectFTSCandidateRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_cancel_repository import (
    SqlAlchemyRAGRetrievalCancellationRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_create_repository import (
    SqlAlchemyRAGRetrievalCreateRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_crypto import (
    AesGcmRetrievalQueryCrypto,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_preparation_repository import (
    SqlAlchemyRAGRetrievalQueryPreparationRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_read_repository import (
    SqlAlchemyRAGRetrievalReadRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_terminal_repository import (
    SqlAlchemyRAGRetrievalTerminalRepository,
)


RAG_RETRIEVAL_QUERY_KEY_REF = "rag-retrieval-query-v1"


class WindowsRAGRetrievalStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows RAG Retrieval unavailable")


@dataclass(frozen=True, slots=True)
class WindowsRAGRetrievalAPI:
    router: APIRouter
    cancel_router: APIRouter
    cancellation_owner: RAGRetrievalCancelOwner


@dataclass(frozen=True, slots=True)
class WindowsRAGRetrievalWorker:
    worker: RAGRetrievalOneShotWorker
    terminal_reconciler: RAGRetrievalTerminalService
    cancel_reconciler: RAGRetrievalCancelReconciler


def _cipher(*, resolver: object | None = None) -> AesGcmRetrievalQueryCrypto:
    source = resolver or WindowsSecretKeyProvider()
    try:
        key = source.resolve_key(RAG_RETRIEVAL_QUERY_KEY_REF)
        if type(key) is not bytes or len(key) != 32:
            raise WindowsRAGRetrievalStartupError()
        del key
        return AesGcmRetrievalQueryCrypto(
            source, key_ref=RAG_RETRIEVAL_QUERY_KEY_REF,
        )
    except Exception:
        raise WindowsRAGRetrievalStartupError() from None


def _valid_runtime(runtime: object) -> bool:
    return callable(getattr(runtime, "unit_of_work", None))


def _authorization(runtime: object) -> ProjectAuthorizationService:
    return ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )


def create_windows_rag_retrieval_api(
    runtime: object, *, sessions: SessionService,
    origins: LoginOriginPolicy, license_guard: object,
    key_resolver: object | None = None,
) -> WindowsRAGRetrievalAPI:
    """Build both frozen Retrieval paths around one cancellation Owner."""
    try:
        if (not _valid_runtime(runtime) or sessions is None
                or origins is None or license_guard is None):
            raise WindowsRAGRetrievalStartupError()
        cipher = _cipher(resolver=key_resolver)
        authorization = _authorization(runtime)
        audit = AuditService(SqlAlchemyAuditRepository())
        receipts = SqlAlchemyIdempotencyReceipts()
        cancellation = RAGRetrievalCancelOwner(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            authorization=authorization, license_guard=license_guard,
            repository=SqlAlchemyRAGRetrievalCancellationRepository(),
            receipts=receipts, audit=audit,
        )
        router = create_rag_retrieval_router(
            sessions=sessions,
            creates=RAGRetrievalCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(),
                license_guard=license_guard, authorization=authorization,
                cipher=cipher, repository=SqlAlchemyRAGRetrievalCreateRepository(),
                receipts=receipts, audit=audit,
            ),
            reads=RAGRetrievalReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectReadAccess(),
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemyRAGRetrievalReadRepository(),
            ),
            origins=origins,
        )
        return WindowsRAGRetrievalAPI(
            router,
            create_rag_retrieval_cancel_router(
                sessions=sessions, cancellations=cancellation, origins=origins,
            ),
            cancellation,
        )
    except WindowsRAGRetrievalStartupError:
        raise
    except Exception:
        raise WindowsRAGRetrievalStartupError() from None


def create_windows_rag_retrieval_worker(
    runtime: object, *, license_guard: object, system_actor: object,
    key_resolver: object | None = None,
) -> WindowsRAGRetrievalWorker:
    """Build a zero-network one-shot Retrieval worker and bounded reconcilers."""
    try:
        if (not _valid_runtime(runtime) or license_guard is None
                or system_actor is None):
            raise WindowsRAGRetrievalStartupError()
        cipher = _cipher(resolver=key_resolver)
        claims = RAGRetrievalClaims(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyRAGRetrievalClaimRepository(),
        )
        authorization = _authorization(runtime)
        audit = AuditService(SqlAlchemyAuditRepository())
        terminal = RAGRetrievalTerminalService(
            unit_of_work=runtime.unit_of_work, claims=claims,
            repository=SqlAlchemyRAGRetrievalTerminalRepository(),
            audit=audit, system_actor=system_actor,
        )
        cancel = RAGRetrievalCancelReconciler(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyRAGRetrievalCancellationRepository(),
            audit=audit, system_actor=system_actor,
        )
        worker = RAGRetrievalOneShotWorker(
            claims=claims,
            preparation=RAGRetrievalQueryPreparationService(
                unit_of_work=runtime.unit_of_work, claims=claims,
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemyRAGRetrievalQueryPreparationRepository(),
                cipher=cipher,
            ),
            candidates=ProjectFTSCandidatePlanner(
                SqlAlchemyProjectFTSCandidateRepository(),
            ),
            merge=FTSRetrievalMergePlanner(), terminal=terminal,
            cancellations=cancel,
        )
        return WindowsRAGRetrievalWorker(worker, terminal, cancel)
    except WindowsRAGRetrievalStartupError:
        raise
    except Exception:
        raise WindowsRAGRetrievalStartupError() from None
