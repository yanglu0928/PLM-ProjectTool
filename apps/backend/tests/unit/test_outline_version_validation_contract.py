"""Pure Outline validation contract; current-fact Owner is separate."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    AUDIT_ACTION,
    OPERATION,
    OutlineVersionValidationContractError,
    OutlineVersionValidationFacts,
    OutlineVersionValidationSnapshot,
    ValidateOutlineVersion,
    audit_reason_for_facts,
    build_outline_version_validation_report,
    facts_from_audit_reason,
)


PROJECT, OUTLINE, VERSION, ACTOR, TRACE, AUDIT = (uuid.uuid4() for _ in range(6))
NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def command(**changes):
    values = dict(session_token=b"s" * 32, csrf_token=b"c" * 32,
                  trace_id=TRACE, project_id=PROJECT,
                  solution_outline_id=OUTLINE,
                  solution_outline_version_id=VERSION,
                  idempotency_key="outline-validate-0001")
    values.update(changes)
    return ValidateOutlineVersion(**values)


def snapshot(**changes):
    values = dict(project_id=PROJECT, solution_outline_id=OUTLINE,
                  solution_outline_version_id=VERSION, version_no=2,
                  version_state="DRAFT", content_fingerprint=b"f" * 32,
                  section_count=2, requirement_count=1, reference_count=0)
    values.update(changes)
    return OutlineVersionValidationSnapshot(**values)


def report(facts=None, fixed=None):
    return build_outline_version_validation_report(
        command(), fixed or snapshot(), facts or OutlineVersionValidationFacts(),
        audit_event_id=AUDIT, observed_at=NOW)


def proven():
    return OutlineVersionValidationFacts(order="PASS", source="PASS", coverage="PASS")


def test_command_binds_original_key_actor_and_fixed_identity_only():
    first = command()
    assert OPERATION == "V1_SOL_OUTLINE_VERSION_VALIDATE"
    assert AUDIT_ACTION == "SOL_OUTLINE_VERSION_VALIDATED"
    assert first.request_fingerprint() == command(
        trace_id=uuid.uuid4(), idempotency_key="another-original-key").request_fingerprint()
    assert first.request_fingerprint() != command(
        solution_outline_version_id=uuid.uuid4()).request_fingerprint()
    assert first.scope(ACTOR).operation == OPERATION
    assert first.scope(ACTOR).key_digest != command(
        idempotency_key="different-key-0001").scope(ACTOR).key_digest
    assert "outline-validate-0001" not in repr(first)
    assert "b'sssss" not in repr(first)


@pytest.mark.parametrize("changes", [
    {"session_token": b"s"}, {"csrf_token": b"c"},
    {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
    {"solution_outline_id": "wrong"},
    {"solution_outline_version_id": uuid.UUID(int=0)},
    {"idempotency_key": "short"}, {"idempotency_key": "x" * 129},
])
def test_command_rejects_invalid_identity_and_key(changes):
    with pytest.raises(OutlineVersionValidationContractError):
        command(**changes)


def test_missing_facts_do_not_become_a_pass():
    value = report()
    assert not value.valid and not value.ready_for_review
    assert value.issue_codes == (
        "SECTION_ORDER_UNAVAILABLE", "FIXED_SOURCE_UNAVAILABLE",
        "REQUIREMENT_COVERAGE_UNAVAILABLE")
    assert value.audit_event_id == AUDIT and value.trace_id == TRACE
    assert value.content_fingerprint == b"f" * 32
    assert "b'ffffffff" not in repr(value)


@pytest.mark.parametrize("dimension", ["order", "source", "coverage"])
@pytest.mark.parametrize("status", ["FAIL", "UNAVAILABLE"])
def test_any_unproven_dimension_blocks_review(dimension, status):
    value = report(replace(proven(), **{dimension: status}))
    assert not value.valid and not value.ready_for_review
    assert len(value.issue_codes) == 1 and value.issue_codes[0].endswith(status)


def test_all_proven_draft_is_review_ready_but_not_approved():
    value = report(proven())
    assert value.valid and value.ready_for_review and value.issue_codes == ()
    assert value.version_state == "DRAFT" and value.version_no == 2


def test_audit_reason_round_trips_without_guessing_pass():
    facts = replace(proven(), source="FAIL", coverage="UNAVAILABLE")
    reason = audit_reason_for_facts(facts)
    assert reason == "OUTLINE_VALIDATION_V1_PFU"
    assert facts_from_audit_reason(reason) == facts
    assert facts_from_audit_reason(audit_reason_for_facts(
        OutlineVersionValidationFacts())) == OutlineVersionValidationFacts()
    for corrupt in ("OUTLINE_VALIDATION_V1_PP", "OUTLINE_VALIDATION_V1_PPPX",
                    "OUTLINE_VALIDATION_V1_ppp", "SECTION_VALIDATION_V1_PPP", None):
        with pytest.raises(OutlineVersionValidationContractError):
            facts_from_audit_reason(corrupt)


def test_non_draft_remains_unready_even_if_all_proofs_pass():
    value = report(proven(), snapshot(version_state="IN_REVIEW"))
    assert value.valid and not value.ready_for_review
    assert value.issue_codes == ("VERSION_NOT_DRAFT",)


@pytest.mark.parametrize("changes", [
    {"content_fingerprint": b"bad"}, {"section_count": 0},
    {"section_count": 101}, {"requirement_count": 501},
    {"reference_count": -1}, {"version_no": True},
    {"version_state": "UNKNOWN"},
])
def test_invalid_fixed_snapshot_fails_closed(changes):
    with pytest.raises(OutlineVersionValidationContractError):
        snapshot(**changes)


def test_foreign_snapshot_or_invalid_facts_fail_closed():
    with pytest.raises(OutlineVersionValidationContractError):
        report(proven(), snapshot(project_id=uuid.uuid4()))
    with pytest.raises(OutlineVersionValidationContractError):
        OutlineVersionValidationFacts(coverage="SKIPPED")


def test_report_cannot_be_forged_into_ready_conclusion():
    value = report()
    with pytest.raises(OutlineVersionValidationContractError):
        replace(value, ready_for_review=True)
    with pytest.raises(OutlineVersionValidationContractError):
        replace(value, valid=True)
    with pytest.raises(OutlineVersionValidationContractError):
        replace(value, issue_codes=())
    with pytest.raises(OutlineVersionValidationContractError):
        replace(value, observed_at=NOW.replace(tzinfo=None))
