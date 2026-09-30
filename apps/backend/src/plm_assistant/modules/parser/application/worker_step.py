"""One fenced Parser Job success step; failure/cancel recovery is separate work."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from re import fullmatch
from threading import Event, Lock, Thread
from typing import Callable, Protocol

from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_publish import (
    PublishedParseResult, StoredParseResult,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob

from .fail_attempt import ParserFailureOutcome, classify_parser_failure
from .extract_ocr import extract_ocr
from .extract_office import extract_office
from .extract_pdf_text import extract_pdf_text
from .extract_textual import extract_textual
from .prepare_input import ParserInputCommand, VerifiedParserInput
from .structured_result import ParsedResult


class ParserWorkerError(RuntimeError):
    def __init__(self, code: str = "PARSER_WORKER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParserWorkerStepOutcome:
    kind: str
    published: PublishedParseResult | None = None
    failed: ParserFailureOutcome | None = None

    def __post_init__(self) -> None:
        if (self.kind not in {"IDLE", "STOPPED", "PUBLISHED", "FAILED"}
                or (self.kind == "PUBLISHED") != (type(self.published) is PublishedParseResult)
                or (self.kind == "FAILED") != (type(self.failed) is ParserFailureOutcome)):
            raise ParserWorkerError()
        if self.published is not None:
            self.published.__post_init__()
        if self.failed is not None:
            self.failed.__post_init__()


class LeasePort(Protocol):
    def claim_next_parse(self, *, worker_ref: str, lease_seconds: int
                         ) -> ClaimedJob | None: ...
    def heartbeat(self, *, job_id: uuid.UUID, fencing_token: int,
                  worker_ref: str, lease_seconds: int) -> None: ...


class PreparePort(Protocol):
    def prepare(self, command: ParserInputCommand) -> VerifiedParserInput: ...


class StartPort(Protocol):
    def start(self, command: ParserInputCommand,
              prepared: VerifiedParserInput) -> StartedParseAttempt: ...


class StoragePort(Protocol):
    def write_once(self, *, scope: str, project_id: uuid.UUID | None,
                   result_ref_id: uuid.UUID, content: bytes) -> StoredParseResult: ...


class PublishPort(Protocol):
    def publish(self, *, command: ParserInputCommand,
                prepared: VerifiedParserInput, started: StartedParseAttempt,
                parsed: ParsedResult, stored: StoredParseResult
                ) -> PublishedParseResult: ...


class FailurePort(Protocol):
    def fail(self, *, command: ParserInputCommand,
             started: StartedParseAttempt | None, error_code: str,
             retryable: bool, delay_seconds: int) -> ParserFailureOutcome: ...


def extract_by_profile(prepared: VerifiedParserInput, *, ocr_engine: object | None
                       ) -> ParsedResult:
    """Use every verified profile's real extractor; OCR is explicit and offline."""
    if type(prepared) is not VerifiedParserInput:
        raise ParserWorkerError("PARSER_INPUT_INVALID")
    profile = prepared.plan.parser_profile
    if profile in ("PLAIN_TEXT", "CSV"):
        return extract_textual(prepared)
    if profile in ("DOCX", "PPTX", "XLSX"):
        return extract_office(prepared)
    if profile == "PDF_TEXT_THEN_OCR":
        return (extract_pdf_text(prepared) if ocr_engine is None
                else extract_ocr(prepared, ocr_engine))
    if profile == "IMAGE_OCR":
        if ocr_engine is None:
            raise ParserWorkerError("PARSER_OCR_ENGINE_REQUIRED")
        return extract_ocr(prepared, ocr_engine)
    raise ParserWorkerError("PARSER_FORMAT_UNSUPPORTED")


class _LeaseHeartbeats:
    def __init__(self, leases: LeasePort, command: ParserInputCommand,
                 lease_seconds: int, interval_seconds: float) -> None:
        self._leases, self._command = leases, command
        self._lease_seconds, self._interval_seconds = lease_seconds, interval_seconds
        self._stop = Event()
        self._failed = Event()
        self._thread = Thread(target=self._run, name="parser-lease-heartbeat",
                              daemon=True)
        self._started = False

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self._leases.heartbeat(job_id=self._command.job_id,
                    fencing_token=self._command.fencing_token,
                    worker_ref=self._command.worker_ref,
                    lease_seconds=self._lease_seconds)
            except Exception:
                self._failed.set()
                self._stop.set()
                return

    def check(self) -> None:
        if self._failed.is_set():
            raise ParserWorkerError("PARSER_HEARTBEAT_UNAVAILABLE")

    def close(self) -> None:
        self._stop.set()
        if self._started:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise ParserWorkerError("PARSER_HEARTBEAT_UNAVAILABLE")
        self.check()


