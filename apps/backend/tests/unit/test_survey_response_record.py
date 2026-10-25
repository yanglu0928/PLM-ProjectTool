from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.survey.application.record_response import (
    RecordSurveyResponse, SurveyResponseRecordError, SurveyResponseRecordService,
)
from plm_assistant.modules.survey.application.response_views import (
    FixedAnswerEvidence, SurveyResponseContext, SurveyResponseWriteView,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
ACTOR, PROJECT, ROUND, SURVEY, VERSION, ASSIGNMENT, QUESTION, QROW = (
    uuid.uuid4() for _ in range(8)
)


class Tx:
    commits = 0
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs): return ACTOR


class Guard:
    def require_valid(self, **kwargs): return object()


class Authorization:
    role = "CUSTOMER_MEMBER"
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(ACTOR, PROJECT, kwargs["operation"], self.role)


class Repository:
    context = SurveyResponseContext(
        ASSIGNMENT, ROUND, SURVEY, VERSION, PROJECT, uuid.uuid4(), ACTOR,
        "ASSIGNED", 0, QROW, QUESTION, "TEXT", (),
    )
    current = None
    def lock_context(self, transaction, **kwargs): return self.context
    def append(self, transaction, **kwargs):
        self.current = SurveyResponseWriteView(
            kwargs["survey_response_id"], kwargs["survey_answer_id"], ASSIGNMENT,
            ROUND, VERSION, PROJECT, QUESTION, kwargs["response_source"],
            kwargs["round_source_record_ref_id"],
            kwargs["correction_of_response_id"], ACTOR, NOW, "IN_PROGRESS",
            '"v1"', len(kwargs["evidence"]),
        )
        self.appended = kwargs
        return self.current
    def get_written(self, transaction, **kwargs): return self.current


class Receipts:
    replay = None
    completed = []
    def reserve(self, transaction, **kwargs): return self.replay
    def complete(self, transaction, **kwargs): self.completed.append(kwargs["result"])


class Audit:
    events = []
    def append(self, transaction, event): self.events.append(event); return uuid.uuid4()


class Unused:
    def prove(self, *args, **kwargs): raise AssertionError("unexpected proof")
    def append(self, *args, **kwargs): raise AssertionError("unexpected append")


class SurveyResponseRecordTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0; Receipts.replay = None; Receipts.completed = []; Audit.events = []
        self.repo, self.receipts = Repository(), Receipts()
        self.service = SurveyResponseRecordService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=self.repo,
            receipts=self.receipts, audit=Audit(), evidence_owner=Unused(),
            round_record_proof=Unused(), round_source_repository=Unused(),
            clock=lambda: NOW,
        )
        self.command = RecordSurveyResponse(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, ROUND, ASSIGNMENT,
            QUESTION, 0, "SELF_SERVICE", None, "  Customer answer  ", (),
            None, None, str(uuid.uuid4()),
        )

    def test_text_response_is_normalized_atomic_audited_and_receipted(self):
        result = self.service.record(self.command)
        self.assertEqual("IN_PROGRESS", result.assignment_state)
        self.assertEqual("Customer answer", self.repo.appended["answer_value"])
        self.assertEqual("SURVEY_RESPONSE_RECORDED", Audit.events[0].action)
        self.assertEqual(1, Tx.commits)
        receipt = Receipts.completed[0]
        self.assertEqual(result.survey_response_id, receipt.ref_id)
        self.assertEqual("V1_SURVEY_RESPONSE_RECORD", receipt.ref_type)

    def test_invalid_type_and_boundaries_fail_closed(self):
        for command in (
            replace(self.command, session_token=b"short"),
            replace(self.command, expected_lock_version=-1),
            replace(self.command, answer_value="\x00"),
            replace(self.command, response_source="FACILITATED_RECORD",
                    project_record_evidence_id=None),
            replace(self.command, evidence_ids=(uuid.UUID(int=0),)),
        ):
            with self.subTest(command=command), self.assertRaises(
                    SurveyResponseRecordError):
                self.service.record(command)

    def test_all_six_answer_types_have_closed_normalization_rules(self):
        evidence = (FixedAnswerEvidence(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 0, b"e" * 32, ACTOR),)
        cases = (
            ("TEXT", (), "  text  ", (), "text"),
            ("SINGLE_CHOICE", ("YES", "NO"), "YES", (), "YES"),
            ("MULTIPLE_CHOICE", ("A", "B"), ("B", "A"), (), ["B", "A"]),
            ("DATE", (), "2026-10-06", (), "2026-10-06"),
            ("NUMBER", (), 42.5, (), 42.5),
            ("ATTACHMENT", (), None, evidence, [str(evidence[0].evidence_id)]),
        )
        for answer_type, options, value, proofs, expected in cases:
            with self.subTest(answer_type=answer_type):
                context = replace(
                    self.repo.context, answer_type=answer_type,
                    option_codes=options)
                command = replace(self.command, answer_value=value)
                self.assertEqual(
                    expected, self.service._answer(context, command, proofs)[1])

        for answer_type, options, value, proofs in (
            ("SINGLE_CHOICE", ("YES",), "NO", ()),
            ("MULTIPLE_CHOICE", ("A",), ["A", "A"], ()),
            ("DATE", (), "2026-02-30", ()),
            ("NUMBER", (), float("nan"), ()),
            ("ATTACHMENT", (), None, ()),
        ):
            with self.subTest(invalid=answer_type), self.assertRaises(
                    SurveyResponseRecordError):
                self.service._answer(
                    replace(self.repo.context, answer_type=answer_type,
                            option_codes=options),
                    replace(self.command, answer_value=value), proofs)

    def test_secrets_are_not_rendered(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__": unittest.main()
