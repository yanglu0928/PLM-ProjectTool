from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.create_task import (
    AuthorizedEgressSnapshot, EgressAuthorizationOwnerError,
)
from plm_assistant.modules.ai.application.task_execution_preflight import (
    AITaskExecutionPreflight, AITaskExecutionPreflightError,
    AITaskExecutionSnapshot,
)


class Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Repository:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def load_for_execution(self, transaction, **kwargs):
        del transaction, kwargs
        return self.snapshot


class Egress:
    def __init__(self, current=None, *, fail=False):
        self.current, self.fail = current, fail

    def resolve_authorized(self, transaction, *, query):
        del transaction, query
        if self.fail:
            raise EgressAuthorizationOwnerError()
        return self.current


class AITaskExecutionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        self.task_id, self.project_id, self.job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.authorization_ref = uuid.uuid4()
        self.content_plan = uuid.uuid4()
        self.provider_id, self.config_id, self.model_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.valid_until = self.now + timedelta(minutes=20)
        self.snapshot = AITaskExecutionSnapshot(
            self.task_id, self.project_id, self.job_id, "GAP_ANALYSIS", b"i" * 32,
            "gap-analysis.v1", 1, uuid.uuid4(), 2,
            "gap-analysis-output.v1", "project-documents.v1",
            {"language": "zh-CN"}, b"p" * 32,
            self.authorization_ref, b"a" * 32, "project-gap-analysis.v1",
            self.provider_id, self.config_id, self.model_id, self.valid_until,
            self.content_plan,
        )
        self.current = AuthorizedEgressSnapshot(
            self.authorization_ref, self.project_id, "project-gap-analysis.v1",
            self.provider_id, self.config_id, self.model_id, "cn-beijing",
            ("DOCUMENT_TEXT",), b"a" * 32, b"v" * 32, b"i" * 32,
            uuid.uuid4(), "PROJECT_MANAGER", self.now - timedelta(minutes=1),
            self.valid_until, "document-minimal.v1", 1, 1000, 100, 2,
            "AUTHORIZED",
            self.content_plan,
        )

    def service(self, snapshot, current=None, *, fail=False):
        return AITaskExecutionPreflight(
            unit_of_work=Transaction,
            repository=Repository(snapshot),
            egress_owner=Egress(current, fail=fail),
        )

    def test_complete_snapshot_and_live_authorization_are_admitted(self):
        result = self.service(self.snapshot, self.current).require(
            ai_task_id=self.task_id, project_id=self.project_id,
            job_id=self.job_id, now=self.now,
        )
        self.assertIs(result, self.snapshot)

    def test_legacy_null_projection_is_not_admitted(self):
        with self.assertRaises(AITaskExecutionPreflightError):
            self.service(None).require(
                ai_task_id=self.task_id, project_id=self.project_id,
                job_id=self.job_id, now=self.now,
            )

    def test_revoked_or_changed_authorization_is_not_admitted(self):
        for service in (
            self.service(self.snapshot, fail=True),
            self.service(self.snapshot, AuthorizedEgressSnapshot(
                self.current.authorization_ref, self.current.project_id,
                self.current.purpose_ref, self.current.ai_provider_id,
                self.current.provider_config_version_id, self.current.ai_model_id,
                self.current.data_region, self.current.allowed_data_categories,
                b"x" * 32, self.current.preview_payload_fingerprint,
                self.current.source_refs_fingerprint, self.current.approved_by,
                self.current.approved_role, self.current.approved_at,
                self.current.valid_until, self.current.minimal_payload_policy_ref,
                self.current.max_record_count, self.current.max_payload_bytes,
                self.current.max_input_tokens, self.current.max_retry_attempts,
                self.current.authorization_state,
            )),
        ):
            with self.subTest(service=service):
                with self.assertRaises(AITaskExecutionPreflightError):
                    service.require(
                        ai_task_id=self.task_id, project_id=self.project_id,
                        job_id=self.job_id, now=self.now,
                    )


if __name__ == "__main__":
    unittest.main()
