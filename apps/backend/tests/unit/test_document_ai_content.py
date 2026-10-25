from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from dataclasses import replace

from plm_assistant.entrypoints.ai_document_content_owner import (
    AIDocumentContentOwner,
)
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentIdentityQuery,
    AIExecutionContentPlanError,
    AIExecutionContentReadQuery,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionInputRef,
)
from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentError,
    DocumentAIContentQuery,
    DocumentAIContentService,
    DocumentAIContentSource,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts,
    ProjectAuthorizationService,
)


class _ProjectRepository:
    def __init__(self) -> None:
        self.facts = ProjectActorFacts("ACTIVE", "IMPLEMENTATION_MEMBER")
        self.locks: list[bool] = []

    def actor_facts(self, transaction, *, user_id, project_id, lock=False):
        self.locks.append(lock)
        return self.facts

    def owner_project_id(self, transaction, *, target, resource_id):
        raise AssertionError("target lookup not expected")


class _Guard:
    def __init__(self) -> None:
        self.calls = 0

    def require_valid(self, *, trace_id):
        self.calls += 1
        return object()


class _Repository:
    def __init__(self, selected, exact):
        self.selected = selected
        self.exact = exact
        self.selection_calls = 0

    def select_current(self, transaction, **kwargs):
        self.selection_calls += 1
        return self.selected

    def get_exact(self, transaction, **kwargs):
        key = (kwargs["parse_record_id"], kwargs["result_ref_id"])
        return self.exact.get(key)


class _Storage:
    def __init__(self, content):
        self.content = content

    def read_verified(self, **kwargs):
        return self.content[kwargs["result_ref_id"]]


