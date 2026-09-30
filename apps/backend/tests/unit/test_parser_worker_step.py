from __future__ import annotations

import hashlib
import io
import time
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_publish import (
    PublishedParseResult, StoredParseResult,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.worker_step import (
    ParserWorkerError, ParserWorkerStep, extract_by_profile,
)


class _Lease:
    def __init__(self, claim: ClaimedJob) -> None:
        self.claim = claim
        self.heartbeats = 0
        self.fail_heartbeat = False

    def claim_next_parse(self, *, worker_ref, lease_seconds):
        value, self.claim = self.claim, None
        return value

    def heartbeat(self, *, job_id, fencing_token, worker_ref, lease_seconds):
        self.heartbeats += 1
        if self.fail_heartbeat:
            raise RuntimeError("synthetic DB outage")


class _Storage:
    def __init__(self) -> None:
        self.writes = 0

    def write_once(self, *, scope, project_id, result_ref_id, content):
        self.writes += 1
        locator = (f"results/projects/{project_id.hex}/{result_ref_id.hex[:2]}/"
                   f"{result_ref_id.hex}.json")
        return StoredParseResult(result_ref_id, locator,
                                 hashlib.sha256(content).digest(), len(content))


class ParserWorkerStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = b"Synthetic Worker line\n"
        self.job_id, self.project_id, self.version_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.plan = choose_parser_profile(ParserInputVersion(self.version_id,
            hashlib.sha256(self.raw).digest(), len(self.raw), "text/plain"))
        self.claim = ClaimedJob(self.job_id, "DOCUMENT_PARSE", "PROJECT",
            self.project_id, {}, str(uuid.uuid4()), 1, 1)
        self.lease = _Lease(self.claim)
        self.preparer, self.first, self.retry, self.publisher = (
            Mock(), Mock(), Mock(), Mock())
        self.preparer.prepare.side_effect = lambda command: VerifiedParserInput(
            self.plan, self.job_id, command.fencing_token,
            self.claim.attempt_no, io.BytesIO(self.raw))
        self.started = StartedParseAttempt(uuid.uuid4(), self.job_id,
            self.version_id, self.plan.parser_profile, self.plan.parser_version,
            1, datetime.now(timezone.utc))
        self.first.start.return_value = self.started
        self.published = PublishedParseResult(self.started.parse_record_id,
            uuid.uuid4(), datetime.now(timezone.utc))
        self.publisher.publish.return_value = self.published
        self.storage = _Storage()

    def worker(self, *, extractor=None) -> ParserWorkerStep:
        return ParserWorkerStep(leases=self.lease, preparer=self.preparer,
            first=self.first, retry=self.retry, storage=self.storage,
            publisher=self.publisher, worker_ref="parser-test",
            lease_seconds=6, heartbeat_interval_seconds=0.1,
            extractor=extractor)

    def test_real_text_extraction_then_private_write_and_publication(self) -> None:
        worker = self.worker()
        result = worker.step()
        self.assertEqual((result.kind, result.published), ("PUBLISHED", self.published))
        self.assertEqual(self.storage.writes, 1)
        self.assertGreaterEqual(self.lease.heartbeats, 1)
        parsed = self.publisher.publish.call_args.kwargs["parsed"]
        self.assertEqual(parsed.document_version_id, self.version_id)
        self.assertIn("Synthetic Worker line", parsed.canonical_bytes().decode("utf-8"))
        self.assertEqual(worker.step().kind, "IDLE")
        worker.request_stop()
        self.assertEqual(worker.step().kind, "STOPPED")

    def test_long_extraction_renews_lease_in_background(self) -> None:
        def slow(prepared):
            time.sleep(0.45)
            return extract_by_profile(prepared, ocr_engine=None)
        self.assertEqual(self.worker(extractor=slow).step().kind, "PUBLISHED")
        self.assertGreaterEqual(self.lease.heartbeats, 3)

    def test_heartbeat_failure_prevents_publication_and_new_admission(self) -> None:
        self.lease.fail_heartbeat = True
        def slow(prepared):
            time.sleep(0.25)
            return extract_by_profile(prepared, ocr_engine=None)
        worker = self.worker(extractor=slow)
        with self.assertRaises(ParserWorkerError) as error:
            worker.step()
        self.assertEqual(error.exception.code, "PARSER_HEARTBEAT_UNAVAILABLE")
        self.publisher.publish.assert_not_called()
        with self.assertRaises(ParserWorkerError) as error:
            worker.step()
        self.assertEqual(error.exception.code, "PARSER_WORKER_STOPPED")

    def test_image_requires_explicit_offline_engine(self) -> None:
        image = VerifiedParserInput(choose_parser_profile(ParserInputVersion(
            uuid.uuid4(), hashlib.sha256(b"image").digest(), 5, "image/png")),
            uuid.uuid4(), 1, 1, io.BytesIO(b"image"))
        with self.assertRaises(ParserWorkerError) as error:
            extract_by_profile(image, ocr_engine=None)
        self.assertEqual(error.exception.code, "PARSER_OCR_ENGINE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
