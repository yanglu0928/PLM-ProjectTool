from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentProjection,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
    content_plan_fingerprint,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    PersistedAIExecutionContentPlan,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContent,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
    execution_grant_fingerprint,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    AITaskInvocationPrepareError,
    AITaskInvocationPrepareService,
)


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Grants:
    def __init__(self, value):
        self.value = value
        self.issued = 0
        self.checked = 0

    def issue(self, **_kwargs):
        self.issued += 1
        return self.value

    def require_usable(self, value):
        assert value is self.value
        self.checked += 1


class _Plans:
    def __init__(self, value):
        self.value = value

    def get(self, _transaction, **_kwargs):
        return self.value


class _Prompts:
    def __init__(self, value):
        self.value = value

    def load_exact(self, _transaction, **_kwargs):
        return self.value


class _Source:
    def __init__(self, value):
        self.value = value

    def read_exact(self, _transaction, _query, source):
        assert source == self.value.source
        return self.value


class AITaskInvocationPrepareTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 14, tzinfo=timezone.utc)
        project, plan_id = uuid.uuid4(), uuid.uuid4()
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), project,
        )
        system, user = "System {parameters}", "Input {input}"
        system_hash = hashlib.sha256(system.encode()).hexdigest()
        user_hash = hashlib.sha256(user.encode()).hexdigest()
        raw = json.dumps({
            "nodes": [{"kind": "TEXT_LINE", "node_id": "line-1", "text": "需求"}],
            "schema_version": "document-minimum-text-v1",
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        source = AIExecutionContentSourceIdentity(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            input_ref.object_id, input_ref.version_id, project,
            "DOCUMENT_PARSED_TEXT", uuid.uuid4(), uuid.uuid4(),
            "PLAIN_TEXT", "1", "document.parse-result.v1",
            "document.parse.fixed.v1", b"d" * 32, b"e" * 32,
            hashlib.sha256(raw).digest(), len(raw), 1,
        )
        self.projection = AIExecutionContentProjection(
            source, "document.minimum-text.v1", 1, raw,
        )
        prompt_id = uuid.uuid4()
        prompt = AIExecutionPromptIdentity(
            "gap-analysis.v1", 1, prompt_id, 1, system_hash, user_hash,
            "provider.v1", "gap-output.v1", 1,
            "strict-placeholders.v1", 1,
        )
        provider, config, model = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.plan = AIExecutionContentPlan(
            plan_id, 1, project, "project-gap-analysis.v1", "GAP_ANALYSIS",
            b"s" * 32, (source,), prompt, b"t" * 32,
            AIExecutionContextIdentity("no-retrieval.v1", "NONE"),
            provider, config, model, "chat", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), "minimum.document.text.v1",
            "provider-neutral-json.v1", 1, "utf8-byte-upper-bound.v1", 1,
        )
        base = AITaskExecutionGrant(
            uuid.uuid4(), project, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            1, 9, "GAP_ANALYSIS", (input_ref,), b"s" * 32,
            "gap-analysis.v1", 1, prompt_id, 1, system_hash, user_hash,
            "provider.v1", "gap-output.v1", 1, "no-retrieval.v1", b"t" * 32,
            uuid.uuid4(), uuid.uuid4(), b"a" * 32, "project-gap-analysis.v1",
            provider, config, model, "chat", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), b"x" * 32, "minimum.document.text.v1",
            1, 100000, 100000, 3, self.now + timedelta(minutes=10), plan_id,
        )
        self.prompt = AIExecutionPromptTaskContent(
            base.ai_task_id, project, base.job_id, base.requested_by, base.trace_id,
            "GAP_ANALYSIS", "gap-analysis.v1", 1, prompt_id, 1,
            system, user, system_hash, user_hash, "provider.v1",
            "gap-output.v1", 1, "no-retrieval.v1",
            {"language": "zh-CN"}, b"t" * 32,
        )
        self.builder = AIExecutionEnvelopeBuilder(
            renderer=StrictAIExecutionPromptRenderer(),
            context_policies=AIExecutionContextPolicyRegistry(
                frozenset({"no-retrieval.v1"})),
            token_estimators=AIExecutionTokenEstimatorRegistry((
                Utf8ByteUpperBoundTokenEstimator(),)),
        )
        envelope = self.builder.build(
            plan=self.plan, sources=(self.projection,), prompt_content=self.prompt,
        )
        self.grant = replace(
            base, approved_payload_fingerprint=envelope.payload_fingerprint,
        )
        self.persisted = PersistedAIExecutionContentPlan(
            uuid.uuid4(), self.plan, content_plan_fingerprint(self.plan),
            envelope.payload_fingerprint, envelope.record_count,
            envelope.payload_bytes, envelope.input_tokens,
        )

    def service(self, grants, *, persisted=None, sources=None):
        return AITaskInvocationPrepareService(
            unit_of_work=_Transaction, grants=grants,
            plans=_Plans(self.persisted if persisted is None else persisted),
            prompts=_Prompts(self.prompt),
            source_owners={"DOC-02": _Source(self.projection)}
            if sources is None else sources,
            envelopes=self.builder,
        )

    def test_prepares_exact_bytes_and_no_content_proof(self):
        grants = _Grants(self.grant)
        result = self.service(grants).prepare(
            job_id=self.grant.job_id, fencing_token=9,
            worker_ref="worker-a", now=self.now,
        )
        self.assertEqual(result.payload_plan.payload_fingerprint,
                         result.envelope.payload_fingerprint)
        self.assertEqual(result.payload_plan.grant_fingerprint,
                         execution_grant_fingerprint(self.grant))
        self.assertEqual((grants.issued, grants.checked), (1, 1))
        self.assertNotIn("需求", repr(result))

    def test_persisted_payload_drift_and_unknown_owner_fail_closed(self):
        drifted = replace(self.persisted, payload_fingerprint=b"z" * 32)
        for service in (
            self.service(_Grants(self.grant), persisted=drifted),
            self.service(_Grants(self.grant), sources={"OTHER": _Source(self.projection)}),
        ):
            with self.subTest(service=service), self.assertRaises(
                    AITaskInvocationPrepareError):
                service.prepare(
                    job_id=self.grant.job_id, fencing_token=9,
                    worker_ref="worker-a", now=self.now,
                )


if __name__ == "__main__":
    unittest.main()
