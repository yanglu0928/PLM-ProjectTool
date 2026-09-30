from __future__ import annotations

import hashlib
import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.document.application.parse_publish import (
    PublishedParseResult, StoredParseResult,
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
from plm_assistant.modules.parser.application.publish_result import (
    ParserPublishError, PublishParserResult,
)
from plm_assistant.modules.parser.application.structured_result import ParsedResult


class _Tx:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self) -> None:
        self.events.append("commit")
        self.committed = True


class PublishParserResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[str] = []
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
        self.parsed = ParsedResult(source.document_version_id, source.content_sha256,
                                   plan.parser_profile, plan.parser_version, ())
        ref_id = uuid.uuid4()
        locator = (f"results/projects/{self.request.project_id.hex}/"
                   f"{ref_id.hex[:2]}/{ref_id.hex}.json")
        canonical = self.parsed.canonical_bytes()
        self.stored = StoredParseResult(ref_id, locator,
            hashlib.sha256(canonical).digest(), len(canonical))
        self.started = StartedParseAttempt(uuid.uuid4(), self.job_id,
            source.document_version_id, plan.parser_profile, plan.parser_version,
            1, datetime.now(timezone.utc))
        self.published = PublishedParseResult(self.started.parse_record_id,
            ref_id, datetime.now(timezone.utc))
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
        self.leases, self.queue, self.documents, self.storage, self.results, self.audit = (
            Mock(), Mock(), Mock(), Mock(), Mock(), Mock())
        self.leases.check_current.return_value = self.claim
        self.leases.finish.return_value = self.claim
        self.queue.peek_parse_for_job.return_value = self.binding
        self.documents.read_input.return_value = self.source
        self.storage.read_verified.return_value = canonical
        self.results.publish_success.return_value = self.published
        self.audit.append.return_value = uuid.uuid4()
        self.transactions: list[_Tx] = []

    def service(self) -> PublishParserResult:
        def uow():
            tx = _Tx(self.events)
            self.transactions.append(tx)
            return tx
        return PublishParserResult(unit_of_work=uow, leases=self.leases,
            queue=self.queue, documents=self.documents, storage=self.storage,
            results=self.results, audit=self.audit, system_actor_id=uuid.uuid4())

    def publish(self):
        return self.service().publish(command=self.command, prepared=self.prepared,
            started=self.started, parsed=self.parsed, stored=self.stored)

    def test_verified_file_current_source_audit_then_job_finish(self) -> None:
        self.assertEqual(self.publish(), self.published)
        self.assertTrue(self.transactions[-1].committed)
        self.storage.read_verified.assert_called_once()
        self.results.publish_success.assert_called_once()
        self.audit.append.assert_called_once()
        self.leases.finish.assert_called_once()
        self.assertEqual(self.events, ["commit"])

    def test_tamper_stale_final_lease_and_audit_failure_never_commit(self) -> None:
        self.storage.read_verified.return_value = b"tampered"
        with self.assertRaises(ParserPublishError) as error:
            self.publish()
        self.assertEqual(error.exception.code, "PARSER_RESULT_MISMATCH")
        self.assertFalse(self.transactions)
        self.storage.read_verified.return_value = self.parsed.canonical_bytes()
        self.leases.finish.side_effect = JobLeaseError("STALE_LEASE")
        with self.assertRaises(ParserPublishError) as error:
            self.publish()
        self.assertEqual(error.exception.code, "STALE_LEASE")
        self.assertFalse(self.transactions[-1].committed)
        self.leases.finish.side_effect = None
        self.audit.append.side_effect = RuntimeError("audit unavailable")
        with self.assertRaises(ParserPublishError):
            self.publish()
        self.assertFalse(self.transactions[-1].committed)

    def test_changed_document_source_and_mismatched_result_rejected(self) -> None:
        wrong = ParsedResult(uuid.uuid4(), self.parsed.source_sha256,
            self.parsed.parser_profile, self.parsed.parser_version, ())
        with self.assertRaises(ParserPublishError):
            self.service().publish(command=self.command, prepared=self.prepared,
                started=self.started, parsed=wrong, stored=self.stored)
        self.assertFalse(self.transactions)
        self.documents.read_input.return_value = DocumentParseInputSource(
            self.source.committed, self.source.storage_locator, b"x" * 32,
            self.source.size_bytes, self.source.detected_mime)
        with self.assertRaises(ParserPublishError) as error:
            self.publish()
        self.assertEqual(error.exception.code, "PARSER_INPUT_CHANGED")
        self.assertFalse(self.transactions[-1].committed)


if __name__ == "__main__":
    unittest.main()
