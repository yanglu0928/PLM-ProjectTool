"""Deterministic digest for an immutable Stage Transition and Gate snapshot."""

from __future__ import annotations

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, canonical_payload_fingerprint,
)

from .append_stage_transition import (
    PersistedStageTransition, StageTransitionAppendError,
)


def stage_transition_fingerprint(value: PersistedStageTransition) -> bytes:
    try:
        if type(value) is not PersistedStageTransition:
            raise StageTransitionAppendError()
        value.__post_init__()
        snapshot = value.snapshot
        return canonical_payload_fingerprint({
            "stage_transition_id": str(value.stage_transition_id),
            "workflow_id": str(snapshot.workflow_id),
            "project_id": str(snapshot.project_id),
            "actor_id": str(snapshot.actor_id),
            "trace_id": str(snapshot.trace_id),
            "definition_version": snapshot.definition_version,
            "from_stage": snapshot.from_stage,
            "to_stage": snapshot.to_stage,
            "before_lock_version": snapshot.before_lock_version,
            "after_lock_version": snapshot.after_lock_version,
            "reason": snapshot.reason,
            "occurred_at": snapshot.occurred_at.isoformat(),
            "gates": [{
                "gate_item_id": str(gate.gate_item_id),
                "checklist_record_id": str(gate.checklist_record_id),
                "observed_item_version": gate.observed_item_version,
                "record_fingerprint": gate.record_fingerprint.hex(),
                "item_key": gate.snapshot.item_key,
                "result": gate.snapshot.result.value,
                "waiver_actor_id": (
                    None if gate.snapshot.waiver_actor_id is None
                    else str(gate.snapshot.waiver_actor_id)
                ),
                "waiver_reason": gate.snapshot.waiver_reason,
                "waiver_impact": gate.snapshot.waiver_impact,
                "basis": [{
                    "ref_kind": ref.ref_kind,
                    "ref_id": str(ref.ref_id),
                    "ref_scope": ref.ref_scope,
                    "ref_project_id": (
                        None if ref.ref_project_id is None
                        else str(ref.ref_project_id)
                    ),
                    "observed_state": ref.observed_state,
                    "observed_lock_version": ref.observed_lock_version,
                    "content_fingerprint": ref.content_fingerprint.hex(),
                    "verified_at": ref.verified_at.isoformat(),
                    "proof_schema_version": ref.proof_schema_version,
                } for ref in gate.basis],
            } for gate in value.gates],
        })
    except (AttributeError, IdempotencyError, StageTransitionAppendError):
        raise ValueError("invalid Stage Transition fingerprint input") from None
