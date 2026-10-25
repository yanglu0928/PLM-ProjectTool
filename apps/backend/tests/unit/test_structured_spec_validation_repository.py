"""Locked fixed-source reconstruction for SOL_SPEC_VALIDATE."""

import hashlib
import json
import uuid
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plm_assistant.modules.solution.application.structured_spec_validation_source import (
    StructuredSpecValidationSourceError,
)
from plm_assistant.modules.solution.infrastructure import (
    structured_spec_validation_repository as module,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)


PROJECT, OTHER_PROJECT, SERIES, V1, V2, ACTOR = (
    uuid.uuid4() for _ in range(6))
PAYLOAD = {
    "assumptions": ["synthetic"], "exclusions": [],
    "source_system": "old", "target_system": "new", "scope": "parts",
    "cleansing_rules": ["deduplicate"],
    "field_mappings": [{"source": "old_id", "target": "part_id"}],
    "trial_plan": "trial", "reconciliation_plan": "compare",
    "rollback_plan": "restore", "acceptance_criteria": "zero difference",
}


class _Result:
    def __init__(self, *, one=None, scalar=None, values=()):
        self._one, self._scalar, self._values = one, scalar, tuple(values)

    def one_or_none(self):
        return self._one

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return iter(self._values)


def _root(identity, version, previous, state="DRAFT"):
    return SimpleNamespace(
        structured_solution_spec_id=identity, spec_series_id=SERIES,
        project_id=PROJECT, spec_type="MIGRATION_SPEC", version_no=version,
        version_state=state, content_fingerprint=b"c" * 32,
        supersedes_version_ref=previous, review_ref=None, review_round_ref=None,
        created_by=ACTOR)


def _row(**values):
    return SimpleNamespace(
        structured_solution_spec_id=values.pop("spec_id", V1),
        spec_series_id=values.pop("series_id", SERIES),
        project_id=values.pop("project_id", PROJECT), **values)


def _session(*, requested=None, latest=None, payload=None,
             requirements=None, sections=None, evidence=(), artifacts=()):
    requested = requested or _root(V1, 1, None)
    latest = latest or requested
    payload = payload or _row(
        schema_version=1, spec_type="MIGRATION_SPEC", payload_json=PAYLOAD,
        payload_fingerprint=hashlib.sha256(
            json.dumps(PAYLOAD, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode()).digest())
    requirements = requirements or (_row(
        ordinal=1, requirement_id=uuid.uuid4(),
        requirement_version_id=uuid.uuid4()),)
    sections = sections or (_row(
        ordinal=1, solution_section_id=uuid.uuid4(),
        solution_section_version_id=uuid.uuid4()),)
    database = Mock()
    database.execute.side_effect = (
        _Result(one=SimpleNamespace(spec_series_id=SERIES)),
        _Result(), _Result(one=(requested, payload)), _Result(scalar=latest),
        _Result(values=requirements), _Result(values=sections),
        _Result(values=evidence), _Result(values=artifacts),
    )
    return database


def _read(monkeypatch, database):
    monkeypatch.setattr(module, "_session", lambda _transaction: database)
    return SqlAlchemyStructuredSpecValidationRepository().lock_source(
        object(), project_id=PROJECT, spec_id=V1)


def test_reconstructs_initial_current_version_and_uses_shared_series_lock(monkeypatch):
    database = _session()
    source = _read(monkeypatch, database)
    assert source is not None and source.is_current_version
    assert source.snapshot.structured_solution_spec_id == V1
    assert source.snapshot.spec_series_id == SERIES
    assert source.snapshot.requirement_count == source.snapshot.section_count == 1
    assert source.snapshot.evidence_count == source.snapshot.artifact_count == 0
    assert source.draft.spec_series_id is None
    assert source.draft.supersedes_version_ref is None
    lock = str(database.execute.call_args_list[1].args[0])
    assert "pg_advisory_xact_lock_shared" in lock
    assert database.execute.call_args_list[1].args[1] == {"series_id": SERIES}


def test_reconstructs_historical_revision_and_all_fixed_refs(monkeypatch):
    requested = _root(V1, 2, uuid.uuid4(), "APPROVED")
    latest = _root(V2, 3, V1)
    evidence_id, artifact_id = uuid.uuid4(), uuid.uuid4()
    source = _read(monkeypatch, _session(
        requested=requested, latest=latest,
        evidence=(_row(ordinal=1, evidence_id=evidence_id),),
        artifacts=(_row(ordinal=1, output_artifact_id=artifact_id),)))
    assert source is not None and not source.is_current_version
    assert source.latest_version_ref == V2 and source.latest_version_no == 3
    assert source.draft.spec_series_id == SERIES
    assert source.draft.supersedes_version_ref == requested.supersedes_version_ref
    assert source.draft.evidence_ids == (evidence_id,)
    assert source.draft.artifact_ids == (artifact_id,)
    assert source.snapshot.evidence_count == source.snapshot.artifact_count == 1


@pytest.mark.parametrize("field,value", [
    ("project_id", uuid.UUID(int=0)), ("spec_id", uuid.UUID(int=0)),
])
def test_invalid_identity_returns_absent_without_database(field, value):
    arguments = {"project_id": PROJECT, "spec_id": V1, field: value}
    assert SqlAlchemyStructuredSpecValidationRepository().lock_source(
        object(), **arguments) is None


def test_absent_same_project_identity_is_hidden(monkeypatch):
    database = Mock()
    database.execute.return_value = _Result(one=None)
    monkeypatch.setattr(module, "_session", lambda _transaction: database)
    assert SqlAlchemyStructuredSpecValidationRepository().lock_source(
        object(), project_id=OTHER_PROJECT, spec_id=V1) is None
    assert database.execute.call_count == 1


def test_payload_reference_and_latest_corruption_fail_closed(monkeypatch):
    broken_payload = _row(
        schema_version=1, spec_type="MIGRATION_SPEC", payload_json=PAYLOAD,
        payload_fingerprint=b"x" * 32)
    cases = (
        _session(payload=broken_payload),
        _session(requirements=(_row(
            ordinal=2, requirement_id=uuid.uuid4(),
            requirement_version_id=uuid.uuid4()),)),
        _session(latest=_root(V2, 1, None)),
        _session(latest=replace_namespace(_root(V2, 2, V1),
                                          spec_type="INTERFACE_SPEC")),
    )
    for database in cases:
        with pytest.raises(RuntimeError):
            _read(monkeypatch, database)


def replace_namespace(value, **changes):
    fields = vars(value).copy()
    fields.update(changes)
    return SimpleNamespace(**fields)


def test_source_value_rejects_forged_current_identity(monkeypatch):
    source = _read(monkeypatch, _session())
    with pytest.raises(StructuredSpecValidationSourceError):
        replace(source, latest_version_ref=V2, latest_version_no=1)
    with pytest.raises(StructuredSpecValidationSourceError):
        replace(source, latest_version_no=0)
