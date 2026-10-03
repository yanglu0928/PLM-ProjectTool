from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.create_task import AuthorizedEgressSnapshot
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrantError, AITaskExecutionInputRef,
)
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantIssuer, AITaskExecutionGrantMaterial,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim, AITaskExecutionClaims,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _ClaimRepository:
    def __init__(self, claim):
        self.claim = claim

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.claim


class _MaterialRepository:
    def __init__(self, material):
        self.material = material

    def load(self, transaction, **kwargs):
        del transaction, kwargs
        return self.material


class _Egress:
    def __init__(self, current):
        self.current = current

    def resolve_authorized(self, transaction, **kwargs):
        del transaction, kwargs
        return self.current


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


class AITaskExecutionGrantIssuerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 9, tzinfo=timezone.utc)
        task, project, job, actor, trace, authorization = (
            uuid.uuid4() for _ in range(6)
        )
        provider, config, model = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), project,
        )
        self.claim = AITaskExecutionClaim(
            job, task, project, actor, trace, authorization, b"i" * 32,
            7, 1, 3,
        )
        valid_until = self.now + timedelta(minutes=20)
        approved_at = self.now - timedelta(minutes=2)
        approved_by = uuid.uuid4()
        self.content_plan = uuid.uuid4()
        self.material = AITaskExecutionGrantMaterial(
            task, project, job, actor, trace, "GAP_ANALYSIS", (input_ref,),
            b"i" * 32, "gap-analysis.v1", 4, uuid.uuid4(), 2,
            "a" * 64, "b" * 64, "deepseek-chat.v1", "gap-output.v1",
            3, "project-documents.v1", b"t" * 32, uuid.uuid4(),
            authorization, b"a" * 32, "project-gap-analysis.v1",
            provider, config, model, "deepseek-chat", "PROVIDER_MANAGED",
            "cn-beijing", ("DOCUMENT_TEXT",), b"p" * 32, approved_by,
            "PROJECT_MANAGER", approved_at, 65_536, 4_096, 3, valid_until,
            self.content_plan,
        )
        self.current = AuthorizedEgressSnapshot(
            authorization, project, "project-gap-analysis.v1", provider, config,
            model, "cn-beijing", ("DOCUMENT_TEXT",), b"a" * 32,
            b"p" * 32, b"i" * 32, approved_by, "PROJECT_MANAGER",
            approved_at, valid_until, "document-minimal.v1", 50,
            65_536, 4_096, 3, "AUTHORIZED",
            self.content_plan,
        )

    def service(self, *, material=None, current=None, guard=None):
        guard = guard or _Guard()
        service = AITaskExecutionGrantIssuer(
            unit_of_work=_Transaction,
            claims=AITaskExecutionClaims(
                repository=_ClaimRepository(self.claim),
            ),
            repository=_MaterialRepository(
                self.material if material is None else material,
            ),
            egress_owner=_Egress(self.current if current is None else current),
            license_guard=guard,
        )
        return service, guard

    def test_exact_current_sources_issue_complete_non_content_grant(self):
        service, guard = self.service()
        grant = service.issue(
            job_id=self.claim.job_id, fencing_token=7,
            worker_ref="worker-a", now=self.now,
        )
        self.assertEqual((grant.attempt_no, grant.fencing_token), (1, 7))
        self.assertEqual(grant.minimal_payload_policy_ref, "document-minimal.v1")
        self.assertEqual(grant.max_record_count, 50)
        self.assertEqual(guard.calls, 2)
        self.assertNotIn("b'i", repr(grant))
        self.assertFalse(hasattr(grant, "system_template"))

    def test_claim_or_live_authorization_drift_fails_closed(self):
        cases = (
            (replace(self.material, requested_by=uuid.uuid4()), self.current),
            (self.material, replace(self.current, max_payload_bytes=65_535)),
            (self.material, replace(self.current, authorization_fingerprint=b"x" * 32)),
        )
        for material, current in cases:
            with self.subTest(material=material, current=current):
                service, _ = self.service(material=material, current=current)
                with self.assertRaises(AITaskExecutionGrantError):
                    service.issue(
                        job_id=self.claim.job_id, fencing_token=7,
                        worker_ref="worker-a", now=self.now,
                    )

    def test_license_is_checked_inside_and_after_transaction(self):
        for failure in (1, 2):
            with self.subTest(failure=failure):
                service, guard = self.service(guard=_Guard(fail_on=failure))
                with self.assertRaises(AITaskExecutionGrantError):
                    service.issue(
                        job_id=self.claim.job_id, fencing_token=7,
                        worker_ref="worker-a", now=self.now,
                    )
                self.assertEqual(guard.calls, failure)


if __name__ == "__main__":
    unittest.main()
