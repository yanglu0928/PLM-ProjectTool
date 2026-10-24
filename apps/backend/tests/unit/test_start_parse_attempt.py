from __future__ import annotations

import hashlib
import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.document.application.parse_attempt import (
    ParseAttemptError, StartedParseAttempt,
)
from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseJobBinding, ParseJobRef, ParseJobRequest,
)
from plm_assistant.modules.parser.application.prepare_input import (
    ParserInputCommand, VerifiedParserInput,
)
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.start_attempt import StartFirstParseAttempt


class _Tx:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self) -> None:
        self.committed = True


class StartParseAttemptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"synthetic parser input"
        self.request = ParseJobRequest(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
            "PROJECT", uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.job_id = uuid.uuid4()
        self.command = ParserInputCommand(self.job_id, 1, "parser-worker-1")
        source = ParserInputVersion(self.request.document_version_id,
            hashlib.sha256(self.content).digest(), len(self.content), "text/plain")
        plan = choose_parser_profile(source)
        self.prepared = VerifiedParserInput(plan, self.job_id, 1, 1,
                                            io.BytesIO(self.content))
        self.claim = ClaimedJob(self.job_id, "DOCUMENT_PARSE", self.request.scope,
            self.request.project_id,
            {"document_id": str(self.request.document_id),
             "document_version_id": str(self.request.document_version_id)},
            str(self.request.trace_id), 1, 1)
        self.binding = ParseJobBinding(self.request,
                                       ParseJobRef(self.job_id, uuid.uuid4()))
        committed = CommittedParseDocumentSource(self.request, uuid.uuid4(),
                                                 datetime.now(timezone.utc))
        self.source = DocumentParseInputSource(committed,
            "projects/" + self.request.project_id.hex + "/objects/aa/" +
            committed.file_object_id.hex, source.content_sha256,
            source.size_bytes, source.detected_mime)
        self.leases, self.queue, self.documents, self.attempts = (
            Mock(), Mock(), Mock(), Mock())
        self.leases.check_current.return_value = self.claim
        self.queue.peek_parse_for_job.return_value = self.binding
        self.documents.read_input.return_value = self.source
        self.started = StartedParseAttempt(uuid.uuid4(), self.job_id,
            source.document_version_id, plan.parser_profile, plan.parser_version,
            1, datetime.now(timezone.utc))
        self.attempts.start_first.return_value = self.started
        self.transactions: list[_Tx] = []

    def service(self) -> StartFirstParseAttempt:
        def uow():
            tx = _Tx()
            self.transactions.append(tx)
            return tx
        return StartFirstParseAttempt(unit_of_work=uow, leases=self.leases,
            queue=self.queue, documents=self.documents, attempts=self.attempts)

    def test_current_lease_queue_document_and_snapshot_start_first(self) -> None:
        result = self.service().start(self.command, self.prepared)
        self.assertEqual(result, self.started)
        self.assertTrue(self.transactions[-1].committed)
        called = self.attempts.start_first.call_args.kwargs
        self.assertEqual(called["job_id"], self.job_id)
        self.assertEqual(called["request"].content_sha256,
                         self.prepared.plan.source.content_sha256)

    def test_stale_lease_and_changed_source_never_commit(self) -> None:
        self.leases.check_current.side_effect = JobLeaseError("STALE_LEASE")
        with self.assertRaises(ParseAttemptError) as error:
            self.service().start(self.command, self.prepared)
        self.assertEqual(error.exception.code, "STALE_LEASE")
        self.assertFalse(self.transactions[-1].committed)
        self.leases.check_current.side_effect = None
        self.documents.read_input.return_value = DocumentParseInputSource(
            self.source.committed, self.source.storage_locator, b"x" * 32,
            self.source.size_bytes, self.source.detected_mime)
        with self.assertRaises(ParseAttemptError) as error:
            self.service().start(self.command, self.prepared)
        self.assertEqual(error.exception.code, "PARSER_INPUT_CHANGED")
        self.assertFalse(self.transactions[-1].committed)
        self.attempts.start_first.assert_not_called()

    def test_retry_or_closed_snapshot_not_started_here(self) -> None:
        self.prepared.attempt_no = 2
        with self.assertRaises(ParseAttemptError):
            self.service().start(self.command, self.prepared)
        self.assertFalse(self.transactions)
        self.prepared.attempt_no = 1
        self.prepared.close()
        with self.assertRaises(ParseAttemptError):
            self.service().start(self.command, self.prepared)


if __name__ == "__main__":
    unittest.main()
