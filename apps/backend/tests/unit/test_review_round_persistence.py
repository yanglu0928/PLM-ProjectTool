from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock
import unittest
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot
from plm_assistant.modules.review.application.subject_start import PreparedReviewSubject, ReviewSubjectStartPort
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistenceService, ReviewRoundPersistError, StartedReviewRoundRef


class RoundPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.now, self.tx = datetime.now(timezone.utc), Mock()
        self.root = ReviewIdentitySnapshot(uuid4(), "PROJECT", uuid4(), "HND-02", uuid4(), "SYNTHETIC_ALL_V1", "DRAFT", None, 0)
        self.round, self.actor, self.version = uuid4(), uuid4(), uuid4()
        self.repo, self.owner, self.audit = Mock(), Mock(spec=ReviewSubjectStartPort), Mock()
        self.repo.lock_start_context.return_value = self.root, self.round
        self.owner.prepare_start_in_transaction.side_effect = lambda tx, r: PreparedReviewSubject(r, b"s"*32, 1, self.now, r.reviewer_ids, ())
        self.owner.assert_active_lock_in_transaction.return_value = None
        self.result = StartedReviewRoundRef(self.round, self.root.review_id, self.root.project_id, 1, self.version, self.actor, self.now)
        self.repo.insert_round.return_value = self.result
        self.params = dict(actor_id=self.actor, project_id=self.root.project_id, review_id=self.root.review_id,
            subject_version_id=self.version, reviewer_ids=(uuid4(),), expected_version=0, trace_id=uuid4())

    def service(self, **k): return ReviewRoundPersistenceService(**(dict(repository=self.repo, audit=self.audit, subjects=self.owner, clock=lambda: self.now) | k))
    def call(self, **k): return self.service().start_in_transaction(self.tx, **(self.params | k))

    def test_owner_lock_checked_twice_same_tx_no_commit(self):
        self.assertEqual(self.call(), self.result)
        self.assertEqual(self.owner.assert_active_lock_in_transaction.call_count, 2)
        self.tx.commit.assert_not_called()
        for method in (self.owner.prepare_start_in_transaction, self.owner.assert_active_lock_in_transaction, self.repo.insert_round, self.audit.append):
            self.assertTrue(all(c.args[0] is self.tx for c in method.call_args_list))
        self.assertEqual(self.audit.append.call_args.args[1].action, "REVIEW_STARTED")

    def test_missing_owner_version_conflict_and_active_root_stop_insert(self):
        with self.assertRaises(ReviewRoundPersistError): self.service(subjects=None).start_in_transaction(self.tx, **self.params)
        with self.assertRaises(ReviewRoundPersistError) as exc: self.call(expected_version=1)
        self.assertEqual(exc.exception.code, "CONFLICT_VERSION")
        self.repo.lock_start_context.return_value = replace(self.root, state="IN_REVIEW", active_round_id=uuid4(), lock_version=1), self.round
        with self.assertRaises(ReviewRoundPersistError) as exc: self.call(expected_version=1)
        self.assertEqual(exc.exception.code, "REVIEW_SUBJECT_LOCKED")
        self.repo.insert_round.assert_not_called()

    def test_wrong_binding_or_bool_lock_marker_rejected(self):
        self.owner.prepare_start_in_transaction.side_effect = lambda tx, r: PreparedReviewSubject(replace(r, round_id=uuid4()), b"s"*32, 1, self.now, r.reviewer_ids, ())
        with self.assertRaises(ValueError): self.call()
        self.owner.prepare_start_in_transaction.side_effect = lambda tx, r: PreparedReviewSubject(r,b"s"*32,1,self.now,r.reviewer_ids,())
        self.owner.assert_active_lock_in_transaction.return_value = True
        with self.assertRaises(ReviewRoundPersistError): self.call()
        self.repo.insert_round.assert_not_called()

    def test_second_lock_failure_or_audit_error_propagates_without_commit(self):
        self.owner.assert_active_lock_in_transaction.side_effect = [None, RuntimeError("synthetic changed Owner lock")]
        with self.assertRaises(RuntimeError): self.call()
        self.audit.append.assert_not_called()
        self.tx.commit.assert_not_called()

    def test_foreign_root_and_wrong_result_rejected(self):
        self.repo.lock_start_context.return_value = replace(self.root, project_id=uuid4()), self.round
        with self.assertRaises(ReviewRoundPersistError): self.call()
        self.repo.lock_start_context.return_value = self.root, self.round
        self.repo.insert_round.return_value = replace(self.result, subject_version_id=uuid4())
        with self.assertRaises(ReviewRoundPersistError): self.call()
        self.audit.append.assert_not_called()
