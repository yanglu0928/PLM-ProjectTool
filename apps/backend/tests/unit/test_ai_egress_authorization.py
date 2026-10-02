from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.egress_authorization import (
    AuthorizeEgress, EgressAuthorizationError, EgressAuthorizationService,
    EgressAuthorizationView, EgressAuthorizeResult, EgressRevokeResult, RevokeEgress,
)
from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewSourceView, EgressPreviewView,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class _Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def commit(self): self.committed = True


class _Uow:
    def __init__(self): self.items = []
    def __call__(self):
        tx = _Tx(); self.items.append(tx); return tx


class _Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class _Guard:
    def __init__(self): self.calls = 0
    def require_valid(self, **_kwargs): self.calls += 1; return object()


class _Authorization:
    def __init__(self, actor, project, role="PROJECT_MANAGER"):
        self.actor, self.project, self.role, self.operations = actor, project, role, []
    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        self.operations.append(operation)
        return AuthorizedProjectAction(user_id, project_id, operation, self.role)


class _Policy:
    def __init__(self, allowed=True): self.allowed, self.calls = allowed, 0
    def permits(self, *_args, **_kwargs): self.calls += 1; return self.allowed


class _Receipts:
    def __init__(self, replay=None): self.replay, self.completed = replay, []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, *_args, **kwargs): self.completed.append(kwargs["result"])


class _Audit:
    def __init__(self): self.events = []
    def append(self, _tx, event):
        self.events.append(event); return uuid.uuid4()


class _Repo:
    def __init__(self, preview, authorization):
        self.preview, self.authorization = preview, authorization
        self.created, self.saved, self.revoked = 0, 0, 0
        self.authorize_replay = None
        self.revoke_replay = None

    def preview_for_authorize(self, *_args, **_kwargs): return self.preview
    def create_authorization(self, *_args, **_kwargs):
        self.created += 1; return self.authorization
    def save_authorize_result(self, *_args, **_kwargs): self.saved += 1
    def get_authorize_result(self, *_args, **_kwargs): return self.authorize_replay
    def authorization_for_revoke(self, *_args, **_kwargs): return self.authorization
    def revoke(self, _tx, *, authorization, actor_id, revoked_role,
               audit_event_id, trace_id, **_kwargs):
        self.revoked += 1
        return EgressRevokeResult(
            uuid.uuid4(), authorization.authorization_id, uuid.uuid4(), actor_id,
            revoked_role, audit_event_id, trace_id, "REVOKED", 1,
            authorization.approved_at + timedelta(minutes=1),
        )
    def get_revoke_result(self, *_args, **_kwargs): return self.revoke_replay


class EgressAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 9, tzinfo=timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.preview = EgressPreviewView(
            uuid.uuid4(), self.project, "gap.analysis.v1", "AI_TASK",
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "cn-beijing",
            ("TECHNICAL_DOCUMENT",),
            (EgressPreviewSourceView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            "minimum.document.text.v1", 10, 65536, 4096, 3,
            b"p" * 32, b"s" * 32, ("EXTERNAL_PROVIDER",),
            self.now - timedelta(minutes=1), self.now + timedelta(minutes=30),
        )
        self.authorization_view = EgressAuthorizationView(
            uuid.uuid4(), self.preview.preview_id, self.project,
            self.preview.purpose_ref, self.preview.operation_type,
            self.preview.provider_id, self.preview.provider_config_version_id,
            self.preview.model_id, self.preview.data_region,
            self.preview.allowed_data_categories,
            self.preview.minimal_payload_policy_ref, 10, 65536, 4096, 3,
            self.preview.payload_fingerprint, self.preview.source_refs_fingerprint,
            self.actor, "ProjectManager", self.now,
            self.now + timedelta(minutes=20), "AUTHORIZED", 0,
        )
        self.authorize_command = AuthorizeEgress(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.preview.preview_id, self.preview.preview_fingerprint,
            ("TECHNICAL_DOCUMENT",), 10, 65536, 4096, 3,
            self.now + timedelta(minutes=20),
        )

    def service(self, *, replay=None, policy=True, role="PROJECT_MANAGER"):
        self.uow, self.guard = _Uow(), _Guard()
        self.authorization = _Authorization(self.actor, self.project, role)
        self.policy, self.receipts, self.audit = _Policy(policy), _Receipts(replay), _Audit()
        self.repo = _Repo(self.preview, self.authorization_view)
        return EgressAuthorizationService(
            unit_of_work=self.uow, access=_Access(self.actor), license_guard=self.guard,
            authorization=self.authorization, approval_policy=self.policy,
            repository=self.repo, receipts=self.receipts, audit=self.audit,
            clock=lambda: self.now,
        )

    def test_authorize_creates_atomic_result(self):
        result = self.service().authorize(self.authorize_command, idempotency_key="A" * 16)
        self.assertEqual(result.authorization, self.authorization_view)
        self.assertEqual((self.repo.created, self.repo.saved, self.policy.calls), (1, 1, 1))
        self.assertEqual(self.guard.calls, 2)
        self.assertEqual(len(self.audit.events), 1)
        self.assertEqual(self.receipts.completed[0].ref_type, "V1_EGRESS_AUTHORIZE")
        self.assertTrue(self.uow.items[-1].committed)

    def test_authorize_replays_result_without_policy_or_preview(self):
        stored = EgressAuthorizeResult(
            uuid.uuid4(), self.authorization_view, uuid.uuid4(), uuid.uuid4(),
        )
        receipt = IdempotencyResult("V1_EGRESS_AUTHORIZE", stored.result_id, 201)
        service = self.service(replay=receipt)
        self.repo.authorize_replay = stored
        self.assertEqual(service.authorize(
            self.authorize_command, idempotency_key="B" * 16,
        ), stored)
        self.assertEqual((self.repo.created, self.policy.calls), (0, 0))

    def test_authorize_denies_policy_and_preview_conflict(self):
        with self.assertRaises(EgressAuthorizationError) as denied:
            self.service(policy=False).authorize(
                self.authorize_command, idempotency_key="C" * 16,
            )
        self.assertEqual(denied.exception.code, "AI_EGRESS_APPROVAL_DENIED")
        changed = AuthorizeEgress(
            self.authorize_command.session_token, self.authorize_command.csrf_token,
            self.authorize_command.trace_id, self.project, self.preview.preview_id,
            b"x" * 32, self.authorize_command.allowed_data_categories,
            self.authorize_command.max_record_count,
            self.authorize_command.max_payload_bytes,
            self.authorize_command.max_input_tokens,
            self.authorize_command.max_retry_attempts,
            self.authorize_command.valid_until,
        )
        with self.assertRaises(EgressAuthorizationError) as conflict:
            self.service().authorize(changed, idempotency_key="D" * 16)
        self.assertEqual(conflict.exception.code, "CONFLICT_VERSION")

    def test_revoke_marks_original_approver_and_replays(self):
        command = RevokeEgress(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.authorization_view.authorization_id, 0,
            "USER_REQUEST", "Approval is no longer required",
        )
        result = self.service().revoke(command, idempotency_key="E" * 16)
        self.assertEqual((result.state, result.revoked_role), ("REVOKED", "OriginalApprover"))
        self.assertEqual(self.receipts.completed[0].ref_type, "V1_EGRESS_REVOKE")
        stored = result
        receipt = IdempotencyResult("V1_EGRESS_REVOKE", stored.result_id, 200)
        service = self.service(replay=receipt)
        self.repo.revoke_replay = stored
        self.assertEqual(service.revoke(command, idempotency_key="E" * 16), stored)
        self.assertEqual(self.repo.revoked, 0)

    def test_revoke_rejects_stale_version(self):
        command = RevokeEgress(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.authorization_view.authorization_id, 1,
            "USER_REQUEST", "Approval is no longer required",
        )
        with self.assertRaises(EgressAuthorizationError) as raised:
            self.service().revoke(command, idempotency_key="F" * 16)
        self.assertEqual(raised.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
