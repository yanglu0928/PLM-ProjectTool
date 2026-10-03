from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
    content_plan_fingerprint,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
    AIExecutionContentPlanPersistenceError,
    PersistedAIExecutionContentPlan,
)
from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope


def fixture() -> tuple[uuid.UUID, AIExecutionContentPlan, AIExecutionEnvelope]:
    project, plan_id, preview = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    source = AIExecutionContentSourceIdentity(
        1, "DOC-02", "document", "DOCUMENT_VERSION", uuid.uuid4(),
        uuid.uuid4(), project, "DOCUMENT_PARSED_TEXT", uuid.uuid4(),
        uuid.uuid4(), "document-parser.standard", "1.0.0",
        "document.parse-result.v1", "document.parse.fixed.v1",
        b"r" * 32, b"c" * 32, b"q" * 32, 2048, 6,
    )
    prompt = AIExecutionPromptIdentity(
        "gap-analysis.v1", 1, uuid.uuid4(), 1, "a" * 64, "b" * 64,
        "content-plan-chat.v1", "gap-output.v1", 1,
        "strict-placeholders.v1", 1,
    )
    plan = AIExecutionContentPlan(
        plan_id, 1, project, "project-gap-analysis.v1", "GAP_ANALYSIS",
        b"s" * 32, (source,), prompt, b"t" * 32,
        AIExecutionContextIdentity("no-retrieval.v1", "NONE"),
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "content-plan-chat",
        "PROVIDER_MANAGED", "cn-beijing", ("DOCUMENT_TEXT",),
        "document-minimal.v1", "provider-neutral-json.v1", 1,
        "utf8-byte-upper-bound.v1", 1,
    )
    envelope = AIExecutionEnvelope(
        plan_id, content_plan_fingerprint(plan), "provider-neutral-json.v1", 1,
        (source.projection_fingerprint,), b'{"messages":[]}', 6, 128,
        "utf8-byte-upper-bound.v1", 1,
    )
    return preview, plan, envelope


class FakeRepository:
    def __init__(self) -> None:
        self.by_id: dict[uuid.UUID, PersistedAIExecutionContentPlan] = {}
        self.by_preview: dict[uuid.UUID, PersistedAIExecutionContentPlan] = {}
        self.add_count = 0

    def get_by_id(self, _transaction: object, *, content_plan_id: uuid.UUID):
        return self.by_id.get(content_plan_id)

    def get_by_preview(self, _transaction: object, *, egress_preview_id: uuid.UUID):
        return self.by_preview.get(egress_preview_id)

    def add(self, _transaction: object, *, value: PersistedAIExecutionContentPlan) -> None:
        self.add_count += 1
        self.by_id[value.plan.content_plan_id] = value
        self.by_preview[value.egress_preview_id] = value


class AIExecutionContentPlanOwnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview, self.plan, self.envelope = fixture()
        self.repository = FakeRepository()
        self.owner = AIExecutionContentPlanOwner(self.repository)

    def test_persist_recomputes_and_replays_exact_record(self) -> None:
        created = self.owner.persist(
            object(), egress_preview_id=self.preview,
            plan=self.plan, envelope=self.envelope,
        )
        replayed = self.owner.persist(
            object(), egress_preview_id=self.preview,
            plan=self.plan, envelope=self.envelope,
        )
        self.assertEqual(created, replayed)
        self.assertEqual(self.repository.add_count, 1)
        self.assertNotIn("messages", repr(created))

    def test_envelope_or_unique_identity_drift_is_rejected(self) -> None:
        wrong_envelope = replace(self.envelope, input_tokens=129)
        self.owner.persist(
            object(), egress_preview_id=self.preview,
            plan=self.plan, envelope=self.envelope,
        )
        with self.assertRaisesRegex(
                AIExecutionContentPlanPersistenceError,
                "AI_EXECUTION_CONTENT_PLAN_CONFLICT"):
            self.owner.persist(
                object(), egress_preview_id=self.preview,
                plan=self.plan, envelope=wrong_envelope,
            )
        mismatched = replace(
            self.envelope, content_plan_fingerprint=b"x" * 32,
        )
        with self.assertRaisesRegex(
                AIExecutionContentPlanPersistenceError,
                "AI_EXECUTION_CONTENT_PLAN_ENVELOPE_MISMATCH"):
            AIExecutionContentPlanOwner(FakeRepository()).persist(
                object(), egress_preview_id=self.preview,
                plan=self.plan, envelope=mismatched,
            )

    def test_corrupt_persisted_fingerprint_fails_closed_on_read(self) -> None:
        value = self.owner.persist(
            object(), egress_preview_id=self.preview,
            plan=self.plan, envelope=self.envelope,
        )
        object.__setattr__(value, "plan_fingerprint", b"x" * 32)
        with self.assertRaises(AIExecutionContentPlanPersistenceError):
            self.owner.get(object(), content_plan_id=self.plan.content_plan_id)


if __name__ == "__main__":
    unittest.main()
