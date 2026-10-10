from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.requirement.application.human_decision_source_proof import (
    RequirementHumanDecisionSourceProof,
)
from plm_assistant.modules.requirement.infrastructure.human_decision_source_proof import (
    SqlAlchemyRequirementHumanDecisionSourceProof,
)


class RequirementHumanDecisionSourceProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.decision, self.requirement, self.project = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        self.actor = uuid.uuid4()
        self.evidence = tuple(sorted((uuid.uuid4(), uuid.uuid4()), key=str))
        self.decided_at = datetime.now(timezone.utc)

    @staticmethod
    def _result(*, row=None, evidence=()):
        first, second = MagicMock(), MagicMock()
        first.one_or_none.return_value = row
        second.scalars.return_value = evidence
        return first, second

    def test_proof_binds_decision_owner_result_and_evidence_set(self) -> None:
        row = (
            self.decision, self.requirement, self.project, "DEFER", self.actor,
            self.decided_at, 0, 1, list(self.evidence),
        )
        first, second = self._result(row=row, evidence=self.evidence)
        proof = SqlAlchemyRequirementHumanDecisionSourceProof()
        with Session() as session, session.begin(), patch.object(
            session, "execute", side_effect=(first, second),
        ) as execute:
            result = proof.prove(
                SimpleNamespace(session=session), project_id=self.project,
                decision_id=self.decision,
            )
            self.assertEqual(result, RequirementHumanDecisionSourceProof(
                *row[:8], self.evidence,
            ))
            decision_sql = str(execute.call_args_list[0].args[0].compile(
                dialect=postgresql.dialect(),
            ))
            evidence_sql = str(execute.call_args_list[1].args[0].compile(
                dialect=postgresql.dialect(),
            ))
            for token in (
                "req_requirement_state_decisions.decision_type",
                "req_requirement_command_results.operation",
                "req_requirement_command_results.reason",
                "req_requirement_command_results.impact",
                "req_requirement_command_results.lock_version",
                "FOR SHARE OF req_requirement_state_decisions, "
                "req_requirement_command_results",
            ):
                self.assertIn(token, decision_sql)
            self.assertIn(
                "FOR SHARE OF req_requirement_decision_evidence_refs",
                evidence_sql,
            )

    def test_missing_mismatched_evidence_and_invalid_ids_fail_closed(self) -> None:
        row = (
            self.decision, self.requirement, self.project, "REJECT", self.actor,
            self.decided_at, 2, 3, list(self.evidence),
        )
        proof = SqlAlchemyRequirementHumanDecisionSourceProof()
        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            first, second = self._result(row=None)
            execute.side_effect = (first, second)
            self.assertIsNone(proof.prove(
                SimpleNamespace(session=session), project_id=self.project,
                decision_id=self.decision,
            ))
            self.assertEqual(execute.call_count, 1)

        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            first, second = self._result(row=row, evidence=self.evidence[:1])
            execute.side_effect = (first, second)
            self.assertIsNone(proof.prove(
                SimpleNamespace(session=session), project_id=self.project,
                decision_id=self.decision,
            ))
            self.assertEqual(execute.call_count, 2)

        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            self.assertIsNone(proof.prove(
                SimpleNamespace(session=session), project_id=self.project,
                decision_id=uuid.UUID(int=0),
            ))
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
