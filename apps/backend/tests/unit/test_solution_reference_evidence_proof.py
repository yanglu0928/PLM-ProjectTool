from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.document.application.prove_fixed_source import FixedSourceProofError, VerifiedFixedSource
from plm_assistant.modules.document.application.read_documents import DocumentEvidenceSourceFacts
from plm_assistant.modules.evidence.application.fixed_global_reference_source import (
    EvidenceFixedGlobalReferenceService, GlobalReferenceEvidenceError,
    GlobalReferenceEvidenceQuery, VerifiedGlobalReferenceEvidence,
)
from plm_assistant.modules.evidence.application.fixed_project_source import VerifiedProjectEvidence
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.solution.infrastructure.reference_evidence_proof import ReferenceEvidenceProofAdapter
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode, ParsedResult, TextRangePosition,
)


class _Session:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, tx, *, session_token, now):
        return self.actor


class _Admin:
    def __init__(self, actor):
        self.actor = actor

    def authorized_admin(self, tx, *, session_token, now):
        return self.actor


class _Evidence:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_for_trace(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.source


class _Document:
    def __init__(self, proof):
        self.proof = proof
        self.calls = []

    def prove(self, tx, query, **kwargs):
        self.calls.append((tx, query, kwargs))
        if isinstance(self.proof, Exception):
            raise self.proof
        return self.proof


class _Proof:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def prove(self, tx, query, evidence_id):
        self.calls.append((tx, query, evidence_id))
        return self.result


class GlobalReferenceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tx, self.actor = object(), uuid.uuid4()
        self.evidence_id, self.document_id, self.version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.trace = uuid.uuid4()
        self.digest = hashlib.sha256(b"synthetic").digest()
        self.source = LockedEvidenceSource(
            self.evidence_id, "GLOBAL", None, self.document_id, self.version_id,
            None, {"locator_type": "DOCUMENT"}, self.digest, 0,
        )
        self.sessions, self.admins = _Session(self.actor), _Admin(self.actor)
        self.evidence = _Evidence(self.source)
        facts = DocumentEvidenceSourceFacts(
            self.document_id, self.version_id, "GLOBAL", None,
            "REFERENCE_MATERIAL", "ACTIVE", self.digest.hex(),
        )
        self.documents = _Document(VerifiedFixedSource(facts))
        self.service = EvidenceFixedGlobalReferenceService(
            sessions=self.sessions, admins=self.admins,
            evidence=self.evidence, documents=self.documents,
            clock=lambda: datetime.now(timezone.utc),
        )

    def prove(self):
        return self.service.prove(
            self.tx, GlobalReferenceEvidenceQuery(b"s" * 32, self.trace), self.evidence_id,
        )

    def test_global_reference_uses_admin_and_same_transaction(self):
        proof = self.prove()
        self.assertEqual((proof.evidence_id, proof.authorized_admin_id),
                         (self.evidence_id, self.actor))
        self.assertIs(self.evidence.calls[0][0], self.tx)
        self.assertEqual(self.evidence.calls[0][1]["scope"], "GLOBAL")
        self.assertIs(self.documents.calls[0][0], self.tx)
        self.assertEqual(self.documents.calls[0][1].scope, "GLOBAL")
        self.assertNotIn(self.digest.hex(), repr(proof))

    def test_nonadmin_and_missing_source_fail_before_document(self):
        self.admins.actor = None
        with self.assertRaises(GlobalReferenceEvidenceError):
            self.prove()
        self.assertEqual(self.evidence.calls, [])
        self.admins.actor = self.actor
        self.evidence.source = None
        with self.assertRaisesRegex(GlobalReferenceEvidenceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.assertEqual(self.documents.calls, [])

    def test_scope_category_and_digest_drift_fail_closed(self):
        self.evidence.source = replace(self.source, scope="PROJECT", project_id=uuid.uuid4())
        with self.assertRaisesRegex(GlobalReferenceEvidenceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.evidence.source = self.source
        self.documents.proof = VerifiedFixedSource(replace(
            self.documents.proof.facts, document_category="PROJECT_RECORD"))
        with self.assertRaisesRegex(GlobalReferenceEvidenceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.documents.proof = VerifiedFixedSource(replace(
            self.documents.proof.facts, document_category="STANDARD_CAPABILITY"))
        self.assertEqual(self.prove().content_fingerprint, self.digest)
        self.evidence.source = replace(self.source, content_fingerprint=b"x" * 32)
        with self.assertRaisesRegex(GlobalReferenceEvidenceError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.prove()

    def test_missing_parse_identity_and_physical_integrity_fail_closed(self):
        self.evidence.source = replace(self.source, locator={"locator_type": "PAGE", "page_no": 1})
        with self.assertRaisesRegex(GlobalReferenceEvidenceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.evidence.source = self.source
        self.documents.proof = FixedSourceProofError("FILE_INTEGRITY_MISMATCH")
        with self.assertRaisesRegex(GlobalReferenceEvidenceError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.prove()

    def test_parsed_node_requires_exact_locator_and_verified_content(self):
        record_id, result_id = uuid.uuid4(), uuid.uuid4()
        payload = ParsedResult(
            document_version_id=self.version_id, source_sha256=self.digest,
            parser_profile="PLAIN_TEXT", parser_version="1",
            nodes=(ParsedNode("line-1", "TEXT_LINE", "Synthetic",
                              TextRangePosition(0, 9, hashlib.sha256(b"Synthetic").hexdigest())),),
        ).canonical_bytes()
        locator = json.loads(payload)["nodes"][0]["source_locator"]
        self.evidence.source = replace(
            self.source, source_parse_record_id=record_id, locator=locator,
            content_fingerprint=hashlib.sha256(b"Synthetic").digest(),
        )
        self.documents.proof = VerifiedFixedSource(
            self.documents.proof.facts, record_id, result_id, "PLAIN_TEXT", "1",
            hashlib.sha256(payload).digest(), payload,
        )
        self.assertEqual(self.prove().content_fingerprint, hashlib.sha256(b"Synthetic").digest())
        self.evidence.source = replace(self.evidence.source,
                                       locator={**locator, "start_offset": 1})
        with self.assertRaises(GlobalReferenceEvidenceError):
            self.prove()


class ReferenceEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tx, self.eid, self.vid = object(), uuid.uuid4(), uuid.uuid4()
        self.project_id, self.actor = uuid.uuid4(), uuid.uuid4()
        self.project = _Proof(VerifiedProjectEvidence(
            self.eid, self.project_id, uuid.uuid4(), self.vid,
            None, 1, b"p" * 32, verified_by=self.actor,
            verified_project_role="IMPLEMENTATION_MEMBER",
        ))
        self.global_ref = _Proof(VerifiedGlobalReferenceEvidence(
            self.eid, uuid.uuid4(), self.vid, None, b"g" * 32, self.actor,
        ))
        self.adapter = ReferenceEvidenceProofAdapter(
            project=self.project, global_reference=self.global_ref)

    def prove(self, scope="PROJECT", project_id=None):
        if project_id is None and scope == "PROJECT":
            project_id = self.project_id
        return self.adapter.prove(
            self.tx, session_token=b"s" * 32, trace_id=uuid.uuid4(),
            scope=scope, project_id=project_id, evidence_id=self.eid,
        )

    def test_project_and_global_keep_scope_and_transaction(self):
        self.assertEqual(self.prove().content_fingerprint, b"p" * 32)
        self.assertIs(self.project.calls[0][0], self.tx)
        self.assertEqual(self.project.calls[0][1].project_id, self.project_id)
        self.assertEqual(self.prove("GLOBAL").content_fingerprint, b"g" * 32)
        self.assertIs(self.global_ref.calls[0][0], self.tx)

    def test_unverified_role_identity_and_scope_rejected(self):
        self.project.result = replace(self.project.result, verified_project_role="CUSTOMER_MEMBER")
        self.assertIsNone(self.prove())
        self.project.result = replace(self.project.result, verified_project_role="PROJECT_MANAGER",
                                      project_id=uuid.uuid4())
        self.assertIsNone(self.prove())
        self.global_ref.result = replace(self.global_ref.result, scope="PROJECT")
        self.assertIsNone(self.prove("GLOBAL"))
        self.assertIsNone(self.prove("GLOBAL", self.project_id))


if __name__ == "__main__":
    unittest.main()
