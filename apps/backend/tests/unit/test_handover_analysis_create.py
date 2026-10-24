from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import (
    DocumentVersionView, DocumentView,
)
from plm_assistant.modules.handover.application.create_analysis import (
    CreateHandoverAnalysis, HandoverAnalysisCreateError,
    HandoverAnalysisCreateService,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverDocumentRef, HandoverSourceValidationError,
    HandoverSourceValidator,
)
from plm_assistant.modules.handover.domain.source_set import (
    HandoverSourceSetError, canonical_handover_source_set_ref,
)


class _Documents:
    def __init__(self, project_id, refs):
        now = datetime.now(timezone.utc)
        self.versions = {
            item.document_version_id: DocumentVersionView(
                item.document_version_id, item.document_id, 1, "ab" * 32,
                8, "application/pdf", "AVAILABLE", None, now, now,
            ) for item in refs
        }
        self.documents = {
            item.document_id: DocumentView(
                item.document_id, "PROJECT", project_id, "PROJECT_RECORD", None,
                "Handover", "handover.pdf", "ACTIVE",
                item.document_version_id, item.document_version_id,
                now, '"v0"',
            ) for item in refs
        }

    def get_version_for_trace(self, _tx, **kwargs):
        return self.versions.get(kwargs["document_version_id"])

    def get(self, _tx, **kwargs):
        return self.documents.get(kwargs["document_id"])


class HandoverSourceValidationTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.refs = (
            HandoverDocumentRef(uuid.uuid4(), uuid.uuid4()),
            HandoverDocumentRef(uuid.uuid4(), uuid.uuid4()),
        )

    def test_source_ref_is_sorted_and_matches_schema_domain(self):
        first = canonical_handover_source_set_ref(tuple(
            item.document_version_id for item in self.refs
        ))
        second = canonical_handover_source_set_ref(tuple(
            item.document_version_id for item in reversed(self.refs)
        ))
        ordered = sorted(str(item.document_version_id) for item in self.refs)
        expected = "sha256:" + hashlib.sha256(
            ("handover-source-set.v1\n" + "\n".join(ordered)).encode()
        ).hexdigest()
        self.assertEqual(first, second)
        self.assertEqual(first, expected)

    def test_source_ref_rejects_empty_duplicate_or_nil(self):
        value = self.refs[0].document_version_id
        for invalid in ((), (value, value), (uuid.UUID(int=0),)):
            with self.subTest(invalid=invalid), self.assertRaises(HandoverSourceSetError):
                canonical_handover_source_set_ref(invalid)

    def test_validator_accepts_only_current_project_documents(self):
        documents = _Documents(self.project_id, self.refs)
        result = HandoverSourceValidator(documents).validate(
            object(), project_id=self.project_id,
            references=tuple(reversed(self.refs)),
        )
        self.assertEqual(result.source_set_ref, canonical_handover_source_set_ref(tuple(
            item.document_version_id for item in self.refs
        )))
        documents.documents[self.refs[0].document_id] = replace(
            documents.documents[self.refs[0].document_id],
            project_id=uuid.uuid4(),
        )
        with self.assertRaises(HandoverSourceValidationError):
            HandoverSourceValidator(documents).validate(
                object(), project_id=self.project_id, references=self.refs,
            )


class HandoverAnalysisCreateValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CreateHandoverAnalysis(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            "Project handover", (HandoverDocumentRef(uuid.uuid4(), uuid.uuid4()),),
            str(uuid.uuid4()),
        )
        self.service = HandoverAnalysisCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), sources=object(), repository=object(),
            receipts=object(), audit=object(),
        )

    def test_untrusted_input_fails_before_io(self):
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"analysis_purpose": " padded "}, {"source_documents": ()},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                    HandoverAnalysisCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_and_key_are_redacted(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
