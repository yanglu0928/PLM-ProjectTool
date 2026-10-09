from __future__ import annotations

import dataclasses
import unittest
import uuid

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.solution.application.prove_section_document_content import (
    SectionDocumentContentProof,
)
from plm_assistant.modules.solution.application.prove_section_evidence_use import (
    SectionEvidenceUseProof,
)
from plm_assistant.modules.solution.application.prove_section_version_input import (
    SectionVersionInputProofError,
    SectionVersionInputProofService,
)
from plm_assistant.modules.solution.application.section_version_base import (
    CurrentSectionVersionBase,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
    SectionVersionDraftInput,
)


PROJECT = uuid.uuid4()
OUTLINE = uuid.uuid4()
SECTION = uuid.uuid4()
DOCUMENT = uuid.uuid4()
DOCUMENT_VERSION = uuid.uuid4()
REQUIREMENT = uuid.uuid4()
REQUIREMENT_VERSION = uuid.uuid4()
EVIDENCE = uuid.uuid4()
TRACE = uuid.uuid4()
SESSION = b"s" * 32


def draft(**overrides):
    values = dict(project_id=PROJECT, solution_section_id=SECTION,
                  title="Implementation", content_document_version_ref=DOCUMENT_VERSION,
                  content_artifact_ref=None,
                  requirement_refs=(SectionRequirementRef(REQUIREMENT, REQUIREMENT_VERSION),),
                  evidence_ids=(EVIDENCE,), assumptions=({"assumption": "a"},),
                  exclusions=())
    values.update(overrides)
    return SectionVersionDraftInput(**values)


class _Port:
    def __init__(self, result, name, calls):
        self.result = result
        self.name = name
        self.calls = calls

    def current(self, transaction, **kwargs):
        self.calls.append((self.name, transaction, kwargs))
        return self.result

    def prove(self, transaction, **kwargs):
        self.calls.append((self.name, transaction, kwargs))
        return self.result


class SectionVersionInputProofTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.transaction = object()
        self.base = CurrentSectionVersionBase(PROJECT, OUTLINE, SECTION, 1, None, 3, 4)
        self.document = SectionDocumentContentProof(
            PROJECT, DOCUMENT, DOCUMENT_VERSION, b"d" * 32)
        self.requirement = OutlineApprovedRequirementProof(
            PROJECT, REQUIREMENT, REQUIREMENT_VERSION, 2, b"r" * 32,
            uuid.uuid4(), uuid.uuid4())
        self.evidence = SectionEvidenceUseProof(
            EVIDENCE, PROJECT, DOCUMENT, DOCUMENT_VERSION, 5, b"e" * 32)
        self.bases = _Port(self.base, "base", self.calls)
        self.documents = _Port(self.document, "document", self.calls)
        self.requirements = _Port(self.requirement, "requirement", self.calls)
        self.evidences = _Port(self.evidence, "evidence", self.calls)
        self.service = SectionVersionInputProofService(
            bases=self.bases, documents=self.documents,
            requirements=self.requirements, evidence=self.evidences)

    def prove(self, value=None, **overrides):
        values = dict(transaction=self.transaction, session_token=SESSION,
                      trace_id=TRACE, draft=draft() if value is None else value)
        values.update(overrides)
        return self.service.prove(**values)

    def denied(self, code="SOURCE_UNAVAILABLE", value=None, **overrides):
        with self.assertRaises(SectionVersionInputProofError) as captured:
            self.prove(value, **overrides)
        self.assertEqual(captured.exception.code, code)

    def test_same_transaction_order_and_minimal_proven_projection(self):
        proven = self.prove()
        self.assertEqual([name for name, _, _ in self.calls],
                         ["base", "document", "requirement", "evidence"])
        self.assertTrue(all(tx is self.transaction for _, tx, _ in self.calls))
        self.assertEqual(self.calls[0][2],
                         {"project_id": PROJECT, "section_id": SECTION})
        self.assertEqual(self.calls[1][2]["session_token"], SESSION)
        self.assertEqual(self.calls[3][2]["trace_id"], TRACE)
        self.assertEqual(proven.base, self.base)
        self.assertEqual(proven.document, self.document)
        self.assertEqual(proven.requirements, (self.requirement,))
        self.assertEqual(proven.evidence, (self.evidence,))
        self.assertEqual(len(proven.content_fingerprint), 32)
        self.assertNotIn("Implementation", repr(proven))

    def test_fingerprint_binds_input_version_and_current_source_facts(self):
        first = self.prove().content_fingerprint
        self.calls.clear()
        self.assertEqual(self.prove().content_fingerprint, first)
        self.assertNotEqual(self.prove(draft(title="Changed")).content_fingerprint,
                            first)
        self.bases.result = dataclasses.replace(self.base, next_version_no=2,
                                                supersedes_version_id=uuid.uuid4())
        self.assertNotEqual(self.prove().content_fingerprint, first)
        self.bases.result = self.base
        self.documents.result = dataclasses.replace(
            self.document, content_sha256=b"x" * 32)
        self.assertNotEqual(self.prove().content_fingerprint, first)
        self.documents.result = self.document
        self.requirements.result = dataclasses.replace(
            self.requirement, content_fingerprint=b"x" * 32)
        self.assertNotEqual(self.prove().content_fingerprint, first)
        self.requirements.result = self.requirement
        self.evidences.result = dataclasses.replace(
            self.evidence, observed_lock_version=6)
        self.assertNotEqual(self.prove().content_fingerprint, first)

    def test_invalid_input_and_artifact_fail_before_ports(self):
        for overrides in (dict(transaction=None), dict(session_token=b"short"),
                          dict(session_token="wrong"),
                          dict(trace_id=uuid.UUID(int=0))):
            with self.subTest(overrides=overrides):
                self.denied("VALIDATION_FAILED", **overrides)
        self.denied("VALIDATION_FAILED", draft(title=""))
        self.denied(value=draft(content_document_version_ref=None,
                                content_artifact_ref=uuid.uuid4()))
        self.assertEqual(self.calls, [])

    def test_missing_or_wrong_base_fails_closed(self):
        for wrong in (None, dataclasses.replace(self.base, project_id=uuid.uuid4()),
                      dataclasses.replace(self.base, solution_section_id=uuid.uuid4()),
                      dataclasses.replace(self.base, solution_outline_id=uuid.UUID(int=0)),
                      dataclasses.replace(self.base, next_version_no=0),
                      dataclasses.replace(self.base, outline_lock_version=-1),
                      dataclasses.replace(self.base, section_lock_version=-1),
                      dataclasses.replace(self.base, supersedes_version_id=uuid.uuid4()),
                      dataclasses.replace(self.base, next_version_no=2)):
            with self.subTest(wrong=wrong):
                self.bases.result = wrong
                self.denied()
        self.assertTrue(all(name == "base" for name, _, _ in self.calls))

    def test_wrong_document_requirement_evidence_fail_closed(self):
        for wrong in (None,
                      dataclasses.replace(self.document, project_id=uuid.uuid4()),
                      dataclasses.replace(self.document, document_version_id=uuid.uuid4()),
                      dataclasses.replace(self.document, content_sha256=b"short")):
            with self.subTest(wrong=wrong):
                self.documents.result = wrong
                self.denied()
        self.documents.result = self.document
        for wrong in (None,
                      dataclasses.replace(self.requirement, project_id=uuid.uuid4()),
                      dataclasses.replace(self.requirement,
                                          requirement_version_id=uuid.uuid4()),
                      dataclasses.replace(self.requirement, version_no=0),
                      dataclasses.replace(self.requirement, review_id=uuid.UUID(int=0)),
                      dataclasses.replace(self.requirement, content_fingerprint=b"short")):
            with self.subTest(wrong=wrong):
                self.requirements.result = wrong
                self.denied()
        self.requirements.result = self.requirement
        for wrong in (None,
                      dataclasses.replace(self.evidence, project_id=uuid.uuid4()),
                      dataclasses.replace(self.evidence, evidence_id=uuid.uuid4()),
                      dataclasses.replace(self.evidence, document_version_id=uuid.UUID(int=0)),
                      dataclasses.replace(self.evidence, observed_lock_version=-1),
                      dataclasses.replace(self.evidence, content_fingerprint=b"short")):
            with self.subTest(wrong=wrong):
                self.evidences.result = wrong
                self.denied()

    def test_zero_requirements_evidence_and_upstream_exception(self):
        value = self.prove(draft(requirement_refs=(), evidence_ids=()))
        self.assertEqual((value.requirements, value.evidence), ((), ()))
        self.assertEqual([name for name, _, _ in self.calls], ["base", "document"])

        def fail(*_args, **_kwargs):
            raise RuntimeError("private source locator")
        self.documents.prove = fail
        self.denied()


if __name__ == "__main__":
    unittest.main()
