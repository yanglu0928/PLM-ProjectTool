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
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordProof, ConclusionResponseProof,
)
from plm_assistant.modules.survey.application.conclusion_views import (
    ConclusionEvidenceView, ConclusionOpenIssueView, DepartmentConclusionView,
    ModuleConclusionView, SurveyConclusionSummaryView, SurveyConclusionView,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionCreatePlan, ConclusionEvidenceInput, ConclusionOpenIssueInput,
    CreateSurveyConclusion, DepartmentConclusionInput, ModuleConclusionInput,
    SurveyConclusionCreateError, SurveyConclusionCreateService,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
ACTOR, PROJECT, SURVEY, ROUND, DEPARTMENT = (uuid.uuid4() for _ in range(5))
RESPONSE, ANSWER, ASSIGNMENT, QUESTION = (uuid.uuid4() for _ in range(4))
EVIDENCE, DOCUMENT, DOCUMENT_VERSION = (uuid.uuid4() for _ in range(3))
ACTION, AI_TASK, INVOCATION, SUGGESTION = (uuid.uuid4() for _ in range(4))


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
            ACTOR, PROJECT, "SURVEY_CONCLUSION_CREATE", "IMPLEMENTATION_MEMBER",
        )


class ResponseOwner:
    def prove(self, transaction, **kwargs):
        return ConclusionResponseProof(
            RESPONSE, ANSWER, ASSIGNMENT, ROUND, SURVEY, uuid.uuid4(),
            PROJECT, DEPARTMENT, QUESTION, "SELF_SERVICE", b"r" * 32,
            (EVIDENCE,),
        )


class EvidenceOwner:
    def prove(self, transaction, query):
        return ConclusionProjectRecordProof(
            EVIDENCE, PROJECT, DOCUMENT, DOCUMENT_VERSION, 4,
            b"e" * 32, ACTOR,
        )


class IssueOwner:
    def prove(self, transaction, **kwargs):
        return SurveyConclusionIssueProof(
            ACTION, PROJECT, "PROVIDE_INFO", "OPEN", 2, NOW,
        )


class AIOwner:
    def prove(self, transaction, **kwargs):
        return SurveyConclusionAITaskProof(
            AI_TASK, PROJECT, INVOCATION, SUGGESTION, b"a" * 32,
            completed_at=NOW,
        )


def view(conclusion_id, series_id, command, *, version_no=1,
         fingerprint=b"f" * 32):
    summary = SurveyConclusionSummaryView(
        conclusion_id, series_id, PROJECT, SURVEY,
        tuple(sorted(command.round_refs, key=lambda value: value.int)),
        tuple(sorted(command.ai_task_refs, key=lambda value: value.int)),
        version_no, "DRAFT", fingerprint.hex(), 1, 1, 1, 1,
        command.supersedes_ref, None, None, ACTOR, NOW,
    )
    return SurveyConclusionView(
        summary,
        (DepartmentConclusionView(
            uuid.uuid4(), DEPARTMENT, "Department", "Department finding",
            (RESPONSE,), 0,
        ),),
        (ModuleConclusionView(
            uuid.uuid4(), "PLM.BOM", "Module", "Module finding",
            (RESPONSE,), 0,
        ),),
        (ConclusionEvidenceView(
            uuid.uuid4(), "SUPPORT", DOCUMENT, DOCUMENT_VERSION, EVIDENCE,
            4, (b"e" * 32).hex(), 0,
        ),),
        (ConclusionOpenIssueView(
            uuid.uuid4(), "handover", "HND-03", ACTION, "OPEN", 2, True, 0,
        ),),
    )


class Repository:
    def prepare(self, transaction, **kwargs):
        self.prepared = kwargs
        series = kwargs["proposed_series_id"]
        return ConclusionCreatePlan(
            kwargs["survey_conclusion_id"], series, PROJECT, SURVEY,
            kwargs["round_refs"], 1, kwargs["supersedes_ref"],
        )

    def create(self, transaction, snapshot):
        self.snapshot = snapshot
        return view(
            snapshot.plan.survey_conclusion_id,
            snapshot.plan.conclusion_series_id,
            COMMAND,
            fingerprint=snapshot.content_fingerprint,
        )

    def get_initial(self, transaction, **kwargs):
        return view(kwargs["survey_conclusion_id"], uuid.uuid4(), COMMAND)


