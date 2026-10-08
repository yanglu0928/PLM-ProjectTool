"""NOT_REQUIRED witnesses must not become Workflow facts when stale/tampered."""

import uuid
from types import SimpleNamespace as Row

from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.prototype.application.workflow_scope_lock import (
    prove_not_required_decision,
)


def _rows():
    project, prototype, confirmer = (uuid.uuid4() for _ in range(3))
    requirement, version, decision_id = (uuid.uuid4() for _ in range(3))
    reason, impact = "Not required", "No prototype artifact"
    fingerprint = canonical_payload_fingerprint({
        "project_id": str(project), "prototype_id": str(prototype),
        "expected_version": 0, "decision_type": "NOT_REQUIRED",
        "reason": reason, "impact": impact,
        "affected_requirement_version_refs": [str(version)],
    })
    root = Row(project_id=project, prototype_id=prototype, name="Scope",
               prototype_state="NOT_REQUIRED", current_approved_version_ref=None,
               lock_version=1, updated_by=confirmer)
    decision = Row(project_id=project, prototype_id=prototype,
                   scope_decision_id=decision_id, decision_type="NOT_REQUIRED",
                   before_version=0, after_version=1, confirmed_by=confirmer,
                   reason=reason, impact=impact, review_id=None,
                   review_round_id=None, decision_fingerprint=fingerprint)
    ref = Row(project_id=project, prototype_id=prototype,
              scope_decision_id=decision_id, requirement_id=requirement,
              requirement_version_id=version, ordinal=1)
    result = Row(project_id=project, prototype_id=prototype,
                 scope_decision_id=decision_id, lock_version=1,
                 confirmed_by=confirmer, name="Scope", reason=reason,
                 impact=impact, review_id=None, review_round_id=None,
                 decision_fingerprint=fingerprint,
                 requirement_version_refs=[version])
    return root, decision, (ref,), result


def test_matching_decision_is_locked_input_not_workflow_pass():
    root, decision, refs, result = _rows()
    proof = prove_not_required_decision(root, decision, refs, result)
    assert proof is not None
    assert proof.requirement_version_refs == (refs[0].requirement_version_id,)
    assert proof.confirmed_by == root.updated_by


def test_tampered_or_stale_decision_fails_closed():
    for change in (
        lambda r, d, refs, v: setattr(r, "lock_version", 2),
        lambda r, d, refs, v: setattr(r, "updated_by", uuid.uuid4()),
        lambda r, d, refs, v: setattr(d, "reason", "Other"),
        lambda r, d, refs, v: setattr(v, "impact", "Other"),
        lambda r, d, refs, v: setattr(v, "requirement_version_refs", []),
        lambda r, d, refs, v: setattr(refs[0], "ordinal", 2),
        lambda r, d, refs, v: setattr(r, "current_approved_version_ref", uuid.uuid4()),
        lambda r, d, refs, v: setattr(v, "project_id", uuid.uuid4()),
        lambda r, d, refs, v: setattr(d, "review_id", uuid.uuid4()),
    ):
        root, decision, refs, result = _rows()
        change(root, decision, refs, result)
        assert prove_not_required_decision(root, decision, refs, result) is None


def test_missing_or_duplicate_witness_fails_closed():
    root, decision, refs, result = _rows()
    assert prove_not_required_decision(root, decision, (), result) is None
    assert prove_not_required_decision(root, decision, refs, None) is None
    assert prove_not_required_decision(root, decision, refs + refs, result) is None
