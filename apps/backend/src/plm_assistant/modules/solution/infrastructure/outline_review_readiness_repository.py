"""Same-transaction shared root/latest-version locks for Outline Review."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from .orm import (
    SolutionOutlineRow as Outline,
    SolutionOutlineVersionRow as Version,
)
from .outline_read_repository import SqlAlchemyOutlineReadRepository
from .outline_version_read_repository import SqlAlchemyOutlineVersionReadRepository
from .reference_deidentification_repository import _session


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class SqlAlchemyOutlineReviewReadinessRepository:
    def __init__(self) -> None:
        self._outlines = SqlAlchemyOutlineReadRepository()
        self._versions = SqlAlchemyOutlineVersionReadRepository()

    def lock_latest(self, transaction: object, *, project_id: uuid.UUID,
                    outline_id: uuid.UUID, version_id: uuid.UUID,
                    required_state: str = "DRAFT"):
        if (transaction is None or not all(_id(value) for value in (
                project_id, outline_id, version_id))
                or required_state not in ("DRAFT", "IN_REVIEW")):
            return None
        session = _session(transaction)
        root = session.execute(select(Outline).where(
            Outline.solution_outline_id == outline_id,
            Outline.project_id == project_id).with_for_update(
                read=True, of=Outline)).scalar_one_or_none()
        if root is None or root.outline_state != "ACTIVE":
            return None
        if self._outlines.get_current(
                transaction, project_id=project_id, outline_id=outline_id) is None:
            return None
        latest = session.execute(select(Version).where(
            Version.solution_outline_id == outline_id,
            Version.project_id == project_id).order_by(
                Version.version_no.desc()).limit(1).with_for_update(
                    read=True, of=Version)).scalar_one_or_none()
        if (latest is None or latest.solution_outline_version_id != version_id
                or latest.version_state != required_state):
            return None
        return self._versions.get(
            transaction, project_id=project_id,
            outline_id=outline_id, version_id=version_id)
