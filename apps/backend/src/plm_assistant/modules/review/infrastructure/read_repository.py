"""Trusted caller transaction, Core mappings and shared current-fact locks."""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewBasisObservation, ReviewIdentitySnapshot,
    ReviewSnapshotReadError, valid_scope,
)
from ..domain.round_progress import ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress, ReviewWithdrawalSnapshot
from .orm import _tables


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReviewSnapshotReadError()
    return value.astimezone(timezone.utc)


class SqlAlchemyReviewSnapshotReadRepository:
    def _session(self, transaction, scope, project_id, *identities):
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Review caller transaction required")
        if not valid_scope(scope, project_id) or any(type(v) is not UUID or not v.int for v in identities):
            raise ValueError("validated Review Scope and identity required")
        return session

    def get_review(self, transaction, scope, project_id, review_id):
        session = self._session(transaction, scope, project_id, review_id)
        t = _tables[0]
        row = session.execute(select(t).where(t.c.review_id == review_id, t.c.scope == scope,
            t.c.project_id.is_(None) if project_id is None else t.c.project_id == project_id
        ).with_for_update(read=True)).mappings().one_or_none()
        if row is None:
            return None
        rounds = self._rows(session, 1, review_id)
        if (row["lock_version"] != len(rounds)+sum(r["lock_version"] for r in rounds)
                or [r["round_no"] for r in rounds] != list(range(1, len(rounds)+1))):
            raise ReviewSnapshotReadError()
        active = [r["review_round_id"] for r in rounds if r["round_state"] == "IN_REVIEW"]
        if (len(active) > 1 or row["active_round_id"] != (active[0] if active else None)
                or row["review_state"] != ("IN_REVIEW" if active else rounds[-1]["round_state"] if rounds else "DRAFT")):
            raise ReviewSnapshotReadError()
        return ReviewIdentitySnapshot(row["review_id"], scope, project_id, row["subject_type"], row["subject_id"],
                                      row["policy_code"], row["review_state"], row["active_round_id"], row["lock_version"])

    def _rows(self, session, index, review_id, round_id=None):
        table = _tables[index]
        query = select(table).where(table.c.review_id == review_id)
        if round_id is not None:
            query = query.where(table.c.review_round_id == round_id)
        order = table.c.round_no if index == 1 else table.c.reviewer_id if index in (2, 3) else list(table.primary_key.columns)[0]
        return session.execute(query.order_by(order)).mappings().all()

    def get_round_subject_version(self, transaction, scope, project_id, review_id, round_id):
        """Locate immutable version under root lock, before acquiring Owner/round locks."""
        session = self._session(transaction, scope, project_id, review_id, round_id)
        if self.get_review(transaction, scope, project_id, review_id) is None:
            return None
        table = _tables[1]
        version = session.execute(select(table.c.subject_version_id).where(
            table.c.review_id == review_id, table.c.review_round_id == round_id,
            table.c.scope == scope,
            table.c.project_id.is_(None) if project_id is None else table.c.project_id == project_id,
        )).scalar_one_or_none()
        if version is not None and (type(version) is not UUID or not version.int):
            raise ReviewSnapshotReadError()
        return version

    def get_round(self, transaction, scope, project_id, review_id, round_id):
        session = self._session(transaction, scope, project_id, review_id, round_id)
        identity = self.get_review(transaction, scope, project_id, review_id)
        if identity is None:
            return None
        table = _tables[1]
        row = session.execute(select(table).where(table.c.review_id == review_id, table.c.review_round_id == round_id,
            table.c.scope == scope, table.c.project_id.is_(None) if project_id is None else table.c.project_id == project_id
        ).with_for_update(read=True)).mappings().one_or_none()
        if row is None:
            return None
        parts = {i: self._rows(session, i, review_id, round_id) for i in range(2, 8)}
        if len(parts[4]) != 1 or len(parts[6]) != 1:
            raise ReviewSnapshotReadError()
        for rows in parts.values():
            if any(r["scope"] != scope or r["project_id"] != project_id for r in rows):
                raise ReviewSnapshotReadError()
        assignments, decisions, snapshots, refs, locks, events = (parts[i] for i in range(2, 8))
        snap, lock = snapshots[0], locks[0]
        if (snap["subject_type"] != identity.subject_type or snap["subject_id"] != identity.subject_id
                or snap["subject_version_id"] != row["subject_version_id"]
                or lock["subject_type"] != identity.subject_type or lock["subject_id"] != identity.subject_id
                or lock["lock_state"] != ("ACTIVE" if row["round_state"] == "IN_REVIEW" else "RELEASED")
                or any(r["snapshot_id"] != snap["snapshot_id"] for r in refs)):
            raise ReviewSnapshotReadError()
        assigned = {a["reviewer_id"]: a for a in assignments}
        if len(assigned) != len(assignments):
            raise ReviewSnapshotReadError()
        decided = set()
        for d in decisions:
            if (d["reviewer_id"] not in assigned or assigned[d["reviewer_id"]]["assignment_id"] != d["assignment_id"]
                    or assigned[d["reviewer_id"]]["assignment_state"] != "DECIDED"):
                raise ReviewSnapshotReadError()
            decided.add(d["reviewer_id"])
        if any(a["assignment_state"] != ("DECIDED" if user in decided else "PENDING") for user, a in assigned.items()):
            raise ReviewSnapshotReadError()
        withdrawal_events = [e for e in events if e["event_type"] == "WITHDRAWN"]
        start_events = [e for e in events if e["event_type"] == "STARTED"]
        decision_events = [e for e in events if e["event_type"] == "DECISION_RECORDED"]
        completion_events = [e for e in events if e["event_type"] == "COMPLETED"]
        if (len(start_events) != 1 or start_events[0]["actor_id"] != row["started_by"]
                or start_events[0]["after_lock_version"] != 0
                or len(withdrawal_events) != (row["round_state"] == "WITHDRAWN")
                or len(decision_events) != len(decisions)
                or len(completion_events) != (row["round_state"] in ("APPROVED", "RETURNED"))
                or len(events) != 1+len(decision_events)+len(completion_events)+len(withdrawal_events)):
            raise ReviewSnapshotReadError()
        for d in decisions:
            matching = [e for e in decision_events if e["decision_id"] == d["decision_id"]]
            if (len(matching) != 1 or matching[0]["actor_id"] != d["reviewer_id"]
                    or matching[0]["after_lock_version"] != d["round_after_version"]):
                raise ReviewSnapshotReadError()
        try:
            withdrawal = None if not withdrawal_events else ReviewWithdrawalSnapshot(
                withdrawal_events[0]["actor_id"], _utc(withdrawal_events[0]["occurred_at"]),
                withdrawal_events[0]["withdrawal_reason"])
            progress = ReviewRoundProgress(round_id, _utc(row["started_at"]), tuple(assigned), tuple(
                ReviewDecisionSnapshot(d["decision_id"], round_id, d["reviewer_id"], ReviewDecisionKind(d["decision"]),
                    _utc(d["decided_at"]), d["comment"]) for d in decisions), withdrawal)
            if progress.state.value != row["round_state"]:
                raise ReviewSnapshotReadError()
            return FixedReviewRoundSnapshot(identity, row["round_no"], row["subject_version_id"], row["started_by"],
                progress, tuple(a["assignment_id"] for a in assignments), row["lock_version"], snap["snapshot_id"],
                bytes(snap["content_fingerprint"]), snap["proof_schema_version"], _utc(snap["verified_at"]),
                tuple(ReviewBasisObservation(r["ref_kind"], r["ref_id"], r["ref_scope"], r["ref_project_id"],
                    r["observed_state"], r["observed_lock_version"], bytes(r["content_fingerprint"]), _utc(r["verified_at"])) for r in refs),
                lock["subject_lock_id"], _utc(lock["acquired_at"]), None if lock["released_at"] is None else _utc(lock["released_at"]))
        except ValueError:
            raise ReviewSnapshotReadError() from None
