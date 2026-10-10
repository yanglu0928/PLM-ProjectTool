from __future__ import annotations

import dataclasses
import unittest
import uuid

from plm_assistant.modules.evidence.application.fixed_project_source import (
    VerifiedProjectEvidence,
)
from plm_assistant.modules.solution.application.prove_section_evidence_use import (
    SectionEvidenceUseError,
)
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import (
    SectionEvidenceUseProofAdapter,
)


EVIDENCE = uuid.uuid4()
PROJECT = uuid.uuid4()
DOCUMENT = uuid.uuid4()
VERSION = uuid.uuid4()
TRACE = uuid.uuid4()
ACTOR = uuid.uuid4()


class _Fixed:
    def __init__(self) -> None:
        self.result = VerifiedProjectEvidence(
            EVIDENCE, PROJECT, DOCUMENT, VERSION, None, 3, b"e" * 32,
            verified_by=ACTOR, verified_project_role="PROJECT_MANAGER",
            document_category="PROJECT_RECORD",
            original_display_name="sensitive-original-name.docx",
        )
        self.calls = []

    def prove(self, transaction, query, evidence_id):
        self.calls.append((transaction, query, evidence_id))
        return self.result


class SectionEvidenceUseProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixed = _Fixed()
        self.adapter = SectionEvidenceUseProofAdapter(fixed_sources=self.fixed)
        self.transaction = object()

    def prove(self, **overrides):
        values = dict(transaction=self.transaction, session_token=b"s" * 32,
                      trace_id=TRACE, project_id=PROJECT, evidence_id=EVIDENCE)
        values.update(overrides)
        return self.adapter.prove(**values)

    def denied(self, code="EVIDENCE_UNAVAILABLE", **overrides) -> None:
        with self.assertRaises(SectionEvidenceUseError) as captured:
            self.prove(**overrides)
        self.assertEqual(captured.exception.code, code)

    def test_uses_same_transaction_and_minimal_projection(self) -> None:
        result = self.prove()
        self.assertEqual(result.evidence_id, EVIDENCE)
        self.assertEqual(result.project_id, PROJECT)
        self.assertEqual(result.document_version_id, VERSION)
        self.assertEqual(result.observed_lock_version, 3)
        self.assertEqual(result.content_fingerprint, b"e" * 32)
        self.assertNotIn("sensitive-original-name", repr(result))
        self.assertFalse(hasattr(result, "original_display_name"))
        self.assertIs(self.fixed.calls[0][0], self.transaction)
        self.assertEqual(self.fixed.calls[0][1].session_token, b"s" * 32)
        self.assertEqual(self.fixed.calls[0][1].project_id, PROJECT)
        self.assertEqual(self.fixed.calls[0][2], EVIDENCE)

    def test_implementation_member_is_allowed(self) -> None:
        self.fixed.result = dataclasses.replace(
            self.fixed.result, verified_project_role="IMPLEMENTATION_MEMBER")
        self.assertEqual(self.prove().evidence_id, EVIDENCE)

    def test_invalid_input_does_not_call_evidence(self) -> None:
        for overrides in (
            dict(transaction=None), dict(session_token=b"short"),
            dict(session_token="not bytes"), dict(trace_id=uuid.UUID(int=0)),
            dict(project_id=uuid.UUID(int=0)), dict(evidence_id=None),
        ):
            with self.subTest(overrides=overrides):
                self.denied("VALIDATION_FAILED", **overrides)
        self.assertEqual(self.fixed.calls, [])

    def test_cross_project_state_role_and_fingerprint_fail_closed(self) -> None:
        base = self.fixed.result
        for changed in (
            None,
            dataclasses.replace(base, evidence_id=uuid.uuid4()),
            dataclasses.replace(base, project_id=uuid.uuid4()),
            dataclasses.replace(base, scope="GLOBAL"),
            dataclasses.replace(base, observed_state="REVOKED"),
            dataclasses.replace(base, verified_by=None),
            dataclasses.replace(base, verified_project_role="CUSTOMER_MEMBER"),
            dataclasses.replace(base, document_id=uuid.UUID(int=0)),
            dataclasses.replace(base, observed_lock_version=-1),
            dataclasses.replace(base, content_fingerprint=b"short"),
        ):
            with self.subTest(changed=changed):
                self.fixed.result = changed
                self.denied()

    def test_upstream_error_is_sanitized(self) -> None:
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("private parse locator")
        self.fixed.prove = unavailable
        self.denied()


if __name__ == "__main__":
    unittest.main()
