from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock
import unittest
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.review.application.create_review import (
    CreateReview, CreatedReviewRef, AuthorizedReviewCreation, ReviewCreateError, ReviewCreateService,
)


class Tx:
    committed = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class ReviewCreateTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid4(), uuid4()
        self.command = CreateReview(b"s"*32, b"c"*32, uuid4(), self.project, "HND-02", uuid4(), uuid4())
        self.result = CreatedReviewRef(uuid4(), self.project, "HND-02", self.command.subject_id,
                                       "CUSTOMER_ALL_V1", self.actor, datetime.now(timezone.utc))
        self.tx = Tx()
        self.access, self.projects, self.guard, self.repository, self.receipts, self.audit, self.owner = (Mock() for _ in range(7))
        self.access.authenticated_user.return_value = self.actor
        self.projects.require_in_transaction.return_value = AuthorizedProjectAction(self.actor, self.project, "REVIEW_CREATE", "PROJECT_MANAGER")
        self.receipts.reserve.return_value = None
        self.owner.authorize_create.side_effect = lambda tx, **k: AuthorizedReviewCreation(**k, policy_code="CUSTOMER_ALL_V1")
        self.owner.authorize_replay.return_value = True
        self.repository.create.return_value = self.result
        self.repository.get_created.return_value = self.result

    def service(self, **overrides):
        return ReviewCreateService(**(dict(unit_of_work=lambda: self.tx, access=self.access, projects=self.projects,
            license_guard=self.guard, repository=self.repository, receipts=self.receipts, audit=self.audit, subjects=self.owner) | overrides))

    def run_create(self, **overrides):
        return self.service(**overrides).create_idempotent(self.command, idempotency_key="synthetic-create-key")

    def deny(self, code, **overrides):
        with self.assertRaises(ReviewCreateError) as exc: self.run_create(**overrides)
        self.assertEqual(exc.exception.code, code)
        self.assertFalse(self.tx.committed)

    def test_single_transaction_create_audit_receipt_commit(self):
        self.assertEqual(self.run_create(), self.result)
        self.assertTrue(self.tx.committed)
        for method in (self.access.authenticated_user, self.projects.require_in_transaction, self.receipts.reserve,
                       self.owner.authorize_create, self.repository.create, self.audit.append, self.receipts.complete):
            self.assertIs(method.call_args.args[0], self.tx)
        draft = self.audit.append.call_args.args[1]
        self.assertEqual((draft.action, draft.after_state, draft.target_object_id), ("REVIEW_CREATED", "DRAFT", self.result.review_id))

    def test_replay_stable_ref_no_repeat_create_or_audit(self):
        self.receipts.reserve.return_value = IdempotencyResult("V1_REVIEW", self.result.review_id, 201)
        self.assertEqual(self.run_create(), self.result)
        self.owner.authorize_create.assert_not_called()
        self.repository.create.assert_not_called()
        self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called()

    def test_missing_owner_or_invalid_owner_proof_rejected(self):
        self.deny("RESOURCE_NOT_FOUND", subjects=None)
        self.owner.authorize_create.side_effect = None
        valid = AuthorizedReviewCreation(self.actor, self.project, "HND-02", self.command.subject_id, self.command.subject_version_id, "CUSTOMER_ALL_V1")
        for proof in (None, True, replace(valid, user_id=uuid4()), replace(valid, project_id=uuid4()),
                      replace(valid, subject_id=uuid4()), replace(valid, subject_version_id=uuid4()), replace(valid, policy_code="bad")):
            self.owner.authorize_create.return_value = proof
            self.deny("RESOURCE_NOT_FOUND")
        self.repository.create.assert_not_called()

    def test_non_pm_or_wrong_project_proof_rejected(self):
        valid = self.projects.require_in_transaction.return_value
        for proof in (None, replace(valid, project_role="CUSTOMER_MANAGER"), replace(valid, project_role="IMPLEMENTATION_MEMBER"),
                      replace(valid, project_role="CUSTOMER_MEMBER"), replace(valid, project_role="DEPLOYMENT_ADMIN"),
                      replace(valid, project_id=uuid4()), replace(valid, operation="PROJECT_PATCH")):
            self.projects.require_in_transaction.return_value = proof
            self.deny("RESOURCE_NOT_FOUND")
        self.receipts.reserve.assert_not_called()

    def test_audit_or_receipt_failure_no_commit_safe_error(self):
        self.audit.append.side_effect = RuntimeError("private SQL path")
        self.deny("REVIEW_UNAVAILABLE")
        self.audit.append.side_effect = None
        self.receipts.complete.side_effect = RuntimeError("private SQL path")
        self.deny("REVIEW_UNAVAILABLE")

    def test_replay_revoked_owner_and_malformed_receipt_fail_closed(self):
        self.receipts.reserve.return_value = IdempotencyResult("V1_REVIEW", self.result.review_id, 201)
        self.owner.authorize_replay.return_value = 1
        self.deny("RESOURCE_NOT_FOUND")
        self.receipts.reserve.return_value = IdempotencyResult("V1_PROJECT", self.result.review_id, 201)
        self.deny("REVIEW_UNAVAILABLE")

    def test_foreign_creation_result_rejected(self):
        for result in (None, replace(self.result, project_id=uuid4()), replace(self.result, subject_id=uuid4()),
                       replace(self.result, created_by=uuid4()), replace(self.result, policy_code="OTHER_V1")):
            self.repository.create.return_value = result
            self.deny("REVIEW_UNAVAILABLE")

    def test_bad_command_key_or_time_and_token_repr(self):
        for changes in (dict(subject_type="unknown"), dict(subject_version_id=None), dict(project_id=True), dict(csrf_token=b"c")):
            with self.assertRaises(ReviewCreateError):
                self.service().create_idempotent(replace(self.command, **changes), idempotency_key="synthetic-create-key")
        with self.assertRaises(ReviewCreateError): self.service().create_idempotent(self.command, idempotency_key="short")
        self.guard.require_valid.assert_not_called()
        self.deny("REVIEW_UNAVAILABLE", clock=lambda: datetime.now())
        self.assertNotIn("ssss", repr(self.command))
