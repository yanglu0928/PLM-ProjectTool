from __future__ import annotations

import hashlib
import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.document.application.parse_attempt import (
    ParseAttemptError, ReconciledParseAttempt, StartedParseAttempt,
)
from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, ClosedJobAttempt
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseJobBinding, ParseJobRef, ParseJobRequest,
)
from plm_assistant.modules.parser.application.prepare_input import (
    ParserInputCommand, VerifiedParserInput,
)
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.start_retry_attempt import (
    StartRetryParseAttempt,
)


class _Tx:
    committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self) -> None:
        self.committed = True


class StartRetryParseAttemptTests(unittest.TestCase):
    def setUp(self) -> None:
        body = b"synthetic retry"
        self.request = ParseJobRequest(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
            "PROJECT", uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.job_id = uuid.uuid4()
        self.command = ParserInputCommand(self.job_id, 2, "parser-worker-2")
        version = ParserInputVersion(self.request.document_version_id,
            hashlib.sha256(body).digest(), len(body), "text/plain")
        plan = choose_parser_profile(version)
        self.prepared = VerifiedParserInput(plan, self.job_id, 2, 2, io.BytesIO(body))
        self.claim = ClaimedJob(self.job_id, "DOCUMENT_PARSE", self.request.scope,
            self.request.project_id,
            {"document_id": str(self.request.document_id),
             "document_version_id": str(self.request.document_version_id)},
            str(self.request.trace_id), 2, 2)
        self.binding = ParseJobBinding(self.request,
                                       ParseJobRef(self.job_id, uuid.uuid4()))
        committed = CommittedParseDocumentSource(self.request, uuid.uuid4(),
                                                 datetime.now(timezone.utc))
        self.source = DocumentParseInputSource(committed,
            "projects/" + self.request.project_id.hex + "/objects/aa/" +
            committed.file_object_id.hex, version.content_sha256,
            version.size_bytes, version.detected_mime)
        self.closed = (ClosedJobAttempt(1, 1, "EXPIRED",
                       datetime.now(timezone.utc), "LEASE_EXPIRED"),)
        self.started = StartedParseAttempt(uuid.uuid4(), self.job_id,
            version.document_version_id, plan.parser_profile, plan.parser_version,
            2, datetime.now(timezone.utc))
        self.reconciled = ReconciledParseAttempt(uuid.uuid4(), 1, "RUNNING", "FAILED")
        self.leases, self.queue, self.documents, self.attempts, self.audit = (
            Mock(), Mock(), Mock(), Mock(), Mock())
        self.leases.check_current.return_value = self.claim
        self.leases.closed_attempts_for_current.return_value = self.closed
        self.queue.peek_parse_for_job.return_value = self.binding
        self.documents.read_input.return_value = self.source
        self.attempts.start_retry.return_value = (self.started, (self.reconciled,))
        self.audit.append.return_value = uuid.uuid4()
        self.transactions: list[_Tx] = []

    def service(self) -> StartRetryParseAttempt:
        def uow():
            tx = _Tx()
            self.transactions.append(tx)
            return tx
        return StartRetryParseAttempt(unit_of_work=uow, leases=self.leases,
            queue=self.queue, documents=self.documents, attempts=self.attempts,
            audit=self.audit, system_actor_id=uuid.uuid4())

    def test_reconciles_prior_and_starts_current_in_one_transaction(self) -> None:
        result = self.service().start(self.command, self.prepared)
        self.assertEqual(result, self.started)
        self.assertTrue(self.transactions[-1].committed)
        self.assertEqual(self.attempts.start_retry.call_args.kwargs["closed"], self.closed)
        event = self.audit.append.call_args.args[1]
        self.assertEqual((event.before_state, event.after_state), ("RUNNING", "FAILED"))

    def test_audit_failure_or_changed_source_never_commits(self) -> None:
        self.audit.append.side_effect = RuntimeError("audit unavailable")
        with self.assertRaises(ParseAttemptError):
            self.service().start(self.command, self.prepared)
        self.assertFalse(self.transactions[-1].committed)
        self.audit.append.side_effect = None
        self.documents.read_input.return_value = DocumentParseInputSource(
            self.source.committed, self.source.storage_locator, b"x" * 32,
            self.source.size_bytes, self.source.detected_mime)
        with self.assertRaises(ParseAttemptError) as error:
            self.service().start(self.command, self.prepared)
        self.assertEqual(error.exception.code, "PARSER_INPUT_CHANGED")
        self.assertFalse(self.transactions[-1].committed)

    def test_first_generation_or_mismatched_proof_rejected(self) -> None:
        self.prepared.attempt_no = 1
        with self.assertRaises(ParseAttemptError):
            self.service().start(self.command, self.prepared)
        self.assertFalse(self.transactions)
        self.prepared.attempt_no = 2
        self.leases.closed_attempts_for_current.return_value = ()
        with self.assertRaises(ParseAttemptError):
            self.service().start(self.command, self.prepared)
        self.assertFalse(self.transactions[-1].committed)


if __name__ == "__main__":
    unittest.main()
