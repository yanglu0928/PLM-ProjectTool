from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
import unittest

from plm_assistant.modules.capability.application.read_capability import (
    CapabilityVersionView,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    VerifiedProjectEvidence,
)
from plm_assistant.modules.handover.application.create_version import (
    HandoverAnalysisItemDraft, HandoverItemOptionDraft,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverDocumentRef, ValidatedHandoverSourceSet,
)
from plm_assistant.modules.handover.application.validate_version import (
    HandoverVersionSnapshot, HandoverVersionValidationService,
)
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowActionLock, HandoverWorkflowQualificationLock,
    HandoverWorkflowQualificationOwner,
    HandoverWorkflowQualificationOwnerError,
    HandoverWorkflowQualificationQuery,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.trace.application.resolution_proof import (
    TraceResolutionProof,
)


class HandoverWorkflowQualificationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.project, self.analysis, self.version = uuid4(), uuid4(), uuid4()
        self.trace_id, self.item_id = uuid4(), uuid4()
        self.review_id, self.round_id = uuid4(), uuid4()
        self.source_doc, self.source_version = uuid4(), uuid4()
        self.response_doc, self.response_version = uuid4(), uuid4()
        self.source_evidence = uuid4()
        self.submit_evidence, self.verify_evidence = uuid4(), uuid4()
        self.capability, self.capability_version = uuid4(), uuid4()
        self.action_id = uuid4()
        item = HandoverAnalysisItemDraft(
            self.item_id, "NEED_CONFIRM", "Confirm scope",
            "Scope is unresolved", "Delivery may be delayed", "HIGH", "HIGH",
            "Confirm one option", "Which scope?",
            {"fields": [{"name": "scope", "format": "text",
                         "example": "Option A", "required": True}]},
            False, (self.source_evidence,), (),
            (HandoverItemOptionDraft("A", "Option A"),
             HandoverItemOptionDraft("B", "Option B")),
        )
        source = HandoverDocumentRef(self.source_doc, self.source_version)
        initial = HandoverVersionSnapshot(
            self.analysis, self.version, self.project, 1, "APPROVED",
            "sha256:" + "a" * 64, self.capability,
            self.capability_version, b"x" * 32, (source,), (item,), (),
        )
        self.snapshot = replace(
            initial, content_fingerprint=canonical_payload_fingerprint(
                HandoverVersionValidationService._snapshot_payload(initial)
            ),
        )
        self.action = HandoverWorkflowActionLock(
            self.action_id, self.project, self.version, self.item_id,
            "VERIFIED", 3,
            (HandoverDocumentRef(
                self.response_doc, self.response_version,
            ),),
            (self.submit_evidence,), (self.verify_evidence,), None,
        )
        self.lock = HandoverWorkflowQualificationLock(
            self.snapshot, "ACTIVE", 4, self.version,
            self.review_id, self.round_id,
            ((self.item_id, "CONFIRMED"),), (self.action,),
        )
        self.repository = Mock()
        self.sources = Mock()
        self.documents = Mock()
        self.evidence = Mock()
        self.capabilities = Mock()
        self.ai_tasks = Mock()
        self.reviews = Mock()
        self.traces = Mock()
        self.repository.lock_current.return_value = self.lock
        self.sources.validate.side_effect = self._validate_sources
        self.documents.prove.side_effect = self._prove_document
        self.evidence.prove.side_effect = self._prove_evidence
        self.capabilities.get_version.return_value = CapabilityVersionView(
            self.capability_version, self.capability, 1, "APPROVED",
            "sha256:" + "b" * 64, "sha256:" + "c" * 64,
            0, 0, 0, None, None, None, self.now,
        )
        self.capabilities.list_items.return_value = ()
        reviewer = uuid4()
        progress = ReviewRoundProgress(
            self.round_id, self.now, (reviewer,),
        ).record_decision(ReviewDecisionSnapshot(
            uuid4(), self.round_id, reviewer,
            ReviewDecisionKind.APPROVE, self.now,
        ))
        self.identity = ReviewIdentitySnapshot(
            self.review_id, "PROJECT", self.project, "HND-02",
            self.analysis, "HANDOVER_ALL_V1", "APPROVED", None, 2,
        )
        self.fixed = FixedReviewRoundSnapshot(
            self.identity, 1, self.version, uuid4(), progress, (uuid4(),), 1,
            uuid4(), self.snapshot.content_fingerprint, 1, self.now, (),
            uuid4(), self.now, self.now,
        )
        self.reviews.get_review.return_value = self.identity
        self.reviews.get_round.return_value = self.fixed
        self.owner = HandoverWorkflowQualificationOwner(
            repository=self.repository, sources=self.sources,
            documents=self.documents, evidence=self.evidence,
            capabilities=self.capabilities, ai_tasks=self.ai_tasks,
            reviews=self.reviews, trace_proofs=self.traces,
            clock=lambda: self.now,
        )
        self.tx = object()

    def query(self, item_key="HANDOVER_ISSUES"):
        return HandoverWorkflowQualificationQuery(
            b"s" * 32, self.trace_id, self.project, self.analysis, item_key,
        )

    def _validate_sources(self, _tx, *, project_id, references):
        self.assertEqual(project_id, self.project)
        ordered = tuple(sorted(
            references, key=lambda value: str(value.document_version_id),
        ))
        if references == self.snapshot.source_documents:
            source_ref = self.snapshot.source_set_ref
        else:
            source_ref = "sha256:" + "d" * 64
        return ValidatedHandoverSourceSet(source_ref, ordered)

    def _prove_document(self, _tx, query, *, document_id,
                        document_version_id, parse_record_id=None):
        self.assertEqual(query.project_id, self.project)
        self.assertIsNone(parse_record_id)
        return VerifiedFixedSource(DocumentEvidenceSourceFacts(
            document_id, document_version_id, "PROJECT", self.project,
            "CONTRACT", "ACTIVE", "f" * 64,
        ))

    def _prove_evidence(self, _tx, query, evidence_id):
        self.assertEqual(query.project_id, self.project)
        pairs = {
            self.source_evidence: (self.source_doc, self.source_version),
            self.submit_evidence: (self.response_doc, self.response_version),
            self.verify_evidence: (self.response_doc, self.response_version),
        }
        document_id, version_id = pairs[evidence_id]
        return VerifiedProjectEvidence(
            evidence_id, self.project, document_id, version_id,
            None, 2, bytes(str(evidence_id), "ascii")[:32].ljust(32, b"x"),
        )

    def test_qualifies_both_fixed_items_from_current_owner_facts(self):
        issues = self.owner.qualify_in_transaction(self.tx, self.query())
        baseline = self.owner.qualify_in_transaction(
            self.tx, self.query("HANDOVER_BASELINE"),
        )
        self.assertEqual(issues.item_key, "HANDOVER_ISSUES")
        self.assertEqual(baseline.item_key, "HANDOVER_BASELINE")
        self.assertEqual(
            tuple(value.evidence_id for value in issues.evidence),
            (self.source_evidence, self.submit_evidence,
             self.verify_evidence),
        )
        self.assertEqual(issues.review.review_round_id, self.round_id)
        self.assertEqual(self.documents.prove.call_count, 4)

    def test_missing_or_nonformal_handover_fails_closed(self):
        for value in (
            None,
            replace(self.lock, analysis_state="ARCHIVED"),
            replace(self.lock, item_states=((self.item_id, "CANDIDATE"),)),
        ):
            self.repository.lock_current.return_value = value
            with self.subTest(value=value), self.assertRaises(
                    HandoverWorkflowQualificationOwnerError):
                self.owner.qualify_in_transaction(self.tx, self.query())

    def test_review_must_be_current_approved_exact_subject(self):
        for identity, fixed in (
            (replace(self.identity, subject_id=uuid4()), self.fixed),
            (self.identity, replace(
                self.fixed, subject_fingerprint=b"z" * 32,
            )),
        ):
            self.reviews.get_review.return_value = identity
            self.reviews.get_round.return_value = fixed
            with self.subTest(identity=identity), self.assertRaises(
                    HandoverWorkflowQualificationOwnerError):
                self.owner.qualify_in_transaction(self.tx, self.query())

    def test_document_or_capability_drift_fails_closed(self):
        self.documents.prove.side_effect = RuntimeError("missing file")
        with self.assertRaises(HandoverWorkflowQualificationOwnerError):
            self.owner.qualify_in_transaction(self.tx, self.query())
        self.documents.prove.side_effect = self._prove_document
        self.capabilities.get_version.return_value = None
        with self.assertRaises(HandoverWorkflowQualificationOwnerError):
            self.owner.qualify_in_transaction(self.tx, self.query())

    def test_evidence_must_resolve_to_its_fixed_document_set(self):
        self.evidence.prove.return_value = VerifiedProjectEvidence(
            self.source_evidence, self.project, uuid4(), uuid4(),
            None, 1, b"e" * 32,
        )
        self.evidence.prove.side_effect = None
        with self.assertRaises(HandoverWorkflowQualificationOwnerError):
            self.owner.qualify_in_transaction(self.tx, self.query())

    def test_open_duplicate_prevents_issue_qualification(self):
        opened = replace(
            self.action, action_item_id=uuid4(), action_state="OPEN",
            lock_version=0, response_documents=(),
            submission_evidence_refs=(), verification_evidence_refs=(),
        )
        self.repository.lock_current.return_value = replace(
            self.lock, actions=(self.action, opened),
        )
        with self.assertRaises(HandoverWorkflowQualificationOwnerError):
            self.owner.qualify_in_transaction(self.tx, self.query())

    def test_closed_action_requires_current_resolution_trace_proof(self):
        resolution = uuid4()
        closed = replace(
            self.action, action_state="CLOSED", lock_version=4,
            resolution_trace_ref=resolution,
        )
        self.repository.lock_current.return_value = replace(
            self.lock, actions=(closed,),
        )
        self.traces.prove.return_value = TraceResolutionProof(
            resolution, Mock(),
        )
        self.owner.qualify_in_transaction(self.tx, self.query())
        self.traces.prove.assert_called_once()
        self.traces.prove.side_effect = RuntimeError("revoked")
        with self.assertRaises(HandoverWorkflowQualificationOwnerError):
            self.owner.qualify_in_transaction(self.tx, self.query())

    def test_nonblocking_closed_action_does_not_expand_trace_gate(self):
        resolution = uuid4()
        item = replace(
            self.snapshot.items[0], item_type="GAP",
            evidence_refs=(self.source_evidence,), options=(),
            confirmation_question=None, required_input_spec={},
        )
        initial = replace(self.snapshot, items=(item,))
        snapshot = replace(
            initial, content_fingerprint=canonical_payload_fingerprint(
                HandoverVersionValidationService._snapshot_payload(initial)
            ),
        )
        closed = replace(
            self.action, action_state="CLOSED", lock_version=4,
            resolution_trace_ref=resolution,
        )
        self.repository.lock_current.return_value = replace(
            self.lock, snapshot=snapshot, actions=(closed,),
        )
        self.fixed = replace(
            self.fixed, subject_fingerprint=snapshot.content_fingerprint,
        )
        self.reviews.get_round.return_value = self.fixed
        self.owner.qualify_in_transaction(self.tx, self.query())
        self.traces.prove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
