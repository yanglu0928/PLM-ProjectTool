"""Pure SOL_SPEC_VALIDATE report contract; no live Owner is simulated here."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    AUDIT_ACTION,
    OPERATION,
    StructuredSpecValidationContractError,
    StructuredSpecValidationFacts,
    StructuredSpecValidationObservation,
    StructuredSpecValidationSnapshot,
    ValidateStructuredSpec,
    audit_reason_for_observation,
    build_structured_spec_type_checks,
    build_structured_spec_validation_report,
    observation_from_audit_reason,
)


PROJECT, SPEC, SERIES, ACTOR, TRACE, AUDIT = (uuid.uuid4() for _ in range(6))
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
CHECKS = {
    "PROCESS_MODEL": ("GRAPH_STRUCTURE", "ROLE_TRACEABILITY", "INPUT_OUTPUT_TRACEABILITY"),
    "INTERFACE_SPEC": ("BOUNDARY_MAPPING", "OWNERSHIP_RUNTIME", "AUTHENTICATION_CONTROL"),
    "MIGRATION_SPEC": ("SCOPE_MAPPING", "TRIAL_EXECUTION", "RECONCILIATION_PROOF",
                       "ROLLBACK_PROOF", "ACCEPTANCE_PROOF"),
    "PERMISSION_DESIGN": ("MATRIX_DEFAULT_DENY", "SCOPE_CONTROL", "DUTY_CONFLICT_REVIEW"),
}


def command(**changes):
    values = dict(session_token=b"s" * 32, csrf_token=b"c" * 32,
                  trace_id=TRACE, project_id=PROJECT,
                  structured_solution_spec_id=SPEC,
                  idempotency_key="spec-validate-0001")
    values.update(changes)
    return ValidateStructuredSpec(**values)


def snapshot(**changes):
    values = dict(project_id=PROJECT, structured_solution_spec_id=SPEC,
                  spec_series_id=SERIES, spec_type="MIGRATION_SPEC",
                  version_no=2, version_state="DRAFT",
                  content_fingerprint=b"c" * 32, payload_fingerprint=b"p" * 32,
                  requirement_count=1, section_count=1,
                  evidence_count=1, artifact_count=0)
    values.update(changes)
    return StructuredSpecValidationSnapshot(**values)


def proven_facts():
    return StructuredSpecValidationFacts(*(["PASS"] * 8))


def type_checks(spec_type="MIGRATION_SPEC", status="PASS"):
    return build_structured_spec_type_checks(
        spec_type, {code: status for code in CHECKS[spec_type]})


def observation(facts=None, checks=None):
    return StructuredSpecValidationObservation(
        facts or StructuredSpecValidationFacts(),
        checks or build_structured_spec_type_checks("MIGRATION_SPEC"))


def report(facts=None, checks=None, fixed=None):
    return build_structured_spec_validation_report(
        command(), fixed or snapshot(), observation(facts, checks),
        audit_event_id=AUDIT, observed_at=NOW)


def test_command_binds_fixed_path_but_hides_session_csrf_and_original_key():
    value = command()
    assert OPERATION == "V1_SOL_STRUCTURED_SPEC_VALIDATE"
    assert AUDIT_ACTION == "SOL_STRUCTURED_SPEC_VALIDATED"
    assert value.request_fingerprint() == command(
        trace_id=uuid.uuid4(), idempotency_key="another-valid-key").request_fingerprint()
    assert value.request_fingerprint() != command(
        structured_solution_spec_id=uuid.uuid4()).request_fingerprint()
    assert value.scope(ACTOR).operation == OPERATION
    assert value.scope(ACTOR).key_digest != command(
        idempotency_key="different-key-001").scope(ACTOR).key_digest
    assert "spec-validate-0001" not in repr(value)
    assert "b'sssss" not in repr(value) and "b'ccccc" not in repr(value)


@pytest.mark.parametrize("changes", [
    {"session_token": b"s"}, {"csrf_token": b"c"},
    {"trace_id": uuid.UUID(int=0)}, {"project_id": "wrong"},
    {"structured_solution_spec_id": uuid.UUID(int=0)},
    {"idempotency_key": "short"}, {"idempotency_key": "x" * 129},
])
def test_command_rejects_invalid_identity_and_key(changes):
    with pytest.raises(StructuredSpecValidationContractError):
        command(**changes)


@pytest.mark.parametrize("spec_type", CHECKS)
def test_each_type_requires_its_exact_ordered_check_set_and_audit_round_trips(spec_type):
    statuses = {code: ("PASS" if index == 0 else "UNAVAILABLE")
                for index, code in enumerate(CHECKS[spec_type])}
    value = StructuredSpecValidationObservation(
        replace(proven_facts(), trace="UNAVAILABLE"),
        build_structured_spec_type_checks(spec_type, statuses))
    reason = audit_reason_for_observation(value)
    assert len(reason) <= 64 and observation_from_audit_reason(reason) == value
    assert tuple(item.code for item in value.type_checks.checks) == CHECKS[spec_type]


def test_missing_proofs_never_become_valid_or_ready():
    value = report()
    assert not value.valid and not value.ready_for_review
    assert value.issue_codes[:8] == (
        "FIXED_VERSION_UNAVAILABLE", "PAYLOAD_STRUCTURE_UNAVAILABLE",
        "REQUIREMENT_SOURCE_UNAVAILABLE", "SECTION_SOURCE_UNAVAILABLE",
        "EVIDENCE_SOURCE_UNAVAILABLE", "ARTIFACT_SOURCE_UNAVAILABLE",
        "TRACE_COVERAGE_UNAVAILABLE", "CURRENT_VERSION_UNAVAILABLE")
    assert value.issue_codes[8:] == tuple(
        f"{code}_UNAVAILABLE" for code in CHECKS["MIGRATION_SPEC"])
    assert value.audit_event_id == AUDIT and value.trace_id == TRACE
    assert "b'cccc" not in repr(value) and "b'pppp" not in repr(value)


@pytest.mark.parametrize("dimension", [
    "integrity", "payload", "requirements", "sections", "evidence",
    "artifacts", "trace", "current_version",
])
@pytest.mark.parametrize("status", ["FAIL", "UNAVAILABLE"])
def test_each_unproven_common_fact_blocks_review_and_only_sources_block_valid(dimension, status):
    value = report(replace(proven_facts(), **{dimension: status}), type_checks())
    assert not value.ready_for_review
    assert value.valid == (dimension not in (
        "integrity", "payload", "requirements", "sections", "evidence"))
    assert any(item.endswith(status) for item in value.issue_codes)


def test_type_owner_gap_preserves_structural_valid_but_blocks_review():
    checks = type_checks()
    changed = replace(checks, checks=(
        checks.checks[0], replace(checks.checks[1], status="UNAVAILABLE"),
        *checks.checks[2:]))
    value = report(proven_facts(), changed)
    assert value.valid and not value.ready_for_review
    assert value.issue_codes == ("TRIAL_EXECUTION_UNAVAILABLE",)


def test_all_proven_latest_draft_is_ready_but_never_approved_by_report():
    value = report(proven_facts(), type_checks())
    assert value.valid and value.ready_for_review and value.issue_codes == ()
    assert value.version_state == "DRAFT" and value.version_no == 2


def test_non_draft_and_noncurrent_versions_remain_unready():
    non_draft = report(proven_facts(), type_checks(), snapshot(version_state="APPROVED"))
    assert non_draft.valid and not non_draft.ready_for_review
    assert non_draft.issue_codes == ("VERSION_NOT_DRAFT",)
    historical = report(replace(proven_facts(), current_version="FAIL"), type_checks())
    assert historical.valid and not historical.ready_for_review
    assert historical.issue_codes == ("CURRENT_VERSION_FAIL",)


def test_malformed_snapshot_checks_audit_and_forged_report_fail_closed():
    with pytest.raises(StructuredSpecValidationContractError):
        snapshot(payload_fingerprint=b"bad")
    with pytest.raises(StructuredSpecValidationContractError):
        build_structured_spec_type_checks("MIGRATION_SPEC", {
            "SCOPE_MAPPING": "PASS"})
    with pytest.raises(StructuredSpecValidationContractError):
        build_structured_spec_type_checks("UNKNOWN")
    with pytest.raises(StructuredSpecValidationContractError):
        observation_from_audit_reason("SPEC_VALIDATION_V1_MG_PPP")
    value = report(proven_facts(), type_checks())
    with pytest.raises(StructuredSpecValidationContractError):
        replace(value, ready_for_review=False)
    with pytest.raises(StructuredSpecValidationContractError):
        replace(value, issue_codes=("MADE_UP",))
    with pytest.raises(StructuredSpecValidationContractError):
        replace(value, observed_at=NOW.replace(tzinfo=None))
    with pytest.raises(StructuredSpecValidationContractError):
        report(proven_facts(), type_checks(), snapshot(project_id=uuid.uuid4()))
