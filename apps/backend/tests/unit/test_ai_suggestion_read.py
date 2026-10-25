from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase

from plm_assistant.modules.ai.application.invocation_read import AIInvocationContextView
from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.suggestion_read import (
    AISuggestionEvidenceFact,
    AISuggestionReadError,
    AISuggestionReadRecord,
    AISuggestionReadService,
    AISuggestionSourceFact,
    GetAISuggestion,
)
from plm_assistant.modules.ai.application.task_read import AITaskInputView
from plm_assistant.modules.document.application.resolve_parse_nodes import (
    DocumentNodeLocation,
    DocumentNodeLocationSet,
    DocumentVersionLocation,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def __init__(self): self.calls = 0
    def require_valid(self, **_kwargs): self.calls += 1


class Authorization:
    def __init__(self, actor, project, role):
        self.actor, self.project, self.role = actor, project, role
    def require_in_transaction(self, *_args, **kwargs):
        return AuthorizedProjectAction(
            self.actor, self.project, kwargs["operation"], self.role,
        )


class Repository:
    def __init__(self, value): self.value, self.calls = value, 0
    def get(self, *_args, **_kwargs):
        self.calls += 1
        return self.value


class Nodes:
    def __init__(self, value): self.value, self.calls = value, []
    def resolve(self, _query, **kwargs):
        self.calls.append(kwargs)
        return self.value


class Versions:
    def __init__(self, value): self.value, self.calls = value, []
    def resolve(self, _query, **kwargs):
        self.calls.append(kwargs)
        return self.value


class AISuggestionReadTests(TestCase):
    def setUp(self) -> None:
        self.actor, self.project, self.task = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.document, self.version = uuid.uuid4(), uuid.uuid4()
        self.parse_record, self.result_ref = uuid.uuid4(), uuid.uuid4()
        self.source_hash = hashlib.sha256(b"source").digest()
        self.result_hash = hashlib.sha256(b"result").digest()
        self.payload = {
            "schema_ref": "gap-output.v2", "schema_version": 2,
            "items": [{
                "category": "PENDING_CONFIRMATION", "title": "确认范围",
                "summary": "需要确认实际业务范围", "rationale": "来源存在差异",
                "recommendation": "由项目经理确认", "source_citations": [{
                    "source_ordinal": 1, "node_ids": ["line-1"],
                }],
                "confirmation": {
                    "required": True, "question": "实际范围是什么？",
                    "required_fields": [{
                        "key": "SCOPE", "label": "实际范围",
                        "prompt": "请填写实际范围", "reason": "用于确定实施边界",
                        "required": True,
                    }],
                },
            }],
        }
        canonical = json.dumps(
            self.payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode()
        self.evidence = AISuggestionEvidenceFact(
            1, "document", "DOCUMENT_VERSION", self.document, self.version,
            self.result_hash,
        )
        self.source = AISuggestionSourceFact(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            self.document, self.version, self.project,
            self.parse_record, self.result_ref, self.source_hash, self.result_hash,
        )
        self.record = AISuggestionReadRecord(
            self.task, self.project, self.actor, "SUCCEEDED", "AVAILABLE", 3,
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            (AITaskInputView("DOC-02", self.document, self.version),),
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "deepseek-chat-v1",
            uuid.uuid4(), 2, "gap-output.v2", 2,
            AIInvocationContextView(
                uuid.uuid4(), 1, "project-documents.v1", "NONE", None, None,
            ),
            self.payload, canonical, hashlib.sha256(canonical).digest(),
            "NOT_FORMAL_FACT", (), datetime.now(timezone.utc),
            (self.evidence,), (self.source,),
        )
        locator = {
            "locator_type": "STRUCTURED_NODE",
            "parse_record_id": str(self.parse_record), "node_id": "line-1",
            "source_locator": {
                "locator_type": "TEXT_RANGE", "section_path": "plain-text-root",
                "start_offset": 0, "end_offset": 5,
                "normalized_fingerprint": hashlib.sha256(b"Alpha").hexdigest(),
            },
        }
        self.node_set = DocumentNodeLocationSet(
            self.document, self.version, self.parse_record, self.result_ref,
            self.source_hash, self.result_hash,
            f"/api/v1/projects/{self.project}/documents/{self.document}/versions/"
            f"{self.version}/content",
            (DocumentNodeLocation(
                "line-1", "TEXT_LINE", locator, hashlib.sha256(b"Alpha").digest(),
                "PARSED_NODE", "文本文档 / 字符 0–5",
            ),),
        )
        self.version_location = DocumentVersionLocation(
            self.document, self.version, self.source_hash,
            {"locator_type": "DOCUMENT"}, "DOCUMENT", "整个文档版本",
            f"/api/v1/projects/{self.project}/documents/{self.document}/versions/"
            f"{self.version}/content",
        )
        self.query = GetAISuggestion(
            b"s" * 32, uuid.uuid4(), self.project, self.task,
        )

    def service(self, *, actor=None, role="IMPLEMENTATION_MEMBER", record=None):
        actor = actor or self.actor
        repository = Repository(self.record if record is None else record)
        nodes, versions, guard = Nodes(self.node_set), Versions(self.version_location), Guard()
        service = AISuggestionReadService(
            unit_of_work=Tx, access=Access(actor), license_guard=guard,
            authorization=Authorization(actor, self.project, role),
            repository=repository, schemas=default_ai_output_schema_registry(),
            document_nodes=nodes, document_versions=versions,
            clock=lambda: datetime.now(timezone.utc),
        )
        return service, repository, nodes, versions, guard

    def test_v2_reauthorizes_twice_and_resolves_exact_document_nodes(self):
        service, repository, nodes, versions, guard = self.service()
        result = service.get(self.query)
        self.assertEqual(result.record.fact_status, "NOT_FORMAL_FACT")
        self.assertEqual(result.locations[0].precision, "PARSED_NODE")
        self.assertEqual(result.locations[0].locations[0]["node_id"], "line-1")
        self.assertEqual(nodes.calls[0]["node_ids"], ("line-1",))
        self.assertEqual(len(versions.calls), 1)
        self.assertEqual(repository.calls, 2)
        self.assertEqual(guard.calls, 3)

    def test_creator_or_management_only(self):
        service, *_ = self.service(actor=uuid.uuid4())
        with self.assertRaises(AISuggestionReadError) as caught:
            service.get(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        service, *_ = self.service(actor=uuid.uuid4(), role="PROJECT_MANAGER")
        self.assertEqual(service.get(self.query).record.ai_task_id, self.task)
        service, *_ = self.service(role="CUSTOMER_MEMBER")
        with self.assertRaises(AISuggestionReadError):
            service.get(self.query)

    def test_payload_evidence_and_owner_hash_drift_fail_closed(self):
        cases = (
            replace(self.record, payload_fingerprint=b"x" * 32),
            replace(self.record, evidence=(replace(
                self.evidence, content_fingerprint=b"x" * 32,
            ),)),
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(AISuggestionReadError):
                self.service(record=value)[0].get(self.query)
        service, *_ = self.service()
        service._nodes.value = replace(self.node_set, result_sha256=b"x" * 32)
        with self.assertRaises(AISuggestionReadError) as caught:
            service.get(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_v1_is_explicit_document_precision(self):
        payload = {
            "schema_ref": "gap-output.v1", "schema_version": 1,
            "items": [{
                "category": "DIFFERENCE", "title": "差异", "summary": "摘要",
                "rationale": "原因", "recommendation": "建议",
                "source_ordinals": [1],
            }],
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()
        record = replace(
            self.record, output_schema_ref="gap-output.v1", schema_version=1,
            canonical_payload=payload, canonical_payload_json=canonical,
            payload_fingerprint=hashlib.sha256(canonical).digest(),
        )
        service, _, nodes, versions, _ = self.service(record=record)
        result = service.get(self.query)
        self.assertEqual(result.locations[0].precision, "DOCUMENT")
        self.assertFalse(nodes.calls)
        self.assertEqual(len(versions.calls), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
