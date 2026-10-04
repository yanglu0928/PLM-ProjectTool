"""Review-owned GLOBAL persistence; no Subject, auth or receipt SQL."""

from datetime import timezone

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..application.global_persistence import (
    AppliedGlobalReviewTransitionRef,
    SubmittedGlobalReviewRef,
)
from ..application.persist_round import ReviewRoundPersistError
from ..application.read_snapshot import ReviewIdentitySnapshot
from ..domain.round_progress import ReviewRoundProgress, ReviewRoundState, _uuid
from .orm import _tables
from .read_repository import SqlAlchemyReviewSnapshotReadRepository


class SqlAlchemyGlobalReviewRepository:
    @staticmethod
    def is_retryable_deadlock(error):
        return (isinstance(error, DBAPIError)
                and getattr(error.orig, "sqlstate", None) == "40P01")

    @staticmethod
    def _session(tx):
        session = getattr(tx, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active GLOBAL Review transaction required")
        return session

    def insert_global_identity(
        self, tx, *, actor_id, subject_type, subject_id, policy_code,
    ):
        table = _tables[0]
        row = self._session(tx).execute(insert(table).values(
            scope="GLOBAL", project_id=None, subject_type=subject_type,
            subject_id=subject_id, policy_code=policy_code,
            created_by=actor_id,
        ).returning(table)).mappings().one()
        identity = ReviewIdentitySnapshot(
            row["review_id"], "GLOBAL", None, row["subject_type"],
            row["subject_id"], row["policy_code"], row["review_state"],
            row["active_round_id"], row["lock_version"],
        )
        round_id = self._session(tx).execute(select(func.uuidv7())).scalar_one()
        return identity, round_id

    def lock_global_start_context(self, tx, *, review_id):
        session, table = self._session(tx), _tables[0]
        row = session.execute(select(table).where(
            table.c.scope == "GLOBAL", table.c.project_id.is_(None),
            table.c.review_id == review_id,
        ).with_for_update()).mappings().one_or_none()
        if row is None:
            return None
        return ReviewIdentitySnapshot(
            row["review_id"], "GLOBAL", None, row["subject_type"],
            row["subject_id"], row["policy_code"], row["review_state"],
            row["active_round_id"], row["lock_version"],
        )

    def insert_global_round(self, tx, *, prepared, trace_id, started_at):
        session = self._session(tx)
        prepared.__post_init__()
        request, root = prepared.request, prepared.request.review
        current = self.lock_global_start_context(
            tx, review_id=root.review_id,
        )
        if current != root:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        rounds = _tables[1]
        number = session.execute(select(
            func.coalesce(func.max(rounds.c.round_no), 0) + 1,
        ).where(rounds.c.review_id == root.review_id)).scalar_one()
        parent = dict(
            review_id=root.review_id, scope="GLOBAL", project_id=None,
        )
        child = dict(parent, review_round_id=request.round_id)
        session.execute(insert(rounds).values(
            **child, round_no=number,
            subject_version_id=request.subject_version_id,
            round_state="IN_REVIEW", started_by=request.actor_id,
            started_at=started_at,
        ))
        for user in request.reviewer_ids:
            session.execute(insert(_tables[2]).values(
                **child, reviewer_id=user,
            ))
        snapshot_id = session.execute(insert(_tables[4]).values(
            **child, subject_type=root.subject_type,
            subject_id=root.subject_id,
            subject_version_id=request.subject_version_id,
            content_fingerprint=prepared.content_fingerprint,
            proof_schema_version=prepared.proof_schema_version,
            verified_at=prepared.verified_at,
        ).returning(_tables[4].c.snapshot_id)).scalar_one()
        for ref in prepared.basis:
            session.execute(insert(_tables[5]).values(
                **child, snapshot_id=snapshot_id, ref_kind=ref.ref_kind,
                ref_id=ref.ref_id, ref_scope=ref.ref_scope,
                ref_project_id=ref.ref_project_id,
                observed_state=ref.observed_state,
                observed_lock_version=ref.observed_lock_version,
                content_fingerprint=ref.content_fingerprint,
                verified_at=ref.verified_at,
            ))
        session.execute(insert(_tables[6]).values(
            **child, subject_type=root.subject_type,
            subject_id=root.subject_id, acquired_at=started_at,
        ))
        changed = session.execute(update(_tables[0]).where(
            _tables[0].c.review_id == root.review_id,
            _tables[0].c.scope == "GLOBAL",
            _tables[0].c.project_id.is_(None),
            _tables[0].c.lock_version == root.lock_version,
        ).values(
            review_state="IN_REVIEW",
            active_round_id=request.round_id,
            lock_version=root.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        session.execute(insert(_tables[7]).values(
            **child, event_type="STARTED", actor_id=request.actor_id,
            trace_id=trace_id, occurred_at=started_at,
            before_lock_version=None, after_lock_version=0,
            result_state="IN_REVIEW",
        ))
        return SubmittedGlobalReviewRef(
            root.review_id, request.round_id, root.subject_type,
            root.subject_id, request.subject_version_id, root.policy_code,
            request.reviewer_ids, request.actor_id, started_at,
            root.lock_version + 1, number,
        )

    def lock_global_transition_context(self, tx, *, review_id, round_id):
        session, root = self._session(tx), _tables[0]
        found = session.execute(select(root.c.review_id).where(
            root.c.review_id == review_id, root.c.scope == "GLOBAL",
            root.c.project_id.is_(None),
        ).with_for_update()).scalar_one_or_none()
        if found is None:
            return None
        return SqlAlchemyReviewSnapshotReadRepository().get_round(
            tx, "GLOBAL", None, review_id, round_id,
        )

    def new_decision_id(self, tx):
        return self._session(tx).execute(select(func.uuidv7())).scalar_one()

    def apply_global_transition(self, tx, *, intent):
        intent.__post_init__()
        session, old, new = self._session(tx), intent.before, intent.after_progress
        current = self.lock_global_transition_context(
            tx, review_id=old.review.review_id,
            round_id=old.progress.round_id,
        )
        if current != old:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        parent = dict(
            review_id=old.review.review_id,
            review_round_id=new.round_id,
            scope="GLOBAL", project_id=None,
        )
        version = old.round_lock_version + 1
        decision_id = None
        if new.withdrawal is None:
            decision = new.decisions[-1]
            index = old.progress.reviewer_ids.index(intent.actor_id)
            assignment = old.assignment_ids[index]
            decision_id = decision.decision_id
            session.execute(insert(_tables[3]).values(
                **parent, decision_id=decision_id, assignment_id=assignment,
                reviewer_id=intent.actor_id, decision=decision.kind.value,
                comment=decision.comment, decided_at=intent.occurred_at,
                trace_id=intent.trace_id,
            ))
            changed = session.execute(update(_tables[2]).where(
                _tables[2].c.assignment_id == assignment,
                _tables[2].c.assignment_state == "PENDING",
            ).values(assignment_state="DECIDED"))
            if changed.rowcount != 1:
                raise ReviewRoundPersistError("REVIEW_DECISION_EXISTS")
        changed = session.execute(update(_tables[1]).where(
            _tables[1].c.review_round_id == new.round_id,
            _tables[1].c.scope == "GLOBAL",
            _tables[1].c.project_id.is_(None),
            _tables[1].c.lock_version == old.round_lock_version,
            _tables[1].c.round_state == "IN_REVIEW",
        ).values(round_state=new.state.value, lock_version=version))
        if changed.rowcount != 1:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        changed = session.execute(update(_tables[0]).where(
            _tables[0].c.review_id == old.review.review_id,
            _tables[0].c.scope == "GLOBAL",
            _tables[0].c.project_id.is_(None),
            _tables[0].c.lock_version == old.review.lock_version,
            _tables[0].c.active_round_id == new.round_id,
        ).values(
            review_state=new.state.value,
            active_round_id=None if intent.terminal else new.round_id,
            lock_version=old.review.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        if intent.terminal:
            changed = session.execute(update(_tables[6]).where(
                _tables[6].c.subject_lock_id == old.subject_lock_id,
                _tables[6].c.scope == "GLOBAL",
                _tables[6].c.project_id.is_(None),
                _tables[6].c.lock_state == "ACTIVE",
            ).values(
                lock_state="RELEASED", released_at=intent.occurred_at,
            ))
            if changed.rowcount != 1:
                raise ReviewRoundPersistError()
        common = dict(
            parent, actor_id=intent.actor_id, trace_id=intent.trace_id,
            occurred_at=intent.occurred_at,
            before_lock_version=old.round_lock_version,
            after_lock_version=version, result_state=new.state.value,
        )
        if new.withdrawal is not None:
            event_id = session.execute(insert(_tables[7]).values(
                **common, event_type="WITHDRAWN", decision_id=None,
                withdrawal_reason=new.withdrawal.reason,
            ).returning(_tables[7].c.round_event_id)).scalar_one()
        else:
            event_id = session.execute(insert(_tables[7]).values(
                **common, event_type="DECISION_RECORDED",
                decision_id=decision_id,
            ).returning(_tables[7].c.round_event_id)).scalar_one()
            if intent.terminal:
                session.execute(insert(_tables[7]).values(
                    **common, event_type="COMPLETED", decision_id=None,
                ))
        return AppliedGlobalReviewTransitionRef(
            old.review.review_id, new.round_id, old.subject_version_id,
            intent.actor_id, intent.occurred_at,
            "WITHDRAW" if new.withdrawal else "DECIDE", new.state,
            old.review.lock_version + 1, version, decision_id, event_id,
        )

    def get_global_transition_ref(
        self, tx, *, review_id, round_id, event_id,
    ):
        if not all(_uuid(value) for value in (review_id, round_id, event_id)):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        fixed = self.lock_global_transition_context(
            tx, review_id=review_id, round_id=round_id,
        )
        if fixed is None:
            return None
        table = _tables[7]
        row = self._session(tx).execute(select(table).where(
            table.c.round_event_id == event_id,
            table.c.review_id == review_id,
            table.c.review_round_id == round_id,
            table.c.scope == "GLOBAL", table.c.project_id.is_(None),
            table.c.event_type.in_(("DECISION_RECORDED", "WITHDRAWN")),
        )).mappings().one_or_none()
        if row is None:
            return None
        if (type(row["after_lock_version"]) is not int
                or not 0 < row["after_lock_version"] <= fixed.round_lock_version):
            raise ReviewRoundPersistError()
        progress = fixed.progress
        if row["event_type"] == "WITHDRAWN":
            if (progress.withdrawal is None
                    or row["actor_id"] != progress.withdrawal.actor_id
                    or row["withdrawal_reason"] != progress.withdrawal.reason
                    or row["result_state"] != "WITHDRAWN"):
                raise ReviewRoundPersistError()
        else:
            decision = next((item for item in progress.decisions
                             if item.decision_id == row["decision_id"]), None)
            if decision is None or decision.reviewer_id != row["actor_id"]:
                raise ReviewRoundPersistError()
        decisions = _tables[3]
        versions = self._session(tx).execute(select(
            decisions.c.decision_id, decisions.c.round_after_version,
        ).where(
            decisions.c.review_id == review_id,
            decisions.c.review_round_id == round_id,
            decisions.c.scope == "GLOBAL", decisions.c.project_id.is_(None),
        ).order_by(decisions.c.round_after_version)).all()
        if ([value.round_after_version for value in versions]
                != list(range(1, len(progress.decisions) + 1))
                or {value.decision_id for value in versions}
                != {item.decision_id for item in progress.decisions}):
            raise ReviewRoundPersistError()
        by_id = {item.decision_id: item for item in progress.decisions}
        prefix = tuple(by_id[value.decision_id] for value in versions
                       if value.round_after_version <= row["after_lock_version"])
        withdrawal = (progress.withdrawal
                      if row["event_type"] == "WITHDRAWN" else None)
        original = ReviewRoundProgress(
            round_id, progress.started_at, progress.reviewer_ids,
            prefix, withdrawal,
        )
        if (row["after_lock_version"] != len(prefix) + (withdrawal is not None)
                or original.state.value != row["result_state"]
                or any(item.decided_at > row["occurred_at"]
                       for item in prefix)):
            raise ReviewRoundPersistError()
        rounds = _tables[1]
        previous = self._session(tx).execute(select(
            rounds.c.round_no, rounds.c.round_state, rounds.c.lock_version,
        ).where(
            rounds.c.review_id == review_id,
            rounds.c.scope == "GLOBAL", rounds.c.project_id.is_(None),
            rounds.c.round_no < fixed.round_no,
        ).order_by(rounds.c.round_no)).all()
        if ([item.round_no for item in previous]
                != list(range(1, fixed.round_no))
                or any(item.round_state not in (
                    "APPROVED", "RETURNED", "WITHDRAWN",
                ) for item in previous)):
            raise ReviewRoundPersistError()
        root_version = (
            fixed.round_no
            + sum(item.lock_version for item in previous)
            + row["after_lock_version"]
        )
        return AppliedGlobalReviewTransitionRef(
            review_id, round_id, fixed.subject_version_id, row["actor_id"],
            row["occurred_at"].astimezone(timezone.utc),
            "WITHDRAW" if row["event_type"] == "WITHDRAWN" else "DECIDE",
            ReviewRoundState(row["result_state"]), root_version,
            row["after_lock_version"], row["decision_id"], event_id,
        )
