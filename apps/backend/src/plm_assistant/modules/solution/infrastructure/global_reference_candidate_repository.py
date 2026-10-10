"""Bounded raw-root scan for published GLOBAL candidate labels only."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.solution.application.list_global_reference_candidates import (
    GlobalReferenceCandidate, GlobalReferenceCandidatePage,
)

from .orm import (
    GlobalReferencePublicationEventRow as Publication,
    ReferenceSolutionRow as Root,
    ReferenceSolutionVersionRow as Version,
)
from .reference_deidentification_repository import _session


class SqlAlchemyGlobalReferenceCandidateRepository:
    def scan(self, transaction: object, *,
             after_reference_solution_id: uuid.UUID | None,
             limit: int) -> GlobalReferenceCandidatePage:
        if ((after_reference_solution_id is not None and (
                type(after_reference_solution_id) is not uuid.UUID
                or after_reference_solution_id.int == 0))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError("invalid GLOBAL candidate scan")
        session = _session(transaction)
        statement = select(Root).where(
            Root.scope == "GLOBAL", Root.project_id.is_(None))
        if after_reference_solution_id is not None:
            statement = statement.where(
                Root.reference_solution_id > after_reference_solution_id)
        rows = tuple(session.execute(statement.order_by(
            Root.reference_solution_id).limit(limit + 1).with_for_update(
                read=True, of=Root)).scalars())
        scanned = rows[:limit]
        items: list[GlobalReferenceCandidate] = []
        for root in scanned:
            if root.current_version_ref is None or root.eligibility_state != "ELIGIBLE":
                continue
            publication = session.execute(select(Publication).where(
                Publication.reference_solution_id == root.reference_solution_id,
            ).order_by(Publication.event_no.desc()).limit(1).with_for_update(
                read=True, of=Publication)).scalar_one_or_none()
            if (publication is None or publication.event_kind != "PUBLISH"
                    or publication.scope != "GLOBAL"
                    or publication.reference_version_id != root.current_version_ref):
                continue
            version = session.execute(select(Version).where(
                Version.reference_version_id == root.current_version_ref,
                Version.reference_solution_id == root.reference_solution_id,
                Version.scope == "GLOBAL", Version.project_id.is_(None),
            ).with_for_update(read=True, of=Version)).scalar_one_or_none()
            if (version is None or version.version_state != "DRAFT"
                    or version.deidentification_confirmation_id is None
                    or type(publication.display_label) is not str
                    or not 1 <= len(publication.display_label) <= 160):
                raise RuntimeError("GLOBAL candidate publication is inconsistent")
            items.append(GlobalReferenceCandidate(
                root.reference_solution_id, version.reference_version_id,
                publication.display_label, version.version_no,
                root.eligibility_state))
        has_more = len(rows) > limit
        return GlobalReferenceCandidatePage(
            tuple(items), scanned[-1].reference_solution_id if has_more else None,
            has_more)
