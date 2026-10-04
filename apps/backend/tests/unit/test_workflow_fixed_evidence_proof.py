import unittest
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.evidence.application.fixed_project_source import VerifiedProjectEvidence
from plm_assistant.modules.evidence.application.fixed_global_standard_source import VerifiedStandardEvidence
from plm_assistant.modules.workflow.application.prove_fixed_evidence import (
    WorkflowEvidenceProofError, WorkflowEvidenceQuery, WorkflowFixedEvidenceProofService,
)


class WorkflowFixedEvidenceProofTests(unittest.TestCase):
    def setUp(self):
        self.tx = object()
        self.query = WorkflowEvidenceQuery(b"s" * 32, uuid4(), uuid4(), uuid4(), "PROJECT")
        self.project = Mock()
        self.global_standard = Mock()
        self.service = WorkflowFixedEvidenceProofService(
            project=self.project, global_standard=self.global_standard,
        )

    def project_result(self):
        return VerifiedProjectEvidence(
            self.query.evidence_id, self.query.project_id, uuid4(), uuid4(),
            None, 3, b"p" * 32,
        )

    def global_result(self):
        return VerifiedStandardEvidence(
            self.query.evidence_id, self.query.project_id, uuid4(), uuid4(),
            None, 4, b"g" * 32,
        )

    def test_project_owner_observation_keeps_caller_transaction(self):
        self.project.prove.return_value = self.project_result()
        fact = self.service.prove(self.tx, self.query)
        self.assertIs(self.project.prove.call_args.args[0], self.tx)
        self.assertEqual(self.project.prove.call_args.args[1].session_token, self.query.session_token)
        self.assertEqual((fact.ref_kind, fact.ref_scope, fact.ref_project_id,
                          fact.observed_state, fact.observed_lock_version,
                          fact.content_fingerprint, fact.proof_schema_version),
                         ("EVIDENCE", "PROJECT", self.query.project_id, "ELIGIBLE", 3,
                          b"p" * 32, 1))
        fact.__post_init__()
        self.global_standard.prove.assert_not_called()

    def test_global_standard_owner_observation_keeps_caller_transaction(self):
        self.global_standard.prove.return_value = self.global_result()
        fact = self.service.prove(self.tx, replace(self.query, scope="GLOBAL"))
        self.assertIs(self.global_standard.prove.call_args.args[0], self.tx)
        self.assertEqual((fact.ref_scope, fact.ref_project_id, fact.observed_lock_version),
                         ("GLOBAL", None, 4))
        fact.__post_init__()
        self.project.prove.assert_not_called()

    def test_unknown_scope_and_bad_input_do_not_call_owners(self):
        for query in (replace(self.query, scope="OTHER"),
                      replace(self.query, session_token=b"short"),
                      replace(self.query, evidence_id=uuid4().hex)):
            with self.assertRaises(WorkflowEvidenceProofError):
                self.service.prove(self.tx, query)
        self.project.prove.assert_not_called()
        self.global_standard.prove.assert_not_called()

    def test_owner_failure_and_cross_project_forgery_fail_closed(self):
        self.project.prove.side_effect = RuntimeError("private path")
        with self.assertRaisesRegex(WorkflowEvidenceProofError, "EVIDENCE_RESOLUTION_UNAVAILABLE"):
            self.service.prove(self.tx, self.query)
        self.project.prove.side_effect = None
        for result in (replace(self.project_result(), project_id=uuid4()),
                       replace(self.project_result(), evidence_id=uuid4()),
                       replace(self.project_result(), scope="GLOBAL"),
                       replace(self.project_result(), observed_state="REVOKED"),
                       replace(self.project_result(), observed_lock_version=-1),
                       replace(self.project_result(), content_fingerprint=b"bad")):
            self.project.prove.return_value = result
            with self.assertRaises(WorkflowEvidenceProofError):
                self.service.prove(self.tx, self.query)

    def test_global_wrong_target_or_kind_fail_closed(self):
        for result in (replace(self.global_result(), target_project_id=uuid4()),
                       replace(self.global_result(), scope="PROJECT"),
                       replace(self.global_result(), source_project_id=uuid4()),
                       self.project_result()):
            self.global_standard.prove.return_value = result
            with self.assertRaises(WorkflowEvidenceProofError):
                self.service.prove(self.tx, replace(self.query, scope="GLOBAL"))


if __name__ == "__main__":
    unittest.main()
