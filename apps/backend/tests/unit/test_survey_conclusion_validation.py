from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.survey_conclusion_task import (
    SurveyConclusionAITaskProof,
)
from plm_assistant.modules.handover.application.survey_conclusion_issue import (
    SurveyConclusionIssueProof,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, canonical_payload_fingerprint,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordProof, ConclusionResponseProof,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionEvidenceInput, ConclusionOpenIssueInput, CreateSurveyConclusion,
    DepartmentConclusionInput, ModuleConclusionInput,
    SurveyConclusionCreateService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    ConclusionValidationAudit, ConclusionValidationSnapshot,
    SurveyConclusionCurrentValidator, SurveyConclusionValidationError,
    SurveyConclusionValidationService, ValidateSurveyConclusion,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
ACTOR, PROJECT, SURVEY, ROUND, CONCLUSION, SERIES = (
    uuid.uuid4() for _ in range(6))
DEPARTMENT, RESPONSE, ANSWER, ASSIGNMENT, QUESTION = (
    uuid.uuid4() for _ in range(5))
EVIDENCE, DOCUMENT, DOCUMENT_VERSION = (uuid.uuid4() for _ in range(3))
ACTION, AI_TASK, INVOCATION, SUGGESTION = (uuid.uuid4() for _ in range(4))


RESPONSE_PROOF = ConclusionResponseProof(
    RESPONSE, ANSWER, ASSIGNMENT, ROUND, SURVEY, uuid.uuid4(), PROJECT,
    DEPARTMENT, QUESTION, "SELF_SERVICE", b"r" * 32, (EVIDENCE,),
)
EVIDENCE_PROOF = ConclusionProjectRecordProof(
    EVIDENCE, PROJECT, DOCUMENT, DOCUMENT_VERSION, 4, b"e" * 32, ACTOR,
)
ISSUE_PROOF = SurveyConclusionIssueProof(
    ACTION, PROJECT, "PROVIDE_INFO", "CLOSED", 3, NOW,
)
AI_PROOF = SurveyConclusionAITaskProof(
    AI_TASK, PROJECT, INVOCATION, SUGGESTION, b"a" * 32,
    completed_at=NOW,
)
COMMAND = ValidateSurveyConclusion(
    b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, CONCLUSION,
    str(uuid.uuid4()),
)


def snapshot(*, roles=("SUPPORT",), issues=(ISSUE_PROOF,), blocking=(True,),
             rounds_current=True, ordinals=True, formal=0,
             declared=(1, 1, 1, 1), fingerprint=None,
             response_refs=(RESPONSE,)):
    value = ConclusionValidationSnapshot(
        CONCLUSION, SERIES, PROJECT, SURVEY, (ROUND,), (AI_TASK,), 1,
        "DRAFT", b"x" * 32, *declared, None,
        (DepartmentConclusionInput(
            DEPARTMENT, "Department", "Finding", response_refs,
        ),),
        (ModuleConclusionInput(
            "PLM.BOM", "Module", "Finding", response_refs,
        ),),
        (EVIDENCE_PROOF,), roles, issues, blocking, rounds_current, ordinals,
        formal,
    )
    create = CreateSurveyConclusion(
        b"x" * 32, b"x" * 32, CONCLUSION, PROJECT, SURVEY, (ROUND,),
        value.departments, value.modules,
        tuple(ConclusionEvidenceInput(item.evidence_id, role)
              for item, role in zip(value.evidence, roles, strict=True)),
        tuple(ConclusionOpenIssueInput(item.action_item_id, flag)
              for item, flag in zip(issues, blocking, strict=True)),
        (AI_TASK,), None, "x" * 16,
    )
    expected = canonical_payload_fingerprint(
        SurveyConclusionCreateService._snapshot_payload(
            create, (() if not response_refs else (RESPONSE_PROOF,)),
            value.evidence, value.issues, (AI_PROOF,),
        ))
    return replace(value, content_fingerprint=(
        expected if fingerprint is None else fingerprint))


class ResponseOwner:
    proof = RESPONSE_PROOF

    def prove(self, transaction, **kwargs):
        return self.proof


class EvidenceOwner:
    proof = EVIDENCE_PROOF

    def prove(self, transaction, query):
        return self.proof


class IssueOwner:
    proof = ISSUE_PROOF

    def prove(self, transaction, **kwargs):
        return self.proof


class AIOwner:
    proof = AI_PROOF

    def prove(self, transaction, **kwargs):
        return self.proof


def validator(**changes):
    values = {
        "response_owner": ResponseOwner(), "evidence_owner": EvidenceOwner(),
        "issue_owner": IssueOwner(), "ai_owner": AIOwner(),
    }
    values.update(changes)
    return SurveyConclusionCurrentValidator(**values)


class Tx:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs):
        return ACTOR


class Guard:
    def require_valid(self, **kwargs):
        return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(
            ACTOR, PROJECT, "SURVEY_CONCLUSION_VALIDATE",
            "IMPLEMENTATION_MEMBER",
        )


class Repository:
    value = snapshot()

    def lock_snapshot(self, transaction, **kwargs):
        return self.value