class Receipts:
    replay = None
    completed = []

    def reserve(self, transaction, **kwargs):
        self.scope = kwargs["scope"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.completed.append(kwargs["result"])


class Audit:
    events = []

    def append(self, transaction, event):
        self.events.append(event)
        return uuid.uuid4()


COMMAND = CreateSurveyConclusion(
    b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, SURVEY, (ROUND,),
    (DepartmentConclusionInput(
        DEPARTMENT, "Department", "Department finding", (RESPONSE,),
    ),),
    (ModuleConclusionInput(
        "PLM.BOM", "Module", "Module finding", (RESPONSE,),
    ),),
    (ConclusionEvidenceInput(EVIDENCE, "SUPPORT"),),
    (ConclusionOpenIssueInput(ACTION, True),),
    (AI_TASK,), None, str(uuid.uuid4()),
)


class SurveyConclusionCreateTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0
        Receipts.replay, Receipts.completed = None, []
        Audit.events = []
        self.repository, self.receipts = Repository(), Receipts()
        self.service = SurveyConclusionCreateService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=self.repository,
            response_owner=ResponseOwner(), evidence_owner=EvidenceOwner(),
            issue_owner=IssueOwner(), ai_owner=AIOwner(),
            receipts=self.receipts, audit=Audit(), clock=lambda: NOW,
        )

    def test_create_is_proven_atomic_audited_and_receipted(self):
        result = self.service.create(COMMAND)
        snapshot = self.repository.snapshot
        self.assertEqual("DRAFT", result.summary.conclusion_state)
        self.assertEqual(1, Tx.commits)
        self.assertEqual(32, len(snapshot.content_fingerprint))
        self.assertEqual(RESPONSE, snapshot.response_proofs[0].response_id)
        self.assertEqual(EVIDENCE, snapshot.evidence_proofs[0].evidence_id)
        self.assertEqual(ACTION, snapshot.issue_proofs[0].action_item_id)
        self.assertEqual(AI_TASK, snapshot.ai_proofs[0].ai_task_id)
        self.assertEqual("SURVEY_CONCLUSION_CREATED", Audit.events[0].action)
        self.assertEqual("V1_SURVEY_CONCLUSION_CREATE",
                         self.receipts.scope.operation)
        self.assertEqual(
            IdempotencyResult(
                "V1_SURVEY_CONCLUSION_CREATE",
                result.summary.survey_conclusion_id, 201,
            ),
            Receipts.completed[0],
        )

    def test_replay_returns_original_without_new_proofs_or_commit(self):
        original = uuid.uuid4()
        Receipts.replay = IdempotencyResult(
            "V1_SURVEY_CONCLUSION_CREATE", original, 201,
        )
        result = self.service.create(COMMAND)
        self.assertEqual(original, result.summary.survey_conclusion_id)
        self.assertEqual(0, Tx.commits)
        self.assertFalse(hasattr(self.repository, "snapshot"))
        self.assertEqual([], Audit.events)

    def test_invalid_secret_identity_shape_and_formal_decision_gap_fail_closed(self):
        changes = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"round_refs": ()}, {"round_refs": (ROUND, ROUND)},
            {"department_conclusions": () , "module_conclusions": ()},
            {"evidence_refs": ()},
            {"module_conclusions": (ModuleConclusionInput(
                "bad key", "Module", "Finding", (),
            ),)},
            {"evidence_refs": (ConclusionEvidenceInput(EVIDENCE, "OTHER"),)},
            {"open_issue_refs": (ConclusionOpenIssueInput(ACTION, 1),)},
        )
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(
                    SurveyConclusionCreateError) as raised:
                self.service.create(replace(COMMAND, **changed))
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        rendered = repr(COMMAND)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(COMMAND.idempotency_key, rendered)

    def test_wrong_department_response_proof_is_rejected(self):
        class WrongResponse(ResponseOwner):
            def prove(self, transaction, **kwargs):
                return replace(super().prove(transaction, **kwargs),
                               department_id=uuid.uuid4())

        service = SurveyConclusionCreateService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repository(),
            response_owner=WrongResponse(), evidence_owner=EvidenceOwner(),
            issue_owner=IssueOwner(), ai_owner=AIOwner(),
            receipts=Receipts(), audit=Audit(), clock=lambda: NOW,
        )
        with self.assertRaisesRegex(
            SurveyConclusionCreateError, "SURVEY_CONCLUSION_SOURCE_INVALID",
        ):
            service.create(COMMAND)


if __name__ == "__main__":
    unittest.main()