class ParserWorkerStep:
    def __init__(self, *, leases: LeasePort, preparer: PreparePort,
                 first: StartPort, retry: StartPort, storage: StoragePort,
                 publisher: PublishPort, failure: FailurePort, worker_ref: str,
                 lease_seconds: int = 60, heartbeat_interval_seconds: float = 10,
                 ocr_engine: object | None = None,
                 extractor: Callable[[VerifiedParserInput], ParsedResult] | None = None) -> None:
        if any(value is None for value in (leases, preparer, first, retry,
                                            storage, publisher, failure)):
            raise ValueError("Parser Worker dependencies required")
        if (type(worker_ref) is not str
                or not fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", worker_ref)
                or type(lease_seconds) is not int or not 6 <= lease_seconds <= 3600
                or type(heartbeat_interval_seconds) not in (int, float)
                or not 0 < heartbeat_interval_seconds <= lease_seconds / 3):
            raise ValueError("safe Parser Worker lease settings required")
        self._leases, self._preparer = leases, preparer
        self._first, self._retry = first, retry
        self._storage, self._publisher = storage, publisher
        self._failure = failure
        self._worker_ref, self._lease_seconds = worker_ref, lease_seconds
        self._heartbeat_interval = heartbeat_interval_seconds
        self._extractor = extractor or (
            lambda prepared: extract_by_profile(prepared, ocr_engine=ocr_engine))
        self._stop = Event()
        self._lock = Lock()
        self._poisoned = False

    def request_stop(self) -> None:
        self._stop.set()

    def step(self) -> ParserWorkerStepOutcome:
        if not self._lock.acquire(blocking=False):
            raise ParserWorkerError("PARSER_WORKER_BUSY")
        try:
            if self._stop.is_set():
                return ParserWorkerStepOutcome("STOPPED")
            if self._poisoned:
                raise ParserWorkerError("PARSER_WORKER_STOPPED")
            try:
                claim = self._leases.claim_next_parse(
                    worker_ref=self._worker_ref, lease_seconds=self._lease_seconds)
                if claim is None:
                    return ParserWorkerStepOutcome("IDLE")
                if (type(claim) is not ClaimedJob
                        or claim.job_type != "DOCUMENT_PARSE"
                        or claim.attempt_no not in (1, 2, 3)):
                    raise ParserWorkerError()
                command = ParserInputCommand(claim.job_id, claim.fencing_token,
                                             self._worker_ref)
                heartbeats = _LeaseHeartbeats(self._leases, command,
                    self._lease_seconds, self._heartbeat_interval)
                heartbeats.start()
                started = None
                stage = "PREPARE"
                try:
                    with self._preparer.prepare(command) as prepared:
                        heartbeats.check()
                        if (type(prepared) is not VerifiedParserInput
                                or (prepared.job_id, prepared.fencing_token,
                                    prepared.attempt_no)
                                != (claim.job_id, claim.fencing_token, claim.attempt_no)):
                            raise ParserWorkerError("PARSER_INPUT_CHANGED")
                        starter = self._first if claim.attempt_no == 1 else self._retry
                        stage = "START"
                        started = starter.start(command, prepared)
                        heartbeats.check()
                        stage = "EXTRACT"
                        parsed = self._extractor(prepared)
                        if type(parsed) is not ParsedResult:
                            raise ParserWorkerError("PARSER_RESULT_INVALID")
                        heartbeats.check()
                        stage = "STORE"
                        stored = self._storage.write_once(scope=claim.scope,
                            project_id=claim.project_id, result_ref_id=uuid.uuid4(),
                            content=parsed.canonical_bytes())
                        heartbeats.close()
                        # A short final renewal bridges file fsync and fenced DB publication.
                        stage = "PUBLISH"
                        self._leases.heartbeat(job_id=claim.job_id,
                            fencing_token=claim.fencing_token, worker_ref=self._worker_ref,
                            lease_seconds=self._lease_seconds)
                        published = self._publisher.publish(command=command,
                            prepared=prepared, started=started, parsed=parsed,
                            stored=stored)
                        return ParserWorkerStepOutcome("PUBLISHED", published)
                except Exception as error:
                    # Never reinterpret a potentially committed publication, an
                    # uncertain Start transaction, or a lost lease as failure.
                    if stage in {"START", "PUBLISH"} or heartbeats._failed.is_set():
                        raise
                    heartbeats.close()
                    code, retryable, delay = classify_parser_failure(
                        error, attempt_no=claim.attempt_no)
                    self._leases.heartbeat(job_id=claim.job_id,
                        fencing_token=claim.fencing_token,
                        worker_ref=self._worker_ref,
                        lease_seconds=self._lease_seconds)
                    failed = self._failure.fail(command=command, started=started,
                        error_code=code, retryable=retryable,
                        delay_seconds=delay)
                    return ParserWorkerStepOutcome("FAILED", failed=failed)
                finally:
                    heartbeats.close()
            except ParserWorkerError:
                self._poisoned = True
                raise
            except Exception:
                self._poisoned = True
                raise ParserWorkerError() from None
        finally:
            self._lock.release()
