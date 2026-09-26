"""Review-owned writes under root exclusive lock, caller owns transaction."""
from sqlalchemy import select, insert, update, func
from .orm import _tables
from .start_repository import SqlAlchemyReviewStartRepository
from .read_repository import SqlAlchemyReviewSnapshotReadRepository
from ..application.persist_round import ReviewRoundPersistError
from ..application.persist_transition import AppliedReviewTransitionRef


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
            session.execute(insert(_tables[7]).values(**common,event_type="WITHDRAWN",
                decision_id=None,withdrawal_reason=new.withdrawal.reason))
        else:
            session.execute(insert(_tables[7]).values(**common,event_type="DECISION_RECORDED",decision_id=decision_id))
            if intent.terminal:
                session.execute(insert(_tables[7]).values(**common,event_type="COMPLETED",decision_id=None))
        return AppliedReviewTransitionRef(old.review.project_id,old.review.review_id,new.round_id,
            old.subject_version_id,intent.actor_id,intent.occurred_at,"WITHDRAW" if new.withdrawal else "DECIDE",
            new.state,old.review.lock_version+1,version,decision_id)
