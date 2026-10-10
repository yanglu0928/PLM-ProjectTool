from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.create_task import (
    EgressAuthorizationOwnerError, EgressAuthorizationQuery,
)
from plm_assistant.modules.ai.application.egress_authorization import EgressAuthorizationView
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry, EgressAuthorizationOwner,
    authorization_fingerprint,
)


class _Repository:
    def __init__(self, value): self.value, self.calls = value, 0
    def resolve_current(self, *_args, **_kwargs): self.calls += 1; return self.value


class EgressAuthorizationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
        self.project, self.authorization_id = uuid.uuid4(), uuid.uuid4()
        self.content_plan = uuid.uuid4()
        self.value = EgressAuthorizationView(
            self.authorization_id, uuid.uuid4(), self.project,
            "gap.analysis.v1", "AI_TASK", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), "cn-beijing", ("TECHNICAL_DOCUMENT",),
            "minimum.document.text.v1", 10, 65536, 4096, 3,
            b"p" * 32, b"s" * 32, uuid.uuid4(), "ProjectManager",
            self.now - timedelta(minutes=1), self.now + timedelta(minutes=20),
            "AUTHORIZED", 0,
            self.content_plan,
        )
        self.query = EgressAuthorizationQuery(
            self.authorization_id, self.project, "GAP_ANALYSIS",
            b"s" * 32, self.now,
        )

    def owner(self, value=None, purposes=None):
        self.repository = _Repository(self.value if value is None else value)
        return EgressAuthorizationOwner(
            repository=self.repository,
            purposes=AITaskEgressPurposeRegistry(purposes or {
                "GAP_ANALYSIS": frozenset({"gap.analysis.v1"}),
            }),
        )

    def test_projects_complete_current_snapshot(self):
        snapshot = self.owner().resolve_authorized(object(), query=self.query)
        self.assertEqual(snapshot.authorization_ref, self.authorization_id)
        self.assertEqual(snapshot.approved_role, "PROJECT_MANAGER")
        self.assertEqual(snapshot.source_refs_fingerprint, b"s" * 32)
        self.assertEqual(snapshot.authorization_fingerprint,
                         authorization_fingerprint(self.value))

    def test_rejects_wrong_source_or_purpose(self):
        changed = EgressAuthorizationQuery(
            self.authorization_id, self.project, "GAP_ANALYSIS", b"x" * 32, self.now,
        )
        with self.assertRaises(EgressAuthorizationOwnerError):
            self.owner().resolve_authorized(object(), query=changed)
        with self.assertRaises(EgressAuthorizationOwnerError):
            self.owner(purposes={"GAP_ANALYSIS": frozenset({"other.purpose.v1"})}).resolve_authorized(
                object(), query=self.query,
            )

    def test_rejects_legacy_authorization_without_content_plan(self):
        with self.assertRaises(EgressAuthorizationOwnerError):
            self.owner(value=replace(
                self.value, content_plan_ref=None,
            )).resolve_authorized(object(), query=self.query)

    def test_rejects_expired_or_revoked_current_root(self):
        expired = EgressAuthorizationView(
            self.value.authorization_id, self.value.preview_id, self.value.project_id,
            self.value.purpose_ref, self.value.operation_type, self.value.provider_id,
            self.value.provider_config_version_id, self.value.model_id,
            self.value.data_region, self.value.allowed_data_categories,
            self.value.minimal_payload_policy_ref, self.value.max_record_count,
            self.value.max_payload_bytes, self.value.max_input_tokens,
            self.value.max_retry_attempts, self.value.payload_fingerprint,
            self.value.source_refs_fingerprint, self.value.approved_by,
            self.value.approved_role, self.value.approved_at, self.now,
            "AUTHORIZED", 0,
            self.value.content_plan_ref,
        )
        with self.assertRaises(EgressAuthorizationOwnerError):
            self.owner(value=expired).resolve_authorized(object(), query=self.query)
        revoked = EgressAuthorizationView(
            self.value.authorization_id, self.value.preview_id, self.value.project_id,
            self.value.purpose_ref, self.value.operation_type, self.value.provider_id,
            self.value.provider_config_version_id, self.value.model_id,
            self.value.data_region, self.value.allowed_data_categories,
            self.value.minimal_payload_policy_ref, self.value.max_record_count,
            self.value.max_payload_bytes, self.value.max_input_tokens,
            self.value.max_retry_attempts, self.value.payload_fingerprint,
            self.value.source_refs_fingerprint, self.value.approved_by,
            self.value.approved_role, self.value.approved_at, self.value.valid_until,
            "REVOKED", 1,
            self.value.content_plan_ref,
        )
        with self.assertRaises(EgressAuthorizationOwnerError):
            self.owner(value=revoked).resolve_authorized(object(), query=self.query)

    def test_registry_rejects_empty_policy(self):
        with self.assertRaises(ValueError):
            AITaskEgressPurposeRegistry({})


if __name__ == "__main__":
    unittest.main()
