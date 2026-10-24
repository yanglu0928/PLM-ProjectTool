"""Exclusive current Outline root and immutable version-chain base."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from plm_assistant.modules.solution.application.prove_outline_version_input import (
    CurrentOutlineVersionBase,
)

from .orm import SolutionOutlineRow as Root, SolutionOutlineVersionRow as Version
from .outline_read_repository import SqlAlchemyOutlineReadRepository
from .reference_deidentification_repository import _session


class SqlAlchemyCurrentOutlineVersionBase:
    def current(self, transaction: object, *, project_id: uuid.UUID,
                outline_id: uuid.UUID) -> CurrentOutlineVersionBase | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(outline_id) is not uuid.UUID or outline_id.int == 0):
            return None
        session = _session(transaction)
        row = session.execute(select(Root, Version).outerjoin(Version, and_(
            Version.solution_outline_version_id == Root.current_approved_version_ref,
            Version.solution_outline_id == Root.solution_outline_id,
            Version.project_id == Root.project_id,
        )).where(
            Root.solution_outline_id == outline_id,
            Root.project_id == project_id,
        ).with_for_update(of=Root)).one_or_none()
        if row is None:
            return None
        root, approved = row
        SqlAlchemyOutlineReadRepository._require_approved_pointer(
            root, approved, project_id)
        if root.outline_state != "ACTIVE" or root.lock_version < 0:
            return None
        latest = session.execute(select(Version).where(
            Version.solution_outline_id == outline_id,
            Version.project_id == project_id,
        ).order_by(Version.version_no.desc()).limit(1).with_for_update(
            read=True, of=Version)).scalar_one_or_none()
        if latest is None:
            return CurrentOutlineVersionBase(project_id, outline_id, 1, None,
                                             root.lock_version)
        if (type(latest.version_no) is not int
                or not 1 <= latest.version_no < 2_147_483_647):
            return None
        return CurrentOutlineVersionBase(
            project_id, outline_id, latest.version_no + 1,
            latest.solution_outline_version_id, root.lock_version)
