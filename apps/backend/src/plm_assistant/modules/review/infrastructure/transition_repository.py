"""Review-owned writes under root exclusive lock, caller owns transaction."""
from datetime import timezone
from sqlalchemy import select, insert, update, func
from .orm import _tables
from .start_repository import SqlAlchemyReviewStartRepository
from .read_repository import SqlAlchemyReviewSnapshotReadRepository
from ..application.persist_round import ReviewRoundPersistError
from ..application.persist_transition import AppliedReviewTransitionRef
from ..domain.round_progress import ReviewRoundState, ReviewRoundProgress, _uuid


class SqlAlchemyReviewTransitionRepository:
    _session = staticmethod(SqlAlchemyReviewStartRepository._session)

    def lock_transition_context(self, tx, *, project_id, review_id, round_id):
        session, root = self._session(tx), _tables[0]
        found = session.execute(select(root.c.review_id).where(root.c.review_id==review_id,
            root.c.scope=="PROJECT",root.c.project_id==project_id).with_for_update()).scalar_one_or_none()
        if found is None:
            return None
        return SqlAlchemyReviewSnapshotReadRepository().get_round(tx,"PROJECT",project_id,review_id,round_id)

    def new_decision_id(self, tx):
        return self._session(tx).execute(select(func.uuidv7())).scalar_one()

    def apply_transition(self, tx, *, intent):
        intent.__post_init__()
        session, old, new = self._session(tx), intent.before, intent.after_progress
        current = self.lock_transition_context(tx,project_id=old.review.project_id,
                                              review_id=old.review.review_id,round_id=old.progress.round_id)
        if current != old:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        parent = dict(review_id=old.review.review_id,review_round_id=new.round_id,scope="PROJECT",project_id=old.review.project_id)
        version = old.round_lock_version+1
        decision_id = None
        if new.withdrawal is None:
            decision = new.decisions[-1]
            index = old.progress.reviewer_ids.index(intent.actor_id)
            assignment = old.assignment_ids[index]
            decision_id = decision.decision_id
            session.execute(insert(_tables[3]).values(**parent,decision_id=decision_id,assignment_id=assignment,
                reviewer_id=intent.actor_id,decision=decision.kind.value,comment=decision.comment,
                decided_at=intent.occurred_at,trace_id=intent.trace_id))
            changed = session.execute(update(_tables[2]).where(_tables[2].c.assignment_id==assignment,
                _tables[2].c.assignment_state=="PENDING").values(assignment_state="DECIDED"))
            if changed.rowcount != 1:
                raise ReviewRoundPersistError("REVIEW_DECISION_EXISTS")
        changed = session.execute(update(_tables[1]).where(_tables[1].c.review_round_id==new.round_id,
            _tables[1].c.lock_version==old.round_lock_version,_tables[1].c.round_state=="IN_REVIEW"
        ).values(round_state=new.state.value,lock_version=version))
        if changed.rowcount != 1:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        changed = session.execute(update(_tables[0]).where(_tables[0].c.review_id==old.review.review_id,
            _tables[0].c.lock_version==old.review.lock_version,_tables[0].c.active_round_id==new.round_id
        ).values(review_state=new.state.value,active_round_id=None if intent.terminal else new.round_id,
                 lock_version=old.review.lock_version+1))
        if changed.rowcount != 1:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        if intent.terminal:
            changed = session.execute(update(_tables[6]).where(_tables[6].c.subject_lock_id==old.subject_lock_id,
                _tables[6].c.lock_state=="ACTIVE").values(lock_state="RELEASED",released_at=intent.occurred_at))
            if changed.rowcount != 1:
                raise ReviewRoundPersistError()
        common = dict(parent,actor_id=intent.actor_id,trace_id=intent.trace_id,occurred_at=intent.occurred_at,
                      before_lock_version=old.round_lock_version,after_lock_version=version,result_state=new.state.value)
        if new.withdrawal is not None:
            event_id = session.execute(insert(_tables[7]).values(**common,event_type="WITHDRAWN",
                decision_id=None,withdrawal_reason=new.withdrawal.reason).returning(_tables[7].c.round_event_id)).scalar_one()
        else:
            event_id = session.execute(insert(_tables[7]).values(**common,event_type="DECISION_RECORDED",
                decision_id=decision_id).returning(_tables[7].c.round_event_id)).scalar_one()
            if intent.terminal:
                session.execute(insert(_tables[7]).values(**common,event_type="COMPLETED",decision_id=None))
        return AppliedReviewTransitionRef(old.review.project_id,old.review.review_id,new.round_id,
            old.subject_version_id,intent.actor_id,intent.occurred_at,"WITHDRAW" if new.withdrawal else "DECIDE",
            new.state,old.review.lock_version+1,version,decision_id,event_id)

    def get_transition_ref(self, tx, *, project_id, review_id, round_id, event_id):
        """Original response from sealed command event, NOT current status.

        Requires caller transaction/authz; no write or commit. Root lock keeps
        structural history consistent. No current Source or Subject permission
        inferred from historical snapshot. Receipt entry point rechecks access.
        """
        if not all(_uuid(v) for v in (project_id,review_id,round_id,event_id)):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        fixed = self.lock_transition_context(tx,project_id=project_id,review_id=review_id,round_id=round_id)
        if fixed is None:
            return None
        table = _tables[7]
        row = self._session(tx).execute(select(table).where(table.c.round_event_id==event_id,
            table.c.review_id==review_id,table.c.review_round_id==round_id,
            table.c.scope=="PROJECT",table.c.project_id==project_id,
            table.c.event_type.in_(("DECISION_RECORDED","WITHDRAWN")))).mappings().one_or_none()
        if row is None:
            return None
        if (type(row["after_lock_version"]) is not int
                or not 0 < row["after_lock_version"] <= fixed.round_lock_version):
            raise ReviewRoundPersistError()
        progress = fixed.progress
        if row["event_type"] == "WITHDRAWN":
            if (progress.withdrawal is None or row["actor_id"] != progress.withdrawal.actor_id
                    or row["withdrawal_reason"] != progress.withdrawal.reason
                    or row["result_state"] != "WITHDRAWN"):
                raise ReviewRoundPersistError()
        else:
            decision = next((d for d in progress.decisions if d.decision_id==row["decision_id"]),None)
            if decision is None or decision.reviewer_id != row["actor_id"]:
                raise ReviewRoundPersistError()
        decisions = _tables[3]
        versions = self._session(tx).execute(select(decisions.c.decision_id,decisions.c.round_after_version).where(
            decisions.c.review_id==review_id,decisions.c.review_round_id==round_id,
            decisions.c.scope=="PROJECT",decisions.c.project_id==project_id
        ).order_by(decisions.c.round_after_version)).all()
        if ([v.round_after_version for v in versions] != list(range(1,len(progress.decisions)+1))
                or {v.decision_id for v in versions} != {d.decision_id for d in progress.decisions}):
            raise ReviewRoundPersistError()
        by_id = {d.decision_id:d for d in progress.decisions}
        prefix = tuple(by_id[v.decision_id] for v in versions if v.round_after_version <= row["after_lock_version"])
        withdrawal = progress.withdrawal if row["event_type"]=="WITHDRAWN" else None
        original = ReviewRoundProgress(round_id,progress.started_at,progress.reviewer_ids,prefix,withdrawal)
        if (row["after_lock_version"] != len(prefix)+(withdrawal is not None)
                or original.state.value != row["result_state"]
                or any(d.decided_at > row["occurred_at"] for d in prefix)):
            raise ReviewRoundPersistError()
        rounds = _tables[1]
        previous = self._session(tx).execute(select(rounds.c.round_no,rounds.c.round_state,rounds.c.lock_version).where(
            rounds.c.review_id==review_id,rounds.c.scope=="PROJECT",rounds.c.project_id==project_id,
            rounds.c.round_no < fixed.round_no).order_by(rounds.c.round_no)).all()
        if ([r.round_no for r in previous] != list(range(1,fixed.round_no))
                or any(r.round_state not in ("APPROVED","RETURNED","WITHDRAWN") for r in previous)):
            raise ReviewRoundPersistError()
        # Earlier rounds are permanently sealed. Future rounds/current root
        # must not change this original response's root-after counter.
        root_version = fixed.round_no+sum(r.lock_version for r in previous)+row["after_lock_version"]
        return AppliedReviewTransitionRef(project_id,review_id,round_id,fixed.subject_version_id,row["actor_id"],
            row["occurred_at"].astimezone(timezone.utc),"WITHDRAW" if row["event_type"]=="WITHDRAWN" else "DECIDE",
            ReviewRoundState(row["result_state"]),root_version,row["after_lock_version"],row["decision_id"],event_id)
