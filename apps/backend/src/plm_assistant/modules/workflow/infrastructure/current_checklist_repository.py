"""Caller-owned transaction; lock current facts before reading immutable history."""
from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.current_checklist_record import (
    ChecklistBasisObservation, ChecklistRecordReadError, CurrentChecklistRecord,
)
from ..domain.catalog_v1 import six_stage_definition
from ..domain.checklist_record import ChecklistRecordSnapshot
from ..domain.fingerprint import definition_fingerprint
from ..domain.transition import ChecklistState
from .checklist_record_orm import ChecklistRecordRow, ChecklistRecordRefRow
from .orm import ProjectWorkflowRow, ChecklistItemRow


class SqlAlchemyCurrentChecklistRecordRepository:
    def get(self, transaction: object, project_id: UUID, workflow_id: UUID,
            item_key: str) -> CurrentChecklistRecord | None:
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Checklist caller transaction required")
        definition = six_stage_definition(1)
        owners = {item.item_key: stage.stage_key for stage in definition.stages
                  for item in stage.checklist_items}
        if (type(project_id) is not UUID or not project_id.int
                or type(workflow_id) is not UUID or not workflow_id.int
                or type(item_key) is not str or item_key not in owners):
            raise ValueError("validated Checklist scope required")
        # Core columns bypass stale ORM identity-map values. Lock order matches writers.
        w, i = ProjectWorkflowRow.__table__, ChecklistItemRow.__table__
        workflow = session.execute(select(w).where(
            w.c.project_id == project_id, w.c.workflow_id == workflow_id,
        ).with_for_update()).mappings().one_or_none()
        if workflow is None:
            return None
        if (workflow["workflow_version"] != 1
                or bytes(workflow["definition_fingerprint"]) != definition_fingerprint(definition)):
            raise ChecklistRecordReadError()
        item = session.execute(select(i).where(
            i.c.project_id == project_id, i.c.workflow_id == workflow_id,
            i.c.item_key == item_key,
        ).with_for_update()).mappings().one_or_none()
        if item is None:
            raise ChecklistRecordReadError()
        r, f = ChecklistRecordRow.__table__, ChecklistRecordRefRow.__table__
        roots = session.execute(select(r).where(
            r.c.project_id == project_id, r.c.workflow_id == workflow_id,
            r.c.item_key == item_key,
        ).order_by(r.c.after_item_version)).mappings().all()
        version = item["lock_version"]
        if version == 0 and item["item_state"] == "PENDING" and not roots:
            return None
        if not roots or len(roots) != version:
            raise ChecklistRecordReadError()
        previous = None
        for index, root in enumerate(roots):
            if (root["definition_version"] != 1 or root["stage_key"] != owners[item_key]
                    or root["before_item_version"] != index or root["after_item_version"] != index+1
                    or root["supersedes_record_id"] != (None if previous is None else previous["record_id"])
                    or root["before_state"] != ("PENDING" if previous is None else previous["result"])
                    or root["after_workflow_version"] != root["before_workflow_version"]+1
                    or root["before_workflow_version"] < 0
                    or previous is not None and root["before_workflow_version"] < previous["after_workflow_version"]):
                raise ChecklistRecordReadError()
            previous = root
        root = roots[-1]
        if root["result"] != item["item_state"] or root["after_workflow_version"] > workflow["lock_version"]:
            raise ChecklistRecordReadError()
        refs = session.execute(select(f).where(
            f.c.record_id == root["record_id"], f.c.workflow_id == workflow_id,
            f.c.project_id == project_id, f.c.item_key == item_key,
        ).order_by(f.c.ref_kind, f.c.ref_id)).mappings().all()
        basis = tuple(ChecklistBasisObservation(
            ref["ref_kind"], ref["ref_id"], ref["ref_scope"], ref["ref_project_id"],
            ref["observed_state"], ref["observed_lock_version"], bytes(ref["content_fingerprint"]),
            ref["verified_at"].astimezone(timezone.utc), ref["proof_schema_version"],
        ) for ref in refs)
        try:
            snapshot = ChecklistRecordSnapshot(
                record_id=root["record_id"], workflow_id=workflow_id, project_id=project_id,
                actor_id=root["actor_id"], trace_id=root["trace_id"], definition_version=1,
                stage_key=root["stage_key"], item_key=item_key,
                before_state=ChecklistState(root["before_state"]), result=ChecklistState(root["result"]),
                before_item_version=root["before_item_version"], after_item_version=root["after_item_version"],
                before_workflow_version=root["before_workflow_version"], after_workflow_version=root["after_workflow_version"],
                occurred_at=root["occurred_at"].astimezone(timezone.utc), supersedes_record_id=root["supersedes_record_id"],
                evidence_refs=tuple(ref.ref_id for ref in basis if ref.ref_kind == "EVIDENCE"),
                review_round_refs=tuple(ref.ref_id for ref in basis if ref.ref_kind == "REVIEW_ROUND"),
                exception_refs=tuple(ref.ref_id for ref in basis if ref.ref_kind == "APPROVED_EXCEPTION"),
                reason=root["reason"], impact=root["impact"],
            )
        except ValueError:
            raise ChecklistRecordReadError() from None
        return CurrentChecklistRecord(snapshot, basis, bytes(root["content_fingerprint"]),
                                      root["observed_stage_state"], workflow["lock_version"])
