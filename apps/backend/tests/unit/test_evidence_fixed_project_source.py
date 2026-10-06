from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.document.application.prove_fixed_source import (
    FixedSourceProofError, VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, EvidenceFixedProjectSourceService,
    EvidenceFixedSourceError,
)
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode, ParsedResult, TextRangePosition,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Session:
    def __init__(self, actor):
        self.actor = actor
        self.calls = []

    def authenticated_user(self, tx, *, session_token, now):
        self.calls.append(tx)
        return self.actor


class _Project:
    def __init__(self):
        self.facts = ProjectActorFacts("ACTIVE", "PROJECT_MANAGER")
        self.calls = []

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        self.calls.append((tx, lock, project_id))
        return self.facts


class _Evidence:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_for_trace(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.source


class _Document:
    def __init__(self, fixed):
        self.fixed = fixed
        self.calls = []
        self.error = None

    def prove(self, tx, query, **kwargs):
        self.calls.append((tx, query, kwargs))
        if self.error is not None:
            raise self.error
        return self.fixed


class EvidenceFixedProjectSourceTests(unittest.TestCase):
    def setUp(self):
        self.tx = object()
        self.actor, self.project, self.evidence_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.document_id, self.version_id, self.record_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.result_id = uuid.uuid4()
        self.query = EvidenceFixedProjectQuery(b"s" * 32, uuid.uuid4(), self.project)
        self.source_sha = hashlib.sha256(b"source").digest()
        self.facts = DocumentEvidenceSourceFacts(
            self.document_id, self.version_id, "PROJECT", self.project,
            "PROJECT_RECORD", "ACTIVE", self.source_sha.hex(),
        )
        self.locator = {"locator_type": "DOCUMENT"}
        self.source = LockedEvidenceSource(
            self.evidence_id, "PROJECT", self.project, self.document_id,
            self.version_id, None, self.locator, self.source_sha, 2,
        )
        self.sessions = _Session(self.actor)
        self.projects = _Project()
        self.evidence = _Evidence(self.source)
        self.documents = _Document(VerifiedFixedSource(self.facts))
        self.service = EvidenceFixedProjectSourceService(
            sessions=self.sessions, projects=self.projects,
            evidence=self.evidence, documents=self.documents,
            clock=lambda: datetime.now(timezone.utc),
        )

    def prove(self):
        return self.service.prove(self.tx, self.query, self.evidence_id)

    def test_whole_document_uses_one_caller_transaction_and_hides_content(self):
        result = self.prove()
        self.assertEqual(result.content_fingerprint, self.source_sha)
        self.assertEqual((result.observed_lock_version, result.observed_state), (2, "ELIGIBLE"))
        self.assertEqual(
            (result.verified_by, result.verified_project_role, result.document_category),
            (self.actor, "PROJECT_MANAGER", "PROJECT_RECORD"),
        )
        self.assertTrue(self.projects.calls[0][1])
        self.assertTrue(all(call is self.tx for call in self.sessions.calls))
        self.assertIs(self.evidence.calls[0][0], self.tx)
        self.assertIs(self.documents.calls[0][0], self.tx)
        self.assertEqual(self.documents.calls[0][2]["parse_record_id"], None)
        self.assertNotIn(self.source_sha.hex(), repr(result))

    def test_inactive_or_wrong_role_fails_before_evidence_read(self):
        for actor, facts in ((None, self.projects.facts),
                             (self.actor, ProjectActorFacts("ACTIVE", "CUSTOMER_MANAGER")),
                             (self.actor, ProjectActorFacts("ARCHIVED", "PROJECT_MANAGER"))):
            with self.subTest(actor=actor, facts=facts):
                self.sessions.actor, self.projects.facts = actor, facts
                with self.assertRaises(EvidenceFixedSourceError):
                    self.prove()
                self.assertEqual(self.evidence.calls, [])

    def test_missing_or_cross_project_and_template_fail_closed(self):
        self.evidence.source = None
        with self.assertRaisesRegex(EvidenceFixedSourceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.assertEqual(self.documents.calls, [])
        self.evidence.source = replace(self.source, project_id=uuid.uuid4())
        with self.assertRaisesRegex(EvidenceFixedSourceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.documents.fixed = VerifiedFixedSource(replace(self.facts, document_category="TEMPLATE"))
        self.evidence.source = self.source
        with self.assertRaisesRegex(EvidenceFixedSourceError, "RESOURCE_NOT_FOUND"):
            self.prove()

    def test_missing_parse_identity_and_fingerprint_drift_fail_closed(self):
        self.evidence.source = replace(self.source, locator={"locator_type": "PAGE", "page_no": 1})
        with self.assertRaisesRegex(EvidenceFixedSourceError, "RESOURCE_NOT_FOUND"):
            self.prove()
        self.evidence.source = replace(self.source, content_fingerprint=b"x" * 32)
        with self.assertRaisesRegex(EvidenceFixedSourceError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.prove()
        self.evidence.source = replace(self.source, source_parse_record_id=self.record_id)
        with self.assertRaisesRegex(EvidenceFixedSourceError, "RESOURCE_NOT_FOUND"):
            self.prove()

    def test_parsed_node_uses_verified_fixed_bytes_and_exact_locator(self):
        payload = ParsedResult(
            document_version_id=self.version_id, source_sha256=self.source_sha,
            parser_profile="PLAIN_TEXT", parser_version="1",
            nodes=(ParsedNode("line-1", "TEXT_LINE", "Synthetic",
                              TextRangePosition(0, 9, hashlib.sha256(b"Synthetic").hexdigest())),),
        ).canonical_bytes()
        locator = json.loads(payload)["nodes"][0]["source_locator"]
        self.evidence.source = replace(
            self.source, source_parse_record_id=self.record_id,
            locator=locator,
            content_fingerprint=hashlib.sha256(b"Synthetic").digest(),
        )
        self.documents.fixed = VerifiedFixedSource(
            self.facts, self.record_id, self.result_id, "PLAIN_TEXT", "1",
            hashlib.sha256(payload).digest(), payload,
        )
        result = self.prove()
        self.assertEqual(result.source_parse_record_id, self.record_id)
        self.assertEqual(result.content_fingerprint, hashlib.sha256(b"Synthetic").digest())
        self.assertNotIn("Synthetic", repr(result))
        self.evidence.source = replace(self.evidence.source,
                                       locator={**locator, "start_offset": 1})
        with self.assertRaises(EvidenceFixedSourceError):
            self.prove()

    def test_physical_integrity_error_is_not_returned_as_content(self):
        self.documents.error = FixedSourceProofError("FILE_INTEGRITY_MISMATCH")
        with self.assertRaisesRegex(EvidenceFixedSourceError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.prove()

    def test_configured_role_and_exact_category_policy_are_enforced(self):
        self.projects.facts = ProjectActorFacts("ACTIVE", "IMPLEMENTATION_MEMBER")
        service = EvidenceFixedProjectSourceService(
            sessions=self.sessions,
            projects=self.projects,
            evidence=self.evidence,
            documents=self.documents,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
            }),
            required_document_category="PROJECT_RECORD",
            clock=lambda: datetime.now(timezone.utc),
        )
        result = service.prove(self.tx, self.query, self.evidence_id)
        self.assertEqual(result.verified_project_role, "IMPLEMENTATION_MEMBER")
        self.documents.fixed = VerifiedFixedSource(
            replace(self.facts, document_category="CONTRACTUAL")
        )
        with self.assertRaisesRegex(EvidenceFixedSourceError, "RESOURCE_NOT_FOUND"):
            service.prove(self.tx, self.query, self.evidence_id)
        with self.assertRaises(ValueError):
            EvidenceFixedProjectSourceService(
                sessions=self.sessions,
                projects=self.projects,
                evidence=self.evidence,
                documents=self.documents,
                allowed_project_roles=frozenset(),
            )


if __name__ == "__main__":
    unittest.main()