class Receipts:
    replay = None
    completed = []

    def reserve(self, transaction, **kwargs):
        self.scope = kwargs["scope"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.completed.append(kwargs["result"])


class Audit:
    event = None
    event_id = uuid.uuid4()

    def append(self, transaction, event):
        type(self).event = event
        return self.event_id


class AuditSource:
    def get(self, transaction, **kwargs):
        if Audit.event is None:
            return None
        return ConclusionValidationAudit(
            Audit.event_id, Audit.event.trace_id, NOW, Audit.event.reason_code,
        )


class SurveyConclusionValidationTests(unittest.TestCase):
    def setUp(self):
        Tx.commits, Receipts.replay, Receipts.completed = 0, None, []
        Audit.event, Audit.event_id = None, uuid.uuid4()

    def test_valid_current_sources_pass(self):
        facts = validator().current_facts(object(), COMMAND, snapshot())
        self.assertEqual((), facts.issues)
        self.assertEqual((1, 1, 0, 0), (
            facts.response_count, facts.support_evidence_count,
            facts.conflict_evidence_count,
            facts.current_open_blocking_issue_count,
        ))

    def test_conflict_and_open_blocking_issue_fail_closed(self):
        open_issue = replace(ISSUE_PROOF, action_state="OPEN", lock_version=2)
        current = IssueOwner()
        current.proof = open_issue
        value = snapshot(
            roles=("CONFLICT",),
            issues=(replace(open_issue, action_state="OPEN", lock_version=2),),
            response_refs=(),
        )
        # Rebuild the root fingerprint from the creation-time OPEN snapshot.
        facts = validator(issue_owner=current).current_facts(object(), COMMAND, value)
        self.assertIn("CONFLICT_EVIDENCE_PRESENT", facts.issues)
        self.assertIn("BLOCKING_OPEN_ISSUE", facts.issues)
        self.assertIn("SOURCE_COVERAGE_MISSING", facts.issues)
        self.assertEqual(1, facts.current_open_blocking_issue_count)

    def test_source_drift_and_integrity_are_distinguished(self):
        evidence = EvidenceOwner()
        evidence.proof = replace(EVIDENCE_PROOF, observed_evidence_lock_version=5)
        ai = AIOwner()
        ai.proof = None
        facts = validator(evidence_owner=evidence, ai_owner=ai).current_facts(
            object(), COMMAND, snapshot(rounds_current=False),
        )
        self.assertIn("ROUND_UNAVAILABLE", facts.issues)
        self.assertIn("EVIDENCE_UNAVAILABLE", facts.issues)
        self.assertIn("AI_PROVENANCE_UNAVAILABLE", facts.issues)
        self.assertNotIn("CONTENT_FINGERPRINT_MISMATCH", facts.issues)
        tampered = validator().current_facts(
            object(), COMMAND, snapshot(fingerprint=b"z" * 32),
        )
        self.assertIn("CONTENT_FINGERPRINT_MISMATCH", tampered.issues)

    def test_counts_and_unverified_formal_decision_fail(self):
        facts = validator().current_facts(
            object(), COMMAND,
            snapshot(declared=(2, 1, 1, 1), ordinals=False, formal=1),
        )
        self.assertIn("COUNT_MISMATCH", facts.issues)
        self.assertIn("FORMAL_DECISION_UNVERIFIED", facts.issues)

    def test_service_is_atomic_audited_receipted_and_does_not_change_state(self):
        service = SurveyConclusionValidationService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repository(),
            response_owner=ResponseOwner(), evidence_owner=EvidenceOwner(),
            issue_owner=IssueOwner(), ai_owner=AIOwner(),
            audit_source=AuditSource(), receipts=Receipts(), audit=Audit(),
            clock=lambda: NOW,
        )
        report = service.validate(COMMAND)
        self.assertTrue(report.valid)
        self.assertEqual("DRAFT", report.conclusion_state)
        self.assertEqual("DRAFT", Audit.event.before_state)
        self.assertEqual("DRAFT", Audit.event.after_state)
        self.assertEqual("SURVEY_CONCLUSION_VALIDATED", Audit.event.action)
        self.assertEqual(1, Tx.commits)
        self.assertEqual("V1_SURVEY_CONCLUSION_VALIDATE",
                         Receipts.completed[0].ref_type)

    def test_replay_uses_original_audit_without_new_source_checks(self):
        Audit.event = type("Event", (), {
            "trace_id": COMMAND.trace_id,
            "reason_code": "CONCLUSION_VALIDATION_PASSED__1_1_0_0",
        })()
        Receipts.replay = IdempotencyResult(
            "V1_SURVEY_CONCLUSION_VALIDATE", Audit.event_id, 200,
        )
        response = ResponseOwner()
        response.proof = None
        service = SurveyConclusionValidationService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repository(),
            response_owner=response, evidence_owner=EvidenceOwner(),
            issue_owner=IssueOwner(), ai_owner=AIOwner(),
            audit_source=AuditSource(), receipts=Receipts(), audit=Audit(),
            clock=lambda: NOW,
        )
        self.assertTrue(service.validate(COMMAND).valid)
        self.assertEqual(0, Tx.commits)

    def test_invalid_secrets_and_key_are_redacted(self):
        service = SurveyConclusionValidationService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repository(),
            response_owner=ResponseOwner(), evidence_owner=EvidenceOwner(),
            issue_owner=IssueOwner(), ai_owner=AIOwner(),
            audit_source=AuditSource(), receipts=Receipts(), audit=Audit(),
        )
        for changed in ({"session_token": b"short"},
                        {"csrf_token": b"short"},
                        {"survey_conclusion_id": uuid.UUID(int=0)}):
            with self.subTest(changed=changed), self.assertRaises(
                    SurveyConclusionValidationError) as raised:
                service.validate(replace(COMMAND, **changed))
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        rendered = repr(COMMAND)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(COMMAND.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
