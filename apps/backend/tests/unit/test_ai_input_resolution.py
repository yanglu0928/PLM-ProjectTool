from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.entrypoints.ai_document_input_owner import DocumentVersionAIInputOwner
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResolutionError, AIInputResolutionQuery, AIInputResourceVersionRef,
    AIInputVersionResolver, AIResolvedInputVersionRef,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentTraceIdentity,
)


class _Owner:
    def __init__(self) -> None:
        self.calls = 0
        self.result = None
        self.error = None

    def resolve(self, transaction, query, project_id, ref):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result or AIResolvedInputVersionRef(
            ref.resource_type, "document", "DOCUMENT_VERSION",
            ref.resource_id, ref.version_id, "PROJECT", project_id,
        )


class _Documents:
    def __init__(self) -> None:
        self.calls = []
        self.error = None
        self.mismatch = False

    def resolve_version_for_trace(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        if self.error:
            raise DocumentReadError(self.error)
        return DocumentTraceIdentity(
            uuid.uuid4() if self.mismatch else kwargs["document_id"],
            kwargs["document_version_id"], "PROJECT", kwargs["path_project_id"],
        )


class AIInputResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.query = AIInputResolutionQuery(b"s" * 32, uuid.uuid4())
        self.ref = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
        self.tx = object()

    def test_registered_owner_returns_exact_internal_identity(self) -> None:
        owner = _Owner()
        resolver = AIInputVersionResolver({"DOC-02": owner})
        result = resolver.resolve_all(self.tx, self.query, self.project, (self.ref,))
        self.assertEqual(result[0].object_id, self.ref.resource_id)
        self.assertEqual(result[0].version_id, self.ref.version_id)
        self.assertEqual((result[0].owner_module, result[0].object_type),
                         ("document", "DOCUMENT_VERSION"))

    def test_unregistered_duplicate_and_bad_query_fail_closed(self) -> None:
        owner = _Owner()
        resolver = AIInputVersionResolver({"DOC-02": owner})
        with self.assertRaises(AIInputResolutionError) as missing:
            AIInputVersionResolver({}).resolve_all(
                self.tx, self.query, self.project,
                (replace(self.ref, resource_type="REQ-03"),),
            )
        self.assertEqual(missing.exception.code, "RESOURCE_NOT_FOUND")
        for refs, query in (((self.ref, self.ref), self.query),
                            ((self.ref,), replace(self.query, session_token=b"short"))):
            with self.subTest(refs=len(refs)), self.assertRaises(AIInputResolutionError) as caught:
                resolver.resolve_all(self.tx, query, self.project, refs)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(owner.calls, 0)

    def test_owner_mismatch_and_cross_project_are_rejected(self) -> None:
        owner = _Owner()
        resolver = AIInputVersionResolver({"DOC-02": owner})
        owner.result = AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", uuid.uuid4(),
            self.ref.version_id, "PROJECT", self.project,
        )
        with self.assertRaises(AIInputResolutionError) as mismatch:
            resolver.resolve_all(self.tx, self.query, self.project, (self.ref,))
        self.assertEqual(mismatch.exception.code, "AI_INPUT_UNAVAILABLE")
        owner.result = replace(owner.result, object_id=self.ref.resource_id,
                               project_id=uuid.uuid4())
        with self.assertRaises(AIInputResolutionError) as cross:
            resolver.resolve_all(self.tx, self.query, self.project, (self.ref,))
        self.assertEqual(cross.exception.code, "RESOURCE_NOT_FOUND")

    def test_owner_unexpected_failure_is_masked(self) -> None:
        owner = _Owner()
        owner.error = RuntimeError("sensitive provider detail")
        resolver = AIInputVersionResolver({"DOC-02": owner})
        with self.assertRaises(AIInputResolutionError) as caught:
            resolver.resolve_all(self.tx, self.query, self.project, (self.ref,))
        self.assertEqual(caught.exception.code, "AI_INPUT_UNAVAILABLE")
        self.assertNotIn("sensitive", str(caught.exception))

    def test_document_bridge_uses_authorized_fixed_version_resolution(self) -> None:
        documents = _Documents()
        bridge = DocumentVersionAIInputOwner(documents)
        result = bridge.resolve(self.tx, self.query, self.project, self.ref)
        self.assertEqual(result, AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", self.ref.resource_id,
            self.ref.version_id, "PROJECT", self.project,
        ))
        transaction, kwargs = documents.calls[0]
        self.assertIs(transaction, self.tx)
        self.assertEqual(kwargs["session_token"], b"s" * 32)
        self.assertEqual(kwargs["path_project_id"], self.project)
        self.assertNotIn("scope", kwargs)

    def test_document_bridge_masks_owner_failures_and_mismatch(self) -> None:
        documents = _Documents()
        bridge = DocumentVersionAIInputOwner(documents)
        for source, expected in (
            ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"),
            ("RESOURCE_NOT_FOUND", "RESOURCE_NOT_FOUND"),
            ("LICENSE_OPERATION_DENIED", "LICENSE_OPERATION_DENIED"),
            ("DOCUMENT_UNAVAILABLE", "AI_INPUT_UNAVAILABLE"),
        ):
            documents.error = source
            with self.subTest(source=source), self.assertRaises(AIInputResolutionError) as caught:
                bridge.resolve(self.tx, self.query, self.project, self.ref)
            self.assertEqual(caught.exception.code, expected)
        documents.error = None
        documents.mismatch = True
        with self.assertRaises(AIInputResolutionError) as mismatch:
            bridge.resolve(self.tx, self.query, self.project, self.ref)
        self.assertEqual(mismatch.exception.code, "AI_INPUT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
