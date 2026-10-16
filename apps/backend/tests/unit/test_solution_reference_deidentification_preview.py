from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.preview_reference_deidentification import (
    PreviewReferenceDeidentification, ReferenceDeidentificationPreviewError,
    ReferenceDeidentificationPreviewService,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    ProvenReferenceSources, ReferenceSourceError, ReferenceSourceRequest,
    VerifiedReferenceDocument, VerifiedReferenceEvidence,
)


ADMIN, DOCUMENT, VERSION, EVIDENCE = (uuid.uuid4() for _ in range(4))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        raise AssertionError("Preview must not commit or create a record")


class Access:
    actor = ADMIN
    calls = 0

    def authorized_admin(self, tx, *, session_token, csrf_token, now):
        self.calls += 1
        assert type(tx) is Tx and session_token == b"s" * 32
        assert csrf_token == b"c" * 32 and now == NOW
        return self.actor


class Guard:
    denied = False

    def require_valid(self, *, trace_id):
        assert type(trace_id) is uuid.UUID
        if self.denied:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class Sources:
    result = ProvenReferenceSources(
        "GLOBAL", None,
        (VerifiedReferenceDocument(DOCUMENT, VERSION, "GLOBAL", None,
                                   "REFERENCE_MATERIAL", b"d" * 32),),
        (VerifiedReferenceEvidence(EVIDENCE, VERSION, "GLOBAL", None,
                                   b"e" * 32),), b"f" * 32,
    )
    calls = 0

    def prove_sources(self, tx, request):
        self.calls += 1
        assert type(tx) is Tx and request.scope == "GLOBAL"
        return self.result


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.sources = Access(), Guard(), Sources()
        self.service = ReferenceDeidentificationPreviewService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            sources=self.sources, clock=lambda: NOW,
        )
        self.request = ReferenceSourceRequest(
            b"s" * 32, uuid.uuid4(), "GLOBAL", None, (VERSION,), (EVIDENCE,),
            "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
        )
        self.command = PreviewReferenceDeidentification(self.request, b"c" * 32)

    def rejects(self, code, command=None):
        with self.assertRaises(ReferenceDeidentificationPreviewError) as caught:
            self.service.preview(command or self.command)
        self.assertEqual(code, caught.exception.code)

    def test_current_global_source_projection_has_no_write_port(self):
        view = self.service.preview(self.command)
        self.assertEqual(b"f" * 32, view.source_fingerprint)
        self.assertEqual((DOCUMENT,), tuple(item.document_id for item in view.document_refs))
        self.assertEqual((VERSION,), tuple(item.document_version_id for item in view.document_refs))
        self.assertEqual((EVIDENCE,), view.evidence_ids)
        self.assertEqual(NOW, view.previewed_at)
        self.assertNotIn((b"f" * 32).hex(), repr(view))
        self.assertEqual(1, self.sources.calls)

    def test_invalid_scope_session_or_csrf_fails_before_proof(self):
        for command in (
            replace(self.command, sources=replace(self.request, scope="PROJECT")),
            replace(self.command, sources=replace(self.request, session_token=b"x")),
            replace(self.command, csrf_token=b"x"),
        ):
            with self.subTest(command=command):
                self.rejects("VALIDATION_FAILED", command)
        self.assertEqual(0, self.sources.calls)

    def test_admin_license_and_source_errors_fail_closed(self):
        self.access.actor = None
        self.rejects("AUTH_ACCESS_DENIED")
        self.access.actor = ADMIN
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED")
        self.guard.denied = False
        self.sources.result = replace(self.sources.result, scope="PROJECT")
        self.rejects("SOLUTION_UNAVAILABLE")
        self.sources.result = replace(self.sources.result,
            document_versions=(replace(self.sources.result.document_versions[0],
                                       document_id=uuid.UUID(int=0)),))
        self.rejects("SOLUTION_UNAVAILABLE")

    def test_source_port_error_is_sanitized(self):
        class Unavailable:
            def prove_sources(self, tx, request):
                raise ReferenceSourceError("RESOURCE_NOT_FOUND")
        service = ReferenceDeidentificationPreviewService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            sources=Unavailable(), clock=lambda: NOW)
        with self.assertRaises(ReferenceDeidentificationPreviewError) as caught:
            service.preview(self.command)
        self.assertEqual("RESOURCE_NOT_FOUND", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
