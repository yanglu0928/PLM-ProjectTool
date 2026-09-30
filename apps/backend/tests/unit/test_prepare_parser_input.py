from __future__ import annotations

import hashlib
import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.document.application.prepare_download import DownloadStorageError
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseJobBinding, ParseJobRef, ParseJobRequest,
)
from plm_assistant.modules.parser.application.prepare_input import (
    ParserInputCommand, ParserInputError, PrepareParserInput,
)


class _Tx:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self) -> None:
        self.committed = True


class _Storage:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.stream = None
        self.calls = 0

    def open_verified_snapshot(self, locator, *, expected_sha256, expected_size, max_bytes):
        self.calls += 1
        if (not locator.startswith("projects/")
                or expected_sha256 != hashlib.sha256(self.content).digest()
                or expected_size != len(self.content) or len(self.content) > max_bytes):
            raise DownloadStorageError()
        self.stream = io.BytesIO(self.content)
        return self.stream


class PrepareParserInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"%PDF-1.7\nsynthetic parser source\n%%EOF\n"
        self.request = ParseJobRequest(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
            "PROJECT", uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.job_id = uuid.uuid4()
        self.command = ParserInputCommand(self.job_id, 1, "parser-worker-1")
        self.binding = ParseJobBinding(self.request, ParseJobRef(self.job_id, uuid.uuid4()))
        self.claim = ClaimedJob(self.job_id, "DOCUMENT_PARSE", "PROJECT",
            self.request.project_id,
            {"document_id": str(self.request.document_id),
             "document_version_id": str(self.request.document_version_id)},
            str(self.request.trace_id), 1, 1)
        committed = CommittedParseDocumentSource(self.request, uuid.uuid4(),
            datetime.now(timezone.utc))
        self.source = DocumentParseInputSource(committed,
            "projects/" + self.request.project_id.hex + "/objects/aa/" + committed.file_object_id.hex,
            hashlib.sha256(self.content).digest(), len(self.content), "application/pdf")
        self.leases, self.queue, self.documents, self.audit = Mock(), Mock(), Mock(), Mock()
        self.leases.check_current.return_value = self.claim
        self.queue.peek_parse_for_job.return_value = self.binding
        self.documents.read_input.return_value = self.source
        self.storage = _Storage(self.content)
        self.transactions: list[_Tx] = []
        self.system_actor_id = uuid.uuid4()

    def _service(self) -> PrepareParserInput:
        def uow():
            value = _Tx()
            self.transactions.append(value)
            return value
        return PrepareParserInput(unit_of_work=uow, leases=self.leases,
            queue=self.queue, documents=self.documents, storage=self.storage,
            audit=self.audit, system_actor_id=self.system_actor_id)

    def test_current_job_and_document_around_verified_snapshot(self) -> None:
        with self._service().prepare(self.command) as prepared:
            self.assertEqual(prepared.stream.read(), self.content)
            self.assertEqual(prepared.plan.source.document_version_id, self.request.document_version_id)
            self.assertEqual(prepared.plan.parser_profile, "PDF_TEXT_THEN_OCR")
            self.assertEqual((prepared.job_id, prepared.fencing_token, prepared.attempt_no),
                             (self.job_id, 1, 1))
            self.assertNotIn("projects/", repr(prepared))
        self.assertTrue(self.storage.stream.closed)
        self.assertEqual(self.leases.check_current.call_count, 2)
        self.assertEqual(self.queue.peek_parse_for_job.call_count, 2)
        self.assertEqual(self.documents.read_input.call_count, 2)
        self.assertEqual(len(self.transactions), 2)
        self.audit.append.assert_not_called()

    def test_stale_lease_blocks_before_storage_and_after_copy(self) -> None:
        self.leases.check_current.side_effect = JobLeaseError("STALE_LEASE")
        with self.assertRaises(ParserInputError) as error:
            self._service().prepare(self.command)
        self.assertEqual(error.exception.code, "STALE_LEASE")
        self.assertEqual(self.storage.calls, 0)
        self.leases.check_current.side_effect = [self.claim, JobLeaseError("STALE_LEASE")]
        with self.assertRaises(ParserInputError) as error:
            self._service().prepare(self.command)
        self.assertEqual(error.exception.code, "STALE_LEASE")
        self.assertTrue(self.storage.stream.closed)

    def test_job_outbox_or_document_drift_fails_closed(self) -> None:
        self.queue.peek_parse_for_job.return_value = None
        with self.assertRaises(ParserInputError):
            self._service().prepare(self.command)
        self.assertEqual(self.storage.calls, 0)
        self.queue.peek_parse_for_job.return_value = self.binding
        self.leases.check_current.return_value = ClaimedJob(self.job_id, "AUDIT_EXPORT",
            "PROJECT", self.request.project_id, self.claim.payload_refs,
            self.claim.trace_id, 1, 1)
        with self.assertRaises(ParserInputError):
            self._service().prepare(self.command)
        self.assertEqual(self.storage.calls, 0)
        self.leases.check_current.return_value = self.claim
        changed = DocumentParseInputSource(self.source.committed, self.source.storage_locator,
            b"z" * 32, self.source.size_bytes, self.source.detected_mime)
        self.documents.read_input.side_effect = [self.source, changed]
        with self.assertRaises(ParserInputError) as error:
            self._service().prepare(self.command)
        self.assertEqual(error.exception.code, "PARSER_INPUT_CHANGED")
        self.assertTrue(self.storage.stream.closed)

    def test_bad_bytes_never_reach_parser_and_audit_is_pathless(self) -> None:
        self.storage.content = b"tampered"
        with self.assertRaises(ParserInputError) as error:
            self._service().prepare(self.command)
        self.assertEqual(error.exception.code, "FILE_INTEGRITY_MISMATCH")
        self.assertEqual(self.leases.check_current.call_count, 1)
        self.assertEqual(self.audit.append.call_count, 1)
        tx, event = self.audit.append.call_args.args
        self.assertTrue(tx.committed)
        self.assertEqual(event.action, "DOCUMENT_PARSE_INTEGRITY_FAILED")
        self.assertEqual((event.actor_id, event.original_actor_id),
                         (self.system_actor_id, self.request.actor_id))
        self.assertNotIn("projects/", repr(event))

    def test_integrity_audit_failure_does_not_expose_bytes(self) -> None:
        self.storage.content = b"tampered"
        self.audit.append.side_effect = RuntimeError("private audit failure")
        with self.assertRaises(ParserInputError) as error:
            self._service().prepare(self.command)
        self.assertEqual(error.exception.code, "PARSER_INPUT_UNAVAILABLE")
        self.assertIsNone(self.storage.stream)
        self.assertEqual(self.leases.check_current.call_count, 1)

    def test_invalid_command_and_unsupported_format_fail_before_storage(self) -> None:
        with self.assertRaises(ParserInputError):
            ParserInputCommand(self.job_id, 0, "parser-worker-1")
        with self.assertRaises(ParserInputError):
            self._service().prepare(object())
        self.documents.read_input.return_value = DocumentParseInputSource(
            self.source.committed, self.source.storage_locator,
            self.source.content_sha256, self.source.size_bytes, "application/octet-stream")
        with self.assertRaises(ParserInputError) as error:
            self._service().prepare(self.command)
        self.assertEqual(error.exception.code, "PARSER_FORMAT_UNSUPPORTED")
        self.assertEqual(self.storage.calls, 0)


if __name__ == "__main__":
    unittest.main()