def _result(version_id, source_sha, text="需求 A\r\n第二行", *, kind="TEXT_LINE"):
    payload = {
        "schema_version": "1", "document_version_id": str(version_id),
        "source_sha256": source_sha.hex(), "parser_profile": "PLAIN_TEXT",
        "parser_version": "1", "nodes": [{
            "node_id": "line-1", "kind": kind, "text": text,
            "source_locator": {"locator_type": "TEXT_RANGE", "start_offset": 0,
                               "end_offset": max(1, len(text)),
                               "normalized_fingerprint": "a" * 64},
        }],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


class DocumentAIContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.uuid4()
        self.actor_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.source_sha = hashlib.sha256(b"source").digest()
        self.content = _result(self.version_id, self.source_sha)
        self.source = DocumentAIContentSource(
            self.document_id, self.version_id, self.project_id,
            uuid.uuid4(), uuid.uuid4(), "PLAIN_TEXT", "1",
            "results/projects/example/result.json", self.source_sha,
            hashlib.sha256(self.content).digest(), len(self.content), 1,
        )
        self.project_repository = _ProjectRepository()
        self.guard = _Guard()
        self.repository = _Repository(
            self.source,
            {(self.source.parse_record_id, self.source.result_ref_id): self.source},
        )
        self.storage = _Storage({self.source.result_ref_id: self.content})
        self.projects = ProjectAuthorizationService(
            unit_of_work=lambda: None, repository=self.project_repository,
        )
        self.service = DocumentAIContentService(
            repository=self.repository, storage=self.storage,
            projects=self.projects, license_guard=self.guard,
        )
        self.query = DocumentAIContentQuery(
            self.project_id, self.actor_id, uuid.uuid4(), "gap-analysis.v1",
            "minimum.document.text.v1", "document.parse.fixed.v1",
        )

    def test_resolve_and_read_exact_normalizes_minimal_projection(self):
        identity = self.service.resolve_identity(
            object(), query=self.query, document_id=self.document_id,
            document_version_id=self.version_id,
        )
        result = self.service.read_exact(
            object(), query=self.query, identity=identity,
        )
        payload = json.loads(result.content_utf8)
        self.assertEqual(identity.record_count, 1)
        self.assertEqual(payload, {
            "nodes": [{"kind": "TEXT_LINE", "node_id": "line-1",
                       "text": "需求 A\n第二行"}],
            "schema_version": "document-minimum-text-v1",
        })
        self.assertNotIn("source_locator", result.content_utf8.decode())
        self.assertNotIn("需求", repr(result))
        self.assertEqual(self.guard.calls, 4)
        self.assertEqual(self.project_repository.locks, [True, True])

    def test_preview_projection_uses_preview_authority_and_minimum_content(self):
        self.project_repository.facts = ProjectActorFacts(
            "ACTIVE", "CUSTOMER_MANAGER",
        )
        result = self.service.resolve_projection(
            object(), query=self.query, document_id=self.document_id,
            document_version_id=self.version_id,
        )
        owner = AIDocumentContentOwner(self.service)
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            self.document_id, self.version_id, self.project_id,
        )
        query = AIExecutionContentIdentityQuery(
            uuid.uuid4(), self.project_id, self.actor_id, uuid.uuid4(),
            "gap-analysis.v1", "minimum.document.text.v1",
            owner.selection_policy_ref,
        )
        projection = owner.resolve_projection(
            object(), query=query, input_ref=input_ref,
        )
        self.assertEqual(result.content_utf8, projection.content_utf8)
        self.assertEqual(projection.source.content_revision_id,
                         self.source.parse_record_id)
        self.assertEqual(projection.source.projection_fingerprint,
                         hashlib.sha256(projection.content_utf8).digest())
        self.assertNotIn("需求", repr(projection))
        with self.assertRaises(DocumentAIContentError):
            self.service.resolve_identity(
                object(), query=self.query, document_id=self.document_id,
                document_version_id=self.version_id,
            )

    def test_execution_rereads_frozen_result_not_new_selection(self):
        identity = self.service.resolve_identity(
            object(), query=self.query, document_id=self.document_id,
            document_version_id=self.version_id,
        )
        newer_content = _result(self.version_id, self.source_sha, "newer")
        newer = replace(
            self.source, parse_record_id=uuid.uuid4(), result_ref_id=uuid.uuid4(),
            result_sha256=hashlib.sha256(newer_content).digest(),
            result_size_bytes=len(newer_content),
        )
        self.repository.selected = newer
        self.repository.exact[(newer.parse_record_id, newer.result_ref_id)] = newer
        self.storage.content[newer.result_ref_id] = newer_content
        result = self.service.read_exact(
            object(), query=self.query, identity=identity,
        )
        self.assertIn("需求 A", result.content_utf8.decode())
        self.assertNotIn("newer", result.content_utf8.decode())
        self.assertEqual(self.repository.selection_calls, 1)

    def test_current_authority_is_required_again_at_execution(self):
        identity = self.service.resolve_identity(
            object(), query=self.query, document_id=self.document_id,
            document_version_id=self.version_id,
        )
        self.project_repository.facts = None
        with self.assertRaises(DocumentAIContentError):
            self.service.read_exact(object(), query=self.query, identity=identity)

    def test_integrity_and_database_drift_fail_closed(self):
        identity = self.service.resolve_identity(
            object(), query=self.query, document_id=self.document_id,
            document_version_id=self.version_id,
        )
        self.storage.content[self.source.result_ref_id] = b"tampered"
        with self.assertRaisesRegex(
                DocumentAIContentError, "DOCUMENT_AI_CONTENT_INTEGRITY_MISMATCH"):
            self.service.read_exact(object(), query=self.query, identity=identity)
        self.storage.content[self.source.result_ref_id] = self.content
        self.repository.exact[(self.source.parse_record_id,
                               self.source.result_ref_id)] = replace(
                                   self.source, result_size_bytes=len(self.content) - 1)
        with self.assertRaises(DocumentAIContentError):
            self.service.read_exact(object(), query=self.query, identity=identity)

    def test_noncanonical_invalid_kind_control_and_empty_text_are_rejected(self):
        invalid_values = (
            self.content + b" ",
            _result(self.version_id, self.source_sha, kind="OCR_LINE"),
            _result(self.version_id, self.source_sha, text="unsafe\u0000"),
            _result(self.version_id, self.source_sha, text="   \r\n"),
        )
        for content in invalid_values:
            with self.subTest(content=content[-20:]):
                source = replace(
                    self.source, result_sha256=hashlib.sha256(content).digest(),
                    result_size_bytes=len(content),
                )
                repository = _Repository(
                    source, {(source.parse_record_id, source.result_ref_id): source})
                service = DocumentAIContentService(
                    repository=repository,
                    storage=_Storage({source.result_ref_id: content}),
                    projects=self.projects, license_guard=self.guard,
                )
                with self.assertRaises(DocumentAIContentError):
                    service.resolve_identity(
                        object(), query=self.query, document_id=self.document_id,
                        document_version_id=self.version_id,
                    )

    def test_owner_maps_identity_and_hides_owner_failures(self):
        owner = AIDocumentContentOwner(self.service)
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            self.document_id, self.version_id, self.project_id,
        )
        identity_query = AIExecutionContentIdentityQuery(
            uuid.uuid4(), self.project_id, self.actor_id, uuid.uuid4(),
            "gap-analysis.v1", "minimum.document.text.v1",
            "document.parse.fixed.v1",
        )
        source = owner.resolve_identity(
            object(), query=identity_query, input_ref=input_ref)
        self.assertEqual(source.content_revision_id, self.source.parse_record_id)
        self.assertEqual(source.content_object_id, self.source.result_ref_id)
        self.assertNotIn("storage_locator", repr(source))
        read_query = AIExecutionContentReadQuery(
            identity_query.content_plan_id, uuid.uuid4(), self.project_id,
            uuid.uuid4(), self.actor_id, uuid.uuid4(), uuid.uuid4(),
            "gap-analysis.v1", "minimum.document.text.v1",
        )
        projection = owner.read_exact(
            object(), query=read_query, source=source)
        self.assertEqual(projection.record_count, 1)
        self.project_repository.facts = None
        with self.assertRaisesRegex(
                AIExecutionContentPlanError, "AI_EXECUTION_SOURCE_UNAVAILABLE"):
            owner.read_exact(object(), query=read_query, source=source)


if __name__ == "__main__":
    unittest.main()
