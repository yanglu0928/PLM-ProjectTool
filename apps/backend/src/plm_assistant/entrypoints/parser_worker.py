"""Explicit Parser Worker composition; process sources are supplied by the caller."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from re import fullmatch
from uuid import UUID, uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.parse_cancel_sources import SqlAlchemyParseCancelAuditSources
from plm_assistant.modules.auth.infrastructure.current_user_access import SqlAlchemyCurrentUserAccess
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_attempt_repository import SqlAlchemyParseAttemptRepository
from plm_assistant.modules.document.infrastructure.parse_cancel_repository import SqlAlchemyParseCancelRepository
from plm_assistant.modules.document.infrastructure.parse_failure_repository import SqlAlchemyParseFailureRepository
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.document.infrastructure.parse_publish_repository import SqlAlchemyParsePublishRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.application.parse_cancel_scan import ExpiredParserCancelCandidates
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.parse_cancel_scan_repository import SqlAlchemyParserCancelScanRepository
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.parser.application.authorized_source import AuthorizedParserInputSource
from plm_assistant.modules.parser.application.cancel_attempt import AcknowledgeParserCancel
from plm_assistant.modules.parser.application.current_authority import ParserCurrentAuthority
from plm_assistant.modules.parser.application.fail_attempt import FailParserAttempt
from plm_assistant.modules.parser.application.prepare_input import PrepareParserInput
from plm_assistant.modules.parser.application.publish_result import PublishParserResult
from plm_assistant.modules.parser.application.recover_expired_cancel import RecoverExpiredParserCancel
from plm_assistant.modules.parser.application.start_attempt import StartFirstParseAttempt
from plm_assistant.modules.parser.application.start_retry_attempt import StartRetryParseAttempt
from plm_assistant.modules.parser.application.sweep_expired_cancel import ParserExpiredCancelSweep
from plm_assistant.modules.parser.application.worker_loop import ParserWorkerLoop
from plm_assistant.modules.parser.application.worker_step import ParserWorkerStep
from plm_assistant.modules.parser.infrastructure.paddle_ocr import OfflinePaddleOcr
from plm_assistant.modules.platform.infrastructure.migration import MIGRATION_PACKAGE
from plm_assistant.modules.platform.infrastructure.worker_database import WorkerDatabaseRuntime


@dataclass(frozen=True, slots=True)
class ParserWorkerSettings:
    worker_ref: str
    lease_seconds: int = 60
    heartbeat_seconds: float = 10
    poll_seconds: float = 1

    def __post_init__(self) -> None:
        if (type(self.worker_ref) is not str
                or not fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.worker_ref)
                or type(self.lease_seconds) is not int
                or not 6 <= self.lease_seconds <= 3600
                or type(self.heartbeat_seconds) not in (int, float)
                or not isfinite(self.heartbeat_seconds)
                or not 0 < self.heartbeat_seconds <= self.lease_seconds / 3
                or type(self.poll_seconds) not in (int, float)
                or not isfinite(self.poll_seconds)
                or not .05 <= self.poll_seconds <= 60):
            raise ValueError("Bounded Parser Worker settings required")


def _current_schema(database: WorkerDatabaseRuntime) -> bool:
    config = Config()
    config.set_main_option("script_location", str(MIGRATION_PACKAGE))
    expected = ScriptDirectory.from_config(config).get_current_head()
    if expected is None:
        return False
    with database.unit_of_work() as tx:
        return tx.session.execute(text("SELECT version_num FROM plm.alembic_version")).scalars().all() == [expected]


def create_parser_worker(*, database: WorkerDatabaseRuntime, projects,
                         license_guard, system_actor, data_root: Path,
                         ocr_engine, settings: ParserWorkerSettings,
                         maintenance_admission=None) -> ParserWorkerLoop:
    """Own no supplied resource; reject ambiguous/partial startup before work."""
    if (type(database) is not WorkerDatabaseRuntime
            or type(settings) is not ParserWorkerSettings
            or not isinstance(data_root, Path) or not data_root.is_absolute()
            or projects is None or not callable(getattr(projects, "require_in_transaction", None))
            or license_guard is None or not callable(getattr(license_guard, "require_valid", None))
            or system_actor is None or not callable(getattr(system_actor, "assert_current", None))
            or type(ocr_engine) is not OfflinePaddleOcr
            or type(getattr(ocr_engine, "model_fingerprint", None)) is not str
            or len(ocr_engine.model_fingerprint) != 64
            or any(char not in "0123456789abcdef"
                   for char in ocr_engine.model_fingerprint)):
        raise ValueError("Explicit Parser Worker dependencies required")
    settings.__post_init__()
    try:
        if database.is_ready() is not True or not _current_schema(database):
            raise ValueError()
        identity = system_actor.assert_current()
        if type(identity) is not UUID or identity.int == 0:
            raise ValueError()
        license_guard.require_valid(trace_id=uuid4())
        source_storage = LocalFileStorage(data_root)
        result_storage = LocalParseResultStorage(data_root)
    except Exception:
        raise RuntimeError("Parser worker unavailable; startup sources rejected") from None

    uow = database.unit_of_work
    lease_repo = SqlAlchemyJobLeaseRepository()
    queue = ParseJobQueue(SqlAlchemyParseJobQueueRepository())
    source = DocumentParseSourceReader(repository=SqlAlchemyDocumentParseSources(),
        audit_sources=UploadCommitAuditSources(repository=SqlAlchemyUploadCommitAuditSources()))
    documents = AuthorizedParserInputSource(source=source,
        authority=ParserCurrentAuthority(users=SqlAlchemyCurrentUserAccess(),
            projects=projects, license_guard=license_guard))
    audit = AuditService(SqlAlchemyAuditRepository())
    common = dict(unit_of_work=uow, leases=lease_repo, queue=queue, documents=documents)
    worker = ParserWorkerStep(
        leases=JobLeaseService(unit_of_work=uow, repository=lease_repo),
        preparer=PrepareParserInput(**common, storage=source_storage, audit=audit,
            system_actor=system_actor),
        first=StartFirstParseAttempt(**common,
            attempts=SqlAlchemyParseAttemptRepository()),
        retry=StartRetryParseAttempt(**common,
            attempts=SqlAlchemyParseAttemptRepository(), audit=audit,
            system_actor=system_actor),
        storage=result_storage,
        publisher=PublishParserResult(**common, storage=result_storage,
            results=SqlAlchemyParsePublishRepository(), audit=audit,
            system_actor=system_actor),
        failure=FailParserAttempt(**{**common, "documents": SqlAlchemyParseFailureRepository()},
            audit=audit, system_actor=system_actor),
        cancellation=AcknowledgeParserCancel(
            **{**common, "documents": SqlAlchemyParseCancelRepository()},
            audit=audit, system_actor=system_actor),
        worker_ref=settings.worker_ref, lease_seconds=settings.lease_seconds,
        heartbeat_interval_seconds=settings.heartbeat_seconds,
        ocr_engine=ocr_engine)
    recovery=RecoverExpiredParserCancel(unit_of_work=uow, leases=lease_repo,
        queue=queue, sources=source,
        cancellations=SqlAlchemyParseCancelAuditSources(),
        documents=SqlAlchemyParseCancelRepository(), audit=audit,
        system_actor=system_actor)
    sweep=ParserExpiredCancelSweep(unit_of_work=uow,
        candidates=ExpiredParserCancelCandidates(repository=SqlAlchemyParserCancelScanRepository()),
        recovery=recovery, system_actor=system_actor)
    return ParserWorkerLoop(step=worker, sweep=sweep,
        poll_seconds=settings.poll_seconds,
        maintenance_admission=maintenance_admission)
