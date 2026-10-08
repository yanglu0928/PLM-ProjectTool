from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4, UUID
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewBasisObservation, ReviewIdentitySnapshot, ReviewSnapshotReadError,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionSnapshot, ReviewDecisionKind, ReviewRoundProgress
from plm_assistant.modules.review.infrastructure.read_repository import (
    SqlAlchemyReviewSnapshotReadRepository, _decode_child_row,
)
from plm_assistant.modules.review.infrastructure.orm import _tables


class ReviewReadSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.time = datetime.now(timezone.utc)
        self.project, self.round, self.user = uuid4(), uuid4(), uuid4()
        self.identity = ReviewIdentitySnapshot(uuid4(), "PROJECT", self.project, "HND-02", uuid4(),
                                               "CUSTOMER_ALL_V1", "APPROVED", None, 2)
        self.progress = ReviewRoundProgress(self.round, self.time, (self.user,), (
            ReviewDecisionSnapshot(uuid4(), self.round, self.user, ReviewDecisionKind.APPROVE, self.time),))
        self.basis = ReviewBasisObservation("EVIDENCE", uuid4(), "PROJECT", self.project, "ELIGIBLE", 1, b"e"*32, self.time)
        self.fixed = FixedReviewRoundSnapshot(self.identity, 1, uuid4(), uuid4(), self.progress, (uuid4(),), 1,
            uuid4(), b"r"*32, 1, self.time, (self.basis,), uuid4(), self.time, self.time)

    def test_immutable_historical_round_can_differ_from_current_identity(self):
        current = replace(self.identity, state="IN_REVIEW", active_round_id=uuid4(), lock_version=3)
        historical = replace(self.fixed, review=current)
        self.assertEqual(historical.progress.state.value, "APPROVED")
        self.assertEqual(historical.review.state, "IN_REVIEW")
        with self.assertRaises(FrozenInstanceError):
            historical.subject_version_id = uuid4()

    def test_scope_identity_and_active_pointer_validation(self):
        for changes in (dict(scope="GLOBAL"), dict(project_id=None), dict(project_id=UUID(int=0)),
                        dict(state="IN_REVIEW"), dict(state="DRAFT"), dict(lock_version=True),
                        dict(subject_type="unknown"), dict(policy_code="unknown"), dict(active_round_id=uuid4())):
            with self.subTest(changes=changes), self.assertRaises(ReviewSnapshotReadError):
                replace(self.identity, **changes)
        replace(self.identity, scope="GLOBAL", project_id=None)

    def test_basis_scope_proof_and_trace_no_source_lock(self):
        for changes in (dict(ref_kind="UNKNOWN"), dict(content_fingerprint=b"x"), dict(observed_lock_version=True),
                        dict(observed_state="REVOKED"), dict(verified_at=datetime.now())):
            with self.subTest(changes=changes), self.assertRaises(ReviewSnapshotReadError):
                replace(self.basis, **changes)
        trace = replace(self.basis, ref_kind="TRACE_LINK", observed_state="ACTIVE", observed_lock_version=0)
        with self.assertRaises(ReviewSnapshotReadError):
            replace(trace, observed_lock_version=1)
        for basis in ((replace(self.basis, ref_project_id=uuid4()),), (self.basis, self.basis),
                      (replace(trace, ref_scope="GLOBAL", ref_project_id=None),)):
            with self.assertRaises(ReviewSnapshotReadError):
                replace(self.fixed, basis=basis)
        replace(self.fixed, basis=(replace(self.basis, ref_scope="GLOBAL", ref_project_id=None),))

    def test_missing_fixed_values_inconsistent_versions_and_collections(self):
        for changes in (dict(assignment_ids=()), dict(round_lock_version=0), dict(round_no=True),
                        dict(subject_fingerprint=b"x"), dict(proof_schema_version=True),
                        dict(lock_released_at=None), dict(basis=list(self.fixed.basis)),
                        dict(review=replace(self.identity, lock_version=1))):
            with self.subTest(changes=changes), self.assertRaises(ReviewSnapshotReadError):
                replace(self.fixed, **changes)

    def test_active_progress_requires_current_pointer_and_unreleased_lock(self):
        active = replace(self.progress, decisions=())
        identity = replace(self.identity, state="IN_REVIEW", active_round_id=self.round, lock_version=1)
        valid = replace(self.fixed, review=identity, progress=active, round_lock_version=0, lock_released_at=None)
        self.assertEqual(valid.progress.pending_reviewer_ids, (self.user,))
        with self.assertRaises(ReviewSnapshotReadError):
            replace(valid, review=replace(identity, active_round_id=uuid4()))

    def test_caller_transaction_required_and_safe_error(self):
        with self.assertRaisesRegex(RuntimeError, "active Review caller transaction required"):
            SqlAlchemyReviewSnapshotReadRepository().get_review(SimpleNamespace(session=None),
                                                               "PROJECT", self.project, self.identity.review_id)
        self.assertEqual(str(ReviewSnapshotReadError()), "Review snapshot unavailable")

    def test_repository_rejects_incomplete_fixed_children(self):
        repository = SqlAlchemyReviewSnapshotReadRepository()
        with Session() as session, session.begin():
            tx = SimpleNamespace(session=session)
            result = MagicMock()
            result.mappings.return_value.one_or_none.return_value = {"review_round_id": self.round}
            with patch.object(repository, "get_review", return_value=self.identity), \
                    patch.object(repository, "_child_rows_bundle", return_value={i: [] for i in range(2, 8)}), \
                    patch.object(session, "execute", return_value=result):
                with self.assertRaisesRegex(ReviewSnapshotReadError, "Review snapshot unavailable"):
                    repository.get_round(tx, "PROJECT", self.project, self.identity.review_id, self.round)

    def test_repository_rejects_stale_root_counter(self):
        repository = SqlAlchemyReviewSnapshotReadRepository()
        with Session() as session, session.begin():
            result = MagicMock()
            result.mappings.return_value.one_or_none.return_value = {"lock_version": 2}
            with patch.object(repository, "_rows", return_value=[]), \
                    patch.object(session, "execute", return_value=result):
                with self.assertRaises(ReviewSnapshotReadError):
                    repository.get_review(SimpleNamespace(session=session), "PROJECT", self.project, self.identity.review_id)

    def test_bundled_child_decoder_preserves_native_types_and_rejects_malformed_rows(self):
        for index in range(2, 8):
            table = _tables[index]
            payload = {}
            for column in table.columns:
                kind = str(column.type)
                payload[column.name] = (
                    str(uuid4()) if kind == "UUID" else
                    "\\x" + "ab" * 32 if kind == "BLOB" else
                    self.time.isoformat() if kind == "TIMESTAMP" else
                    1 if kind in ("INTEGER", "BIGINT") else "VALUE"
                )
            with self.subTest(table=table.name):
                decoded = _decode_child_row(index, payload)
                self.assertEqual(set(decoded), set(payload))
                for column in table.columns:
                    if str(column.type) == "UUID":
                        self.assertIsInstance(decoded[column.name], UUID)
                    if str(column.type) == "BLOB":
                        self.assertEqual(decoded[column.name], b"\xab" * 32)
                    if str(column.type) == "TIMESTAMP":
                        self.assertEqual(decoded[column.name], self.time)
                for changed in (
                    {key: value for key, value in payload.items() if key != next(iter(payload))},
                    {**payload, "unexpected": "VALUE"},
                ):
                    with self.assertRaises(ReviewSnapshotReadError):
                        _decode_child_row(index, changed)
                nullable = next((column for column in table.columns if column.nullable), None)
                if nullable is not None:
                    self.assertIsNone(_decode_child_row(
                        index, {**payload, nullable.name: None},
                    )[nullable.name])
                first = next(iter(table.columns))
                with self.assertRaises(ReviewSnapshotReadError):
                    _decode_child_row(index, {**payload, first.name: None})
        for index, field, bad in (
            (2, "review_id", "invalid"),
            (3, "round_after_version", True),
            (4, "content_fingerprint", "not-bytea"),
            (4, "verified_at", "not-a-time"),
            (5, "ref_kind", 7),
        ):
            payload = {}
            for column in _tables[index].columns:
                kind = str(column.type)
                payload[column.name] = (
                    str(uuid4()) if kind == "UUID" else
                    "\\x" + "ab" * 32 if kind == "BLOB" else
                    self.time.isoformat() if kind == "TIMESTAMP" else
                    1 if kind in ("INTEGER", "BIGINT") else "VALUE"
                )
            with self.subTest(index=index, field=field), self.assertRaises(ReviewSnapshotReadError):
                _decode_child_row(index, {**payload, field: bad})

    def test_bundled_children_reject_unknown_bucket_before_review_assembly(self):
        repository = SqlAlchemyReviewSnapshotReadRepository()
        session = MagicMock()
        session.execute.return_value = [(9, {})]
        with self.assertRaises(ReviewSnapshotReadError):
            repository._child_rows_bundle(session, self.identity.review_id, self.round)

    def test_bundled_children_reject_wrong_round_and_duplicate_primary_key(self):
        payload = {}
        for column in _tables[2].columns:
            kind = str(column.type)
            payload[column.name] = str(uuid4()) if kind == "UUID" else "VALUE"
        payload["review_id"] = str(self.identity.review_id)
        payload["review_round_id"] = str(self.round)
        repository = SqlAlchemyReviewSnapshotReadRepository()
        session = MagicMock()
        session.execute.return_value = [(2, {**payload, "review_round_id": str(uuid4())})]
        with self.assertRaises(ReviewSnapshotReadError):
            repository._child_rows_bundle(session, self.identity.review_id, self.round)
        session.execute.return_value = [(2, payload), (2, payload)]
        with self.assertRaises(ReviewSnapshotReadError):
            repository._child_rows_bundle(session, self.identity.review_id, self.round)
