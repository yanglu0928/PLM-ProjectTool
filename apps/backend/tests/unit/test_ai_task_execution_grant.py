from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant, AITaskExecutionGrantError, AITaskExecutionInputRef,
    AITaskPayloadPlanProof, execution_grant_fingerprint, require_payload_plan,
)


class AITaskExecutionGrantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        self.task_id, self.project_id, self.job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), self.project_id,
        )
        self.grant = AITaskExecutionGrant(
            self.task_id, self.project_id, self.job_id, uuid.uuid4(), uuid.uuid4(),
            1, 1, "GAP_ANALYSIS", (input_ref,), b"s" * 32,
            "gap-analysis.v1", 1, uuid.uuid4(), 2, "a" * 64, "b" * 64,
            "deepseek-chat.v1", "gap-output.v1", 1, "project-documents.v1",
            b"t" * 32, uuid.uuid4(), uuid.uuid4(), b"a" * 32,
            "project-gap-analysis.v1", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            "deepseek-chat", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), b"p" * 32, 1, 65536, 4096, 3,
            self.now + timedelta(minutes=20),
        )

    def proof(self) -> AITaskPayloadPlanProof:
        return AITaskPayloadPlanProof(
            self.task_id, self.job_id, 1, execution_grant_fingerprint(self.grant),
            b"s" * 32, b"p" * 32, 1, 4096, 512,
        )

    def test_exact_bounded_plan_is_authorized_without_content_projection(self) -> None:
        proof = self.proof()
        self.assertIs(require_payload_plan(self.grant, proof, now=self.now), proof)
        self.assertNotIn("fingerprint", repr(proof))
        self.assertNotIn("b'p", repr(proof))

    def test_changed_payload_or_grant_is_rejected(self) -> None:
        for proof in (
            replace(self.proof(), payload_fingerprint=b"x" * 32),
            replace(self.proof(), grant_fingerprint=b"x" * 32),
            replace(self.proof(), source_refs_fingerprint=b"x" * 32),
        ):
            with self.subTest(proof=proof), self.assertRaises(AITaskExecutionGrantError):
                require_payload_plan(self.grant, proof, now=self.now)

    def test_every_quantitative_bound_and_expiry_fail_closed(self) -> None:
        for proof, moment in (
            (replace(self.proof(), record_count=2), self.now),
            (replace(self.proof(), payload_bytes=65537), self.now),
            (replace(self.proof(), input_tokens=4097), self.now),
            (self.proof(), self.grant.valid_until),
        ):
            with self.subTest(proof=proof, moment=moment), self.assertRaises(
                    AITaskExecutionGrantError):
                require_payload_plan(self.grant, proof, now=moment)

    def test_invalid_attempt_input_order_and_categories_are_rejected(self) -> None:
        with self.assertRaises(AITaskExecutionGrantError):
            replace(self.grant, attempt_no=4)
        with self.assertRaises(AITaskExecutionGrantError):
            bad_ref = replace(self.grant.input_refs[0], ordinal=2)
            replace(self.grant, input_refs=(bad_ref,))
        with self.assertRaises(AITaskExecutionGrantError):
            replace(self.grant, allowed_data_categories=(
                "DOCUMENT_TEXT", "DOCUMENT_TEXT",
            ))


if __name__ == "__main__":
    unittest.main()
