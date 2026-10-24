from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateError,
    CapabilityBaselineCreateService,
    CreateCapabilityBaseline,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilityDocumentRef,
    CapabilitySourceValidationError,
    CapabilitySourceValidator,
)
from plm_assistant.modules.capability.domain.source_collection import (
    CapabilitySourceCollectionError,
    canonical_source_collection_ref,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentVersionView,
    DocumentView,
)


class _Documents:
    def __init__(self, references: tuple[CapabilityDocumentRef, ...]) -> None:
        now = datetime.now(timezone.utc)
        self.versions = {
            item.document_version_id: DocumentVersionView(
                item.document_version_id, item.document_id, 1, "ab" * 32,
                8, "application/pdf", "AVAILABLE", None, now, now,
            ) for item in references
        }
        self.documents = {
            item.document_id: DocumentView(
                item.document_id, "GLOBAL", None, "STANDARD_CAPABILITY", None,
                "Standard", "standard.pdf", "ACTIVE",
                item.document_version_id, item.document_version_id,
                now, '"v0"',
            ) for item in references
        }

    def get_version_for_trace(self, _tx, **kwargs):
        return self.versions.get(kwargs["document_version_id"])

    def get(self, _tx, **kwargs):
        return self.documents.get(kwargs["document_id"])


class CapabilitySourceValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.references = (
            CapabilityDocumentRef(uuid.uuid4(), uuid.uuid4()),
            CapabilityDocumentRef(uuid.uuid4(), uuid.uuid4()),
        )

    def test_source_ref_is_sorted_deterministic_and_domain_separated(self) -> None:
        first = canonical_source_collection_ref(tuple(
            item.document_version_id for item in self.references
        ))
        second = canonical_source_collection_ref(tuple(
            item.document_version_id for item in reversed(self.references)
        ))
        ordered = sorted(str(item.document_version_id) for item in self.references)
        expected = "sha256:" + hashlib.sha256(
            ("capability-source-set.v1\n" + "\n".join(ordered)).encode()
        ).hexdigest()
        self.assertEqual(first, second)
        self.assertEqual(first, expected)

    def test_source_collection_rejects_duplicate_or_empty_ids(self) -> None:
        value = self.references[0].document_version_id
        for invalid in ((), (value, value), (uuid.UUID(int=0),)):
            with self.subTest(invalid=invalid), self.assertRaises(
                    CapabilitySourceCollectionError):
                canonical_source_collection_ref(invalid)

    def test_validator_accepts_only_current_global_standard_documents(self) -> None:
        documents = _Documents(self.references)
        result = CapabilitySourceValidator(documents).validate(
            object(), tuple(reversed(self.references)),
        )
        self.assertEqual(
            result.source_collection_ref,
            canonical_source_collection_ref(tuple(
                item.document_version_id for item in self.references
            )),
        )
        documents.documents[self.references[0].document_id] = replace(
            documents.documents[self.references[0].document_id],
            document_state="ARCHIVED",
        )
        with self.assertRaises(CapabilitySourceValidationError):
            CapabilitySourceValidator(documents).validate(object(), self.references)


class CapabilityBaselineCreateValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CreateCapabilityBaseline(
            b"s" * 32, b"c" * 32, uuid.uuid4(), "PLM.CORE", "PLM Core",
            "Synthetic standard", (CapabilityDocumentRef(uuid.uuid4(), uuid.uuid4()),),
            str(uuid.uuid4()),
        )
        self.service = CapabilityBaselineCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            sources=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_untrusted_input_fails_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"baseline_code": "lower"},
            {"name": " padded "}, {"description": ""},
            {"source_documents": ()}, {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                    CapabilityBaselineCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_and_key_are_redacted(self) -> None:
        view = repr(self.command)
        self.assertNotIn("s" * 32, view)
        self.assertNotIn("c" * 32, view)
        self.assertNotIn(self.command.idempotency_key, view)


if __name__ == "__main__":
    unittest.main()
