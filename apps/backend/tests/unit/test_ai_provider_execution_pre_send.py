from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.create_task import AuthorizedEgressSnapshot
from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    require_provider_send,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy,
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AIProviderExecutionRouteMaterial,
    AIProviderPreSendError,
    AIProviderPreSendService,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
    AITaskPayloadPlanProof,
    execution_grant_fingerprint,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    BegunAITaskInvocation,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    PreparedAITaskInvocation,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
    AITaskExecutionClaims,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _ClaimRepository:
    def __init__(self, value):
        self.value = value

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _RouteRepository:
    def __init__(self, value):
        self.value = value

    def load_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _Egress:
    def __init__(self, value):
        self.value = value

    def resolve_authorized(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _Secrets:
    def __init__(self, value):
        self.value = value

    def active_provider_key_version(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _Guard:
    def __init__(self, fail_on=0):
        self.calls = 0
        self.fail_on = fail_on

    def require_valid(self, **kwargs):
        del kwargs
        self.calls += 1
        if self.calls == self.fail_on:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class AIProviderPreSendTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 17, tzinfo=timezone.utc)
        project, task, job, actor, trace, authorization = (
            uuid.uuid4() for _ in range(6)
        )
        provider, config, model, snapshot, plan = (
            uuid.uuid4() for _ in range(5)
        )
        secret, secret_version, invocation = (
            uuid.uuid4() for _ in range(3)
        )
        valid_until = self.now + timedelta(minutes=10)
        canonical_bytes = b'{"input":"safe synthetic"}'
        payload_fingerprint = hashlib.sha256(canonical_bytes).digest()
        self.grant = AITaskExecutionGrant(
            task, project, job, actor, trace, 1, 7, "GAP_ANALYSIS",
            (AITaskExecutionInputRef(
                1, "DOC-02", "document", "DOCUMENT_VERSION",
                uuid.uuid4(), uuid.uuid4(), project,
            ),),
            b"i" * 32, "gap-analysis.v1", 1, uuid.uuid4(), 1,
            "a" * 64, "b" * 64, "provider.v1", "gap-output.v1", 1,
            "no-retrieval.v1", b"t" * 32, snapshot, authorization,
            b"a" * 32, "project-gap-analysis.v1", provider, config, model,
            "chat-model", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), payload_fingerprint, "document-minimal.v1",
            2, 65_536, 4_096, 3, valid_until, plan,
        )
        self.envelope = AIExecutionEnvelope(
            plan, b"c" * 32, "provider-neutral-json.v1", 1,
            (b"d" * 32,), canonical_bytes, 2, 30,
            "utf8-byte-upper-bound.v1", 1,
        )
        self.payload_plan = AITaskPayloadPlanProof(
            task, job, 1, execution_grant_fingerprint(self.grant),
            self.grant.source_refs_fingerprint,
            self.grant.approved_payload_fingerprint, 2,
            self.envelope.payload_bytes, self.envelope.input_tokens,
        )
        self.prepared = PreparedAITaskInvocation(
            self.grant, self.envelope, self.payload_plan,
        )
        self.begun = BegunAITaskInvocation(invocation, self.grant)
        self.claim = AITaskExecutionClaim(
            job, task, project, actor, trace, authorization, b"i" * 32,
            7, 1, 3,
        )
        self.material = AIProviderExecutionRouteMaterial(
            task, invocation, project, job, 1, snapshot, authorization, plan,
            payload_fingerprint, provider, config, model,
            ProviderKind.OPENAI_COMPATIBLE, "endpoint.execution.v1", secret,
            "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED", "chat-model",
            "PROVIDER_MANAGED",
        )
        self.current = AuthorizedEgressSnapshot(
            authorization, project, "project-gap-analysis.v1", provider, config,
            model, "cn-beijing", ("DOCUMENT_TEXT",), b"a" * 32,
            payload_fingerprint, b"i" * 32, uuid.uuid4(), "PROJECT_MANAGER",
            self.now - timedelta(minutes=1), valid_until,
            "document-minimal.v1", 2, 65_536, 4_096, 3, "AUTHORIZED", plan,
        )
        self.secret_version = secret_version
        self.policy = AIProviderExecutionPolicy(
            "endpoint.execution.v1", ProviderKind.OPENAI_COMPATIBLE,
            "https://api.example.test/v1/chat/completions", "cn-beijing",
            "EXTERNAL_APPROVAL_REQUIRED", frozenset({"chat-model"}),
            1_000_000, 3, 10, 20,
        )

    def service(self, *, material=None, current=None, secret_version=True,
                policy=None, guard=None):
        guard = guard or _Guard()
        service = AIProviderPreSendService(
            unit_of_work=_Transaction,
            claims=AITaskExecutionClaims(
                repository=_ClaimRepository(self.claim),
            ),
            repository=_RouteRepository(
                self.material if material is None else material,
            ),
            egress_owner=_Egress(self.current if current is None else current),
            secret_proof=_Secrets(
                self.secret_version if secret_version is True else secret_version,
            ),
            policies=AIProviderExecutionPolicyRegistry((policy or self.policy,)),
            license_guard=guard,
        )
        return service, guard

    def authorize(self, service, *, prepared=None, begun=None):
        return service.authorize(
            prepared=self.prepared if prepared is None else prepared,
            begun=self.begun if begun is None else begun,
            job_id=self.grant.job_id, fencing_token=7,
            worker_ref="worker-a", now=self.now,
        )

    def test_exact_post_begin_facts_authorize_one_bounded_route(self):
        service, guard = self.service()
        result = self.authorize(service)
        self.assertEqual(result.route.secret_version_id, self.secret_version)
        self.assertEqual(result.proof.ai_invocation_id, self.begun.ai_invocation_id)
        self.assertIs(require_provider_send(
            result.proof, result.route, self.envelope, now=self.now,
        ), result.proof)
        self.assertEqual(guard.calls, 2)
        self.assertNotIn(result.route.endpoint_url, repr(result.route))
        self.assertNotIn(str(result.route.secret_ref), repr(result.route))

    def test_grant_material_authorization_and_secret_drift_fail_closed(self):
        cases = (
            (self.service(material=replace(
                self.material, provider_config_version_id=uuid.uuid4())),
             self.prepared, self.begun),
            (self.service(current=replace(
                self.current, authorization_fingerprint=b"z" * 32)),
             self.prepared, self.begun),
            (self.service(secret_version=None), self.prepared, self.begun),
            (self.service(), self.prepared, BegunAITaskInvocation(
                self.begun.ai_invocation_id,
                replace(self.grant, fencing_token=8),
            )),
        )
        for (service, _), prepared, begun in cases:
            with self.subTest(begun=begun), self.assertRaises(AIProviderPreSendError):
                self.authorize(service, prepared=prepared, begun=begun)

    def test_policy_model_mismatch_fails_closed(self):
        policy = replace(
            self.policy, allowed_model_keys=frozenset({"other-model"}),
        )
        service, _ = self.service(policy=policy)
        with self.assertRaises(AIProviderPreSendError):
            self.authorize(service)

    def test_license_is_checked_inside_and_after_transaction(self):
        for failure in (1, 2):
            guard = _Guard(fail_on=failure)
            service, _ = self.service(guard=guard)
            with self.subTest(failure=failure), self.assertRaises(AIProviderPreSendError):
                self.authorize(service)
            self.assertEqual(guard.calls, failure)


if __name__ == "__main__":
    unittest.main()
