from __future__ import annotations

import hashlib
import io
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.document.application.prove_global_standard import (
    GlobalStandardProofError, GlobalStandardReferenceProofService,
    GlobalStandardReferenceQuery,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentDownloadSource, DocumentVersionView, DocumentView,
)
from plm_assistant.modules.document.application.read_parse_result import FixedParseResultSource
from plm_assistant.modules.evidence.application.fixed_global_standard_source import (
    EvidenceFixedGlobalStandardService, StandardEvidenceError,
    StandardEvidenceQuery,
)
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode, ParsedResult, TextRangePosition,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Session:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, tx, *, session_token, now):
        return self.actor


class _Project:
    def __init__(self):
        self.facts = ProjectActorFacts("ACTIVE", "PROJECT_MANAGER")

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        assert lock
        return self.facts


class _Guard:
    def __init__(self):
        self.error = False

    def require_valid(self, *, trace_id):
        if self.error:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class _Documents:
    def __init__(self, version, document, source):
        self.version, self.document, self.source = version, document, source
        self.calls = []

    def get_version_for_trace(self, tx, **kwargs):
        self.calls.append(("version", tx, kwargs))
        return self.version

    def get(self, tx, **kwargs):
        self.calls.append(("document", tx, kwargs))
        return self.document

    def get_download_source(self, tx, **kwargs):
        self.calls.append(("source", tx, kwargs))
        return self.source


class _Files:
    def __init__(self):
        self.calls = 0
        self.error = False

    def open_verified_snapshot(self, locator, **kwargs):
        self.calls += 1
        if self.error:
            raise RuntimeError("private path must not escape")
        return io.BytesIO(b"standard")


