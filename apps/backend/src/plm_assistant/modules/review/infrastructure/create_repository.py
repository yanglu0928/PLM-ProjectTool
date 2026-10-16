"""Review-owned insertion and immutable creation fields, no business Owner SQL."""
from datetime import timezone
from sqlalchemy import insert, select
from sqlalchemy.orm import Session
from ..application.create_review import AuthorizedReviewCreation, CreatedReviewRef
from .orm import _tables


class SqlAlchemyReviewCreationRepository:
    @staticmethod
    def _session(tx):
        session = getattr(tx, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Review creation transaction required")
        return session

    @staticmethod
    def _result(row):
        return CreatedReviewRef(row["review_id"], row["project_id"], row["subject_type"], row["subject_id"],
            row["policy_code"], row["created_by"], row["created_at"].astimezone(timezone.utc))

    def create(self, tx, *, proof):
        if type(proof) is not AuthorizedReviewCreation:
            raise ValueError("validated Review creation proof required")
        table = _tables[0]
        row = self._session(tx).execute(insert(table).values(scope="PROJECT", project_id=proof.project_id,
            subject_type=proof.subject_type, subject_id=proof.subject_id, policy_code=proof.policy_code,
            created_by=proof.user_id).returning(table)).mappings().one()
        return self._result(row)

    def get_created(self, tx, *, project_id, review_id):
        table = _tables[0]
        row = self._session(tx).execute(select(table).where(table.c.scope == "PROJECT",
            table.c.project_id == project_id, table.c.review_id == review_id).with_for_update(read=True)).mappings().one_or_none()
        return None if row is None else self._result(row)
