"""Deterministic digest for immutable Checklist record content and observations."""

from __future__ import annotations

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, canonical_payload_fingerprint,
)
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordSnapshot,
)

from .current_checklist_record import ChecklistBasisObservation


def checklist_record_fingerprint(
    record: ChecklistRecordSnapshot,
    basis: tuple[ChecklistBasisObservation, ...],
    observed_stage_state: str,
) -> bytes:
    record.__post_init__()
    if (type(basis) is not tuple
            or any(type(value) is not ChecklistBasisObservation for value in basis)
            or observed_stage_state not in {"ACTIVE", "BLOCKED"}):
        raise ValueError("invalid Checklist record fingerprint input")
    for value in basis:
        value.__post_init__()
    try:
        return canonical_payload_fingerprint({
            "record_id": str(record.record_id),
        "workflow_id": str(record.workflow_id),
        "project_id": str(record.project_id),
        "actor_id": str(record.actor_id),
        "trace_id": str(record.trace_id),
        "definition_version": record.definition_version,
        "stage_key": record.stage_key,
        "observed_stage_state": observed_stage_state,
        "item_key": record.item_key,
        "before_state": record.before_state.value,
        "result": record.result.value,
        "before_item_version": record.before_item_version,
        "after_item_version": record.after_item_version,
        "before_workflow_version": record.before_workflow_version,
        "after_workflow_version": record.after_workflow_version,
        "supersedes_record_id": (
            None if record.supersedes_record_id is None
            else str(record.supersedes_record_id)
        ),
        "occurred_at": record.occurred_at.isoformat(),
        "reason": record.reason,
        "impact": record.impact,
        "basis": [{
            "ref_kind": value.ref_kind,
            "ref_id": str(value.ref_id),
            "ref_scope": value.ref_scope,
            "ref_project_id": (
                None if value.ref_project_id is None
                else str(value.ref_project_id)
            ),
            "observed_state": value.observed_state,
            "observed_lock_version": value.observed_lock_version,
            "content_fingerprint": value.content_fingerprint.hex(),
            "verified_at": value.verified_at.isoformat(),
            "proof_schema_version": value.proof_schema_version,
            } for value in basis],
        })
    except IdempotencyError:
        raise ValueError("invalid Checklist record fingerprint input") from None
