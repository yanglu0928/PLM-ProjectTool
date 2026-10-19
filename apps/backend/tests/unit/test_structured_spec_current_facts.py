"""Current facts remain independent and fail closed for SOL_SPEC_VALIDATE."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.solution.application.evaluate_structured_spec_validation import (
    StructuredSpecCurrentFactEvaluator, StructuredSpecCurrentFactsError,
)
from plm_assistant.modules.solution.application.prove_section_document_content import (
    SectionDocumentContentProof,
)
from plm_assistant.modules.solution.application.prove_section_evidence_use import (
    SectionEvidenceUseProof,
)
from plm_assistant.modules.solution.application.read_section import SectionCurrentView
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    StructuredSpecValidationSnapshot, ValidateStructuredSpec,
)
from plm_assistant.modules.solution.application.structured_spec_validation_source import (
    StructuredSpecValidationSource,
)


PROJECT, SPEC, SERIES, ACTOR, TRACE = (uuid.uuid4() for _ in range(5))
REQ = SpecRequirementRef(uuid.uuid4(), uuid.uuid4())
SECTION = SpecSectionRef(uuid.uuid4(), uuid.uuid4())
EVIDENCE = uuid.uuid4()
DOCUMENT_VERSION = uuid.uuid4()
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def _base():
    return {"assumptions": [], "exclusions": []}


PAYLOADS = {
    "PROCESS_MODEL": {
        **_base(),
        "nodes": [
            {"id": "s", "kind": "START", "role": "user",
             "inputs": [], "outputs": ["request"]},
            {"id": "e", "kind": "END", "role": "user",
             "inputs": ["request"], "outputs": []},
        ],
        "edges": [{"from": "s", "to": "e"}],
    },
    "INTERFACE_SPEC": {
        **_base(), "source_system": "PLM", "target_system": "ERP",
        "direction": "OUTBOUND", "data_owner": "owner",
        "frequency": "event", "error_handling": "alert",
        "retry_policy": "three attempts", "authentication": "mTLS",
        "field_mappings": [{"source": "part", "target": "item"}],
    },
    "MIGRATION_SPEC": {
        **_base(), "source_system": "old", "target_system": "new",
        "scope": "parts", "cleansing_rules": ["deduplicate"],
        "field_mappings": [{"source": "old_id", "target": "part_id"}],
        "trial_plan": "trial", "reconciliation_plan": "compare",
        "rollback_plan": "restore", "acceptance_criteria": "zero difference",
    },
    "PERMISSION_DESIGN": {
        **_base(), "roles": ["maker", "checker"], "resources": ["change"],
        "grants": [
            {"role": "maker", "resource": "change", "action": "CREATE",
             "scope": "OWN"}],
        "default_deny": True, "separation_policy": "maker checker split",
        "separation_of_duties": [
            {"left_role": "maker", "right_role": "checker"}],
    },
}
STRUCTURAL = {
    "PROCESS_MODEL": "GRAPH_STRUCTURE",
    "INTERFACE_SPEC": "BOUNDARY_MAPPING",
    "MIGRATION_SPEC": "SCOPE_MAPPING",
    "PERMISSION_DESIGN": "MATRIX_DEFAULT_DENY",
}


def _command(spec_id=SPEC):
    return ValidateStructuredSpec(
        b"s" * 32, b"c" * 32, TRACE, PROJECT, spec_id,
        "structured-spec-facts-0001")


def _source(spec_type="MIGRATION_SPEC", *, current=True, artifacts=(),
            content_fingerprint=b"c" * 32):
    draft = validate_structured_spec_draft(StructuredSpecDraftInput(
        PROJECT, None, None, spec_type, PAYLOADS[spec_type],
        (REQ,), (SECTION,), (EVIDENCE,), artifacts))
    snapshot = StructuredSpecValidationSnapshot(
        PROJECT, SPEC, SERIES, spec_type, 1, "DRAFT", content_fingerprint,
        draft.payload_fingerprint, 1, 1, 1, len(artifacts))
    return StructuredSpecValidationSource(
        snapshot, draft, SPEC if current else uuid.uuid4(),
        1 if current else 2)


@pytest.fixture
def facts():
    requirement = OutlineApprovedRequirementProof(
        PROJECT, REQ.requirement_id, REQ.requirement_version_id,
        2, b"r" * 32, uuid.uuid4(), uuid.uuid4())
    root = SectionCurrentView(
        SECTION.solution_section_id, uuid.uuid4(), PROJECT,
        "migration", "ACTIVE", None, uuid.uuid4(), NOW, '"v0"')
    version = SectionVersionHistoryView(
        SECTION.solution_section_version_id, SECTION.solution_section_id,
        PROJECT, 1, "DRAFT", "migration", DOCUMENT_VERSION, None,
        b"v" * 32,
        (SectionRequirementRef(REQ.requirement_id,
                               REQ.requirement_version_id),),
        (EVIDENCE,), (), (), None, None, None, ACTOR, NOW)
    evidence = SectionEvidenceUseProof(
        EVIDENCE, PROJECT, uuid.uuid4(), uuid.uuid4(), 1, b"e" * 32)
    document = SectionDocumentContentProof(
        PROJECT, uuid.uuid4(), DOCUMENT_VERSION, b"d" * 32)
    ports = tuple(Mock() for _ in range(5))
    requirements, sections, versions, evidence_port, documents = ports
    requirements.prove.return_value = requirement
    sections.get_current.return_value = root
    versions.get.return_value = version
    versions.list.return_value = (version,)
    evidence_port.prove.return_value = evidence
    documents.prove.return_value = document
    evaluator = StructuredSpecCurrentFactEvaluator(
        requirements=requirements, sections=sections, versions=versions,
        evidence=evidence_port, documents=documents)
    return evaluator, ports, (requirement, version, document, evidence)


def _with_current_fingerprint(source, proofs):
    requirement, version, document, evidence = proofs
    fingerprint = canonical_payload_fingerprint({
        "kind": "STRUCTURED_SPEC_PROVEN_SOURCES_V1",
        "request_fingerprint": source.draft.request_fingerprint.hex(),
        "project_id": str(PROJECT),
        "requirements": [[
            str(REQ.requirement_id), str(REQ.requirement_version_id),
            requirement.version_no, requirement.content_fingerprint.hex(),
            str(requirement.review_id), str(requirement.review_round_id)]],
        "sections": [[
            str(SECTION.solution_section_id),
            str(SECTION.solution_section_version_id), version.version_no,
            version.version_state, version.content_fingerprint.hex(),
            str(document.document_id), str(document.document_version_id),
            document.content_sha256.hex(), None, None]],
        "evidence": [[
            str(EVIDENCE), str(evidence.document_id),
            str(evidence.document_version_id), evidence.observed_lock_version,
            evidence.content_fingerprint.hex()]],
    })
    return replace(source, snapshot=replace(
        source.snapshot, content_fingerprint=fingerprint))


def test_proven_common_sources_stay_valid_but_missing_trace_blocks_ready(facts):
    evaluator, _ports, proofs = facts
    source = _with_current_fingerprint(_source(), proofs)
    observed = evaluator.evaluate(object(), command=_command(), source=source)
    assert (observed.facts.integrity, observed.facts.payload,
            observed.facts.requirements, observed.facts.sections,
            observed.facts.evidence) == ("PASS",) * 5
    assert observed.facts.artifacts == "PASS"
    assert observed.facts.trace == "UNAVAILABLE"
    assert observed.facts.current_version == "PASS"
    assert observed.type_checks.checks[0].status == "PASS"
    assert all(item.status == "UNAVAILABLE"
               for item in observed.type_checks.checks[1:])


def test_changed_source_digest_fails_integrity_without_hiding_owner_facts(facts):
    evaluator, _ports, _proofs = facts
    observed = evaluator.evaluate(
        object(), command=_command(), source=_source())
    assert observed.facts.integrity == "FAIL"
    assert (observed.facts.requirements, observed.facts.sections,
            observed.facts.evidence) == ("PASS", "PASS", "PASS")


def test_owner_failures_are_independent_and_do_not_invent_fail(facts):
    evaluator, ports, _proofs = facts
    requirements, sections, versions, evidence, documents = ports
    requirements.prove.side_effect = RuntimeError("opaque")
    evidence.prove.return_value = replace(
        evidence.prove.return_value, project_id=uuid.uuid4())
    observed = evaluator.evaluate(object(), command=_command(), source=_source())
    assert observed.facts.requirements == "UNAVAILABLE"
    assert observed.facts.evidence == "UNAVAILABLE"
    assert observed.facts.sections == "PASS"
    sections.get_current.assert_called_once()
    versions.get.assert_called_once()
    documents.prove.assert_called_once()


def test_stale_section_historical_spec_and_nonempty_artifact_are_explicit(facts):
    evaluator, ports, proofs = facts
    version = proofs[1]
    ports[2].list.return_value = (
        replace(version, solution_section_version_id=uuid.uuid4()),)
    artifact = uuid.uuid4()
    observed = evaluator.evaluate(
        object(), command=_command(),
        source=_source(current=False, artifacts=(artifact,)))
    assert observed.facts.sections == "UNAVAILABLE"
    assert observed.facts.current_version == "FAIL"
    assert observed.facts.artifacts == "UNAVAILABLE"
    assert observed.facts.trace == "UNAVAILABLE"


@pytest.mark.parametrize("spec_type", tuple(PAYLOADS))
def test_each_type_only_claims_strict_payload_structure(spec_type, facts):
    evaluator, _ports, _proofs = facts
    checks = evaluator.evaluate(
        object(), command=_command(), source=_source(spec_type)).type_checks
    values = {item.code: item.status for item in checks.checks}
    assert values[STRUCTURAL[spec_type]] == "PASS"
    assert all(status == "UNAVAILABLE" for code, status in values.items()
               if code != STRUCTURAL[spec_type])


def test_identity_and_missing_context_fail_before_owner_calls(facts):
    evaluator, ports, _proofs = facts
    for transaction, command in (
            (None, _command()),
            (object(), _command(uuid.uuid4()))):
        with pytest.raises(StructuredSpecCurrentFactsError) as failure:
            evaluator.evaluate(transaction, command=command, source=_source())
        assert failure.value.code == "VALIDATION_FAILED"
    assert all(not port.mock_calls for port in ports)


def test_all_ports_are_required():
    with pytest.raises(ValueError):
        StructuredSpecCurrentFactEvaluator(
            requirements=None, sections=Mock(), versions=Mock(),
            evidence=Mock(), documents=Mock())
