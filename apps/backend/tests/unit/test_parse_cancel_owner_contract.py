from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase
from uuid import uuid4

from plm_assistant.modules.document.application.request_parse_cancel import DocumentParseJobCancelOwner
from plm_assistant.modules.jobs.application.cancel_request import JobCancelError
from plm_assistant.modules.jobs.infrastructure.parse_cancel_repository import (
    ParseCancelFacts, ParseCancelMutation, ParseCancelStoreError,
)


class ParserCancelOwnerContractTests(TestCase):
    def test_facts_reject_incoherent_history_and_version(self):
        valid = ParseCancelFacts(uuid4(), "PENDING", None, None, None, 0)
        for changes in (
            {"state": "CANCELLED"}, {"lock_version": True}, {"lock_version": -1},
            {"requested_by": uuid4()},
        ):
            with self.assertRaises(ParseCancelStoreError):
                replace(valid, **changes)
        cancelled = ParseCancelFacts(uuid4(), "CANCELLED", uuid4(),
                                     datetime.now(timezone.utc), "reason", 2)
        self.assertEqual(cancelled.state, "CANCELLED")

    def test_mutation_rejects_finished_changed(self):
        with self.assertRaises(ParseCancelStoreError):
            ParseCancelMutation(uuid4(), "SUCCEEDED", True)
        self.assertFalse(ParseCancelMutation(uuid4(), "FAILED", False).changed)

    def test_owner_requires_actual_dependencies_and_command(self):
        with self.assertRaises(ValueError):
            DocumentParseJobCancelOwner(unit_of_work=None, queue=object(), sources=object(),
                project_access=object(), projects=object(), license_guard=object(),
                cancellations=object(), receipts=object(), audit_sources=object(), audit=object())
        owner = DocumentParseJobCancelOwner(unit_of_work=object(), queue=object(),
            sources=object(), project_access=object(), projects=object(),
            license_guard=object(), cancellations=object(), receipts=object(),
            audit_sources=object(), audit=object())
        with self.assertRaises(JobCancelError) as error:
            owner.cancel(object(), idempotency_key="synthetic-test-key-0001")
        self.assertEqual(error.exception.code, "VALIDATION_FAILED")
