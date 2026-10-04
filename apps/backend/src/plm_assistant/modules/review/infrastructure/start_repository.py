"""Complete Review-owned round structure in the caller transaction, no Owner SQL."""
from sqlalchemy import select, insert, update, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from datetime import timezone
from ..application.read_snapshot import ReviewIdentitySnapshot
from ..application.persist_round import StartedReviewRoundRef, ReviewRoundPersistError
from .orm import _tables


class SqlAlchemyReviewStartRepository:
    @staticmethod
    def is_retryable_deadlock(error):
        return isinstance(error,DBAPIError) and getattr(error.orig,"sqlstate",None)=="40P01"

    @staticmethod
    def _session(tx):
        session = getattr(tx, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Review start transaction required")
        return session

    def lock_start_context(self, tx, *, project_id, review_id):
        session, table = self._session(tx), _tables[0]
        row = session.execute(select(table).where(table.c.scope=="PROJECT", table.c.project_id==project_id,
            table.c.review_id==review_id).with_for_update()).mappings().one_or_none()
        if row is None: return None, None
        identity = ReviewIdentitySnapshot(review_id, "PROJECT", project_id, row["subject_type"], row["subject_id"],
            row["policy_code"], row["review_state"], row["active_round_id"], row["lock_version"])
        return identity, session.execute(select(func.uuidv7())).scalar_one()

    def insert_round(self, tx, *, prepared, trace_id, started_at):
        session = self._session(tx)
        prepared.__post_init__()
        request, root = prepared.request, prepared.request.review
        # Re-lock and compare Core current root, never trust stale caller/ORM data.
        current, _ = self.lock_start_context(tx, project_id=root.project_id, review_id=root.review_id)
        if current != root:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        rounds = _tables[1]
        number = session.execute(select(func.coalesce(func.max(rounds.c.round_no), 0)+1).where(rounds.c.review_id==root.review_id)).scalar_one()
        parent = dict(review_id=root.review_id, scope="PROJECT", project_id=root.project_id)
        child = dict(parent, review_round_id=request.round_id)
        session.execute(insert(rounds).values(**child, round_no=number, subject_version_id=request.subject_version_id,
            round_state="IN_REVIEW", started_by=request.actor_id, started_at=started_at))
        for user in request.reviewer_ids:
            session.execute(insert(_tables[2]).values(**child, reviewer_id=user))
        snapshot_id = session.execute(insert(_tables[4]).values(**child, subject_type=root.subject_type,
            subject_id=root.subject_id, subject_version_id=request.subject_version_id, content_fingerprint=prepared.content_fingerprint,
            proof_schema_version=prepared.proof_schema_version, verified_at=prepared.verified_at).returning(_tables[4].c.snapshot_id)).scalar_one()
        for ref in prepared.basis:
            session.execute(insert(_tables[5]).values(**child, snapshot_id=snapshot_id, ref_kind=ref.ref_kind, ref_id=ref.ref_id,
                ref_scope=ref.ref_scope, ref_project_id=ref.ref_project_id, observed_state=ref.observed_state,
                observed_lock_version=ref.observed_lock_version, content_fingerprint=ref.content_fingerprint, verified_at=ref.verified_at))
        session.execute(insert(_tables[6]).values(**child, subject_type=root.subject_type, subject_id=root.subject_id, acquired_at=started_at))
        changed = session.execute(update(_tables[0]).where(_tables[0].c.review_id==root.review_id,
            _tables[0].c.lock_version==root.lock_version).values(review_state="IN_REVIEW", active_round_id=request.round_id,
                lock_version=root.lock_version+1))
        if changed.rowcount != 1: raise ReviewRoundPersistError("CONFLICT_VERSION")
        session.execute(insert(_tables[7]).values(**child, event_type="STARTED", actor_id=request.actor_id, trace_id=trace_id,
            occurred_at=started_at, before_lock_version=None, after_lock_version=0, result_state="IN_REVIEW"))
        return StartedReviewRoundRef(request.round_id, root.review_id, root.project_id, number,
            request.subject_version_id, request.actor_id, started_at)

    def get_started_ref(self, tx, *, project_id, review_id, round_id):
        root, _ = self.lock_start_context(tx,project_id=project_id,review_id=review_id)
        if root is None: return None
        row = self._session(tx).execute(select(_tables[1]).where(_tables[1].c.review_round_id==round_id,
            _tables[1].c.review_id==review_id,_tables[1].c.scope=="PROJECT",_tables[1].c.project_id==project_id
        ).with_for_update(read=True)).mappings().one_or_none()
        if row is None: return None
        reviewers = tuple(self._session(tx).execute(select(_tables[2].c.reviewer_id).where(
            _tables[2].c.review_round_id==round_id,_tables[2].c.review_id==review_id
        ).order_by(_tables[2].c.reviewer_id)).scalars())
        return StartedReviewRoundRef(round_id,review_id,project_id,row["round_no"],row["subject_version_id"],
            row["started_by"],row["started_at"].astimezone(timezone.utc)), reviewers