class _Parses:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_for_trace(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.source


class _ParseBytes:
    def __init__(self, content):
        self.content = content

    def read_verified(self, **kwargs):
        return self.content


class _Evidence:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_for_trace(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.source


class GlobalStandardReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tx = object()
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.document_id, self.version_id = uuid.uuid4(), uuid.uuid4()
        self.evidence_id, self.record_id, self.result_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.query = GlobalStandardReferenceQuery(b"s" * 32, uuid.uuid4(), self.project)
        self.digest = hashlib.sha256(b"standard").digest()
        now = datetime.now(timezone.utc)
        version = DocumentVersionView(self.version_id, self.document_id, 1,
                                      self.digest.hex(), 8, "text/plain", "AVAILABLE",
                                      None, now, None)
        document = DocumentView(self.document_id, "GLOBAL", None,
                                "STANDARD_CAPABILITY", None, "Standard", "standard.txt",
                                "ACTIVE", self.version_id, self.version_id, now, '"v0"')
        source = DocumentDownloadSource(self.actor, self.document_id, self.version_id,
                                        uuid.uuid4(), "GLOBAL", None, "private/path",
                                        self.digest, 8, "text/plain")
        self.sessions, self.projects = _Session(self.actor), _Project()
        self.documents, self.files = _Documents(version, document, source), _Files()
        self.payload = ParsedResult(
            document_version_id=self.version_id, source_sha256=self.digest,
            parser_profile="PLAIN_TEXT", parser_version="1",
            nodes=(ParsedNode("line-1", "TEXT_LINE", "Standard",
                              TextRangePosition(0, 8, hashlib.sha256(b"Standard").hexdigest())),),
        ).canonical_bytes()
        self.parse_source = FixedParseResultSource(
            self.record_id, self.version_id, "GLOBAL", None,
            "PLAIN_TEXT", "1", self.result_id, "results/global/private.json",
            hashlib.sha256(self.payload).digest(), len(self.payload), 1,
        )
        self.parses, self.parse_bytes = _Parses(self.parse_source), _ParseBytes(self.payload)
        self.guard = _Guard()
        self.standard = GlobalStandardReferenceProofService(
            sessions=self.sessions, projects=self.projects, license_guard=self.guard,
            documents=self.documents, files=self.files, parses=self.parses,
            parse_bytes=self.parse_bytes,
        )
        self.evidence_source = LockedEvidenceSource(
            self.evidence_id, "GLOBAL", None, self.document_id, self.version_id,
            None, {"locator_type": "DOCUMENT"}, self.digest, 4,
        )
        self.evidence = _Evidence(self.evidence_source)
        self.owner = EvidenceFixedGlobalStandardService(
            sessions=self.sessions, projects=self.projects,
            evidence=self.evidence, standards=self.standard,
        )

    def prove_document(self, record=None):
        return self.standard.prove(
            self.tx, self.query, document_id=self.document_id,
            document_version_id=self.version_id, parse_record_id=record,
        )

    def prove_evidence(self):
        return self.owner.prove(
            self.tx, StandardEvidenceQuery(
                self.query.session_token, self.query.trace_id, self.project,
            ), self.evidence_id,
        )

    def test_whole_standard_reference_is_narrow_and_hides_locator(self):
        verified = self.prove_document()
        observed = self.prove_evidence()
        self.assertEqual((verified.facts.scope, verified.facts.document_category),
                         ("GLOBAL", "STANDARD_CAPABILITY"))
        self.assertEqual((observed.scope, observed.target_project_id),
                         ("GLOBAL", self.project))
        self.assertEqual(self.files.calls, 2)
        self.assertTrue(all(call[1] is self.tx for call in self.documents.calls))
        self.assertTrue(all(call[2]["project_id"] is None for call in self.documents.calls))
        self.assertNotIn("private/path", repr(verified))
        self.assertNotIn("private/path", repr(observed))

    def test_invalid_role_or_category_rejected_before_file_access(self):
        self.projects.facts = ProjectActorFacts("ACTIVE", "CUSTOMER_MANAGER")
        with self.assertRaisesRegex(GlobalStandardProofError, "RESOURCE_NOT_FOUND"):
            self.prove_document()
        self.assertEqual(self.files.calls, 0)
        self.projects.facts = ProjectActorFacts("ACTIVE", "PROJECT_MANAGER")
        self.documents.document = replace(self.documents.document,
                                          document_category="REFERENCE_MATERIAL")
        with self.assertRaisesRegex(GlobalStandardProofError, "RESOURCE_NOT_FOUND"):
            self.prove_document()
        self.assertEqual(self.files.calls, 0)

    def test_session_license_and_archived_target_fail_closed(self):
        self.sessions.actor = None
        with self.assertRaisesRegex(GlobalStandardProofError, "AUTH_ACCESS_DENIED"):
            self.prove_document()
        self.sessions.actor = self.actor
        self.guard.error = True
        with self.assertRaisesRegex(GlobalStandardProofError, "LICENSE_OPERATION_DENIED"):
            self.prove_document()
        self.guard.error = False
        self.projects.facts = ProjectActorFacts("ARCHIVED", "PROJECT_MANAGER")
        with self.assertRaisesRegex(StandardEvidenceError, "RESOURCE_NOT_FOUND"):
            self.prove_evidence()
        self.assertEqual(self.files.calls, 0)

    def test_missing_evidence_and_bad_physical_file_fail_closed(self):
        self.evidence.source = None
        with self.assertRaisesRegex(StandardEvidenceError, "RESOURCE_NOT_FOUND"):
            self.prove_evidence()
        self.evidence.source = self.evidence_source
        self.files.error = True
        with self.assertRaisesRegex(StandardEvidenceError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.prove_evidence()

    def test_parsed_standard_node_is_fixed_and_fingerprinted(self):
        locator = json.loads(self.payload)["nodes"][0]["source_locator"]
        self.evidence.source = replace(
            self.evidence_source, source_parse_record_id=self.record_id,
            locator=locator,
            content_fingerprint=hashlib.sha256(b"Standard").digest(),
        )
        observed = self.prove_evidence()
        self.assertEqual(observed.source_parse_record_id, self.record_id)
        self.assertEqual(observed.content_fingerprint, hashlib.sha256(b"Standard").digest())
        self.assertIs(self.parses.calls[0][0], self.tx)
        self.parse_bytes.content = self.payload[:-1] + b"!"
        with self.assertRaisesRegex(StandardEvidenceError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.prove_evidence()

    def test_valid_hash_but_wrong_source_binding_is_rejected(self):
        payload = json.loads(self.payload)
        payload["source_sha256"] = (b"x" * 32).hex()
        changed = json.dumps(payload, separators=(",", ":")).encode()
        self.parse_bytes.content = changed
        self.parses.source = replace(
            self.parse_source, result_sha256=hashlib.sha256(changed).digest(),
            size_bytes=len(changed),
        )
        with self.assertRaisesRegex(GlobalStandardProofError, "PARSER_RESULT_INVALID"):
            self.prove_document(self.record_id)


if __name__ == "__main__":
    unittest.main()
