"""Stable IDs must come from the same rows as the shared-locked snapshot."""

import uuid
from types import SimpleNamespace

from plm_assistant.modules.requirement.infrastructure.version_validation_repository import (
    SqlAlchemyRequirementVersionValidationRepository,
)


def test_same_snapshot_rows_make_stable_refs(monkeypatch):
    project, requirement, version = (uuid.uuid4() for _ in range(3))
    ids = (uuid.uuid4(), uuid.uuid4())
    snapshot = SimpleNamespace(declared_acceptance_count=2)
    rows = tuple(SimpleNamespace(ordinal=index, acceptance_criterion_id=value)
                 for index, value in enumerate(ids))
    repository = SqlAlchemyRequirementVersionValidationRepository()
    monkeypatch.setattr(repository, "_lock_snapshot_and_rows",
                        lambda *_a, **_k: (snapshot, rows))
    result = repository.lock_snapshot_and_acceptance_refs(
        object(), project_id=project, requirement_id=requirement,
        requirement_version_id=version,
    )
    assert result is not None
    assert result[0] is snapshot
    assert result[1].criterion_refs == ids


def test_same_snapshot_rows_reject_missing_gap_duplicate_or_bad_id(monkeypatch):
    ids = (uuid.uuid4(), uuid.uuid4())
    cases = (
        (2, ((0, ids[0]),)),
        (2, ((0, ids[0]), (2, ids[1]))),
        (2, ((0, ids[0]), (1, ids[0]))),
        (2, ((0, ids[0]), (1, uuid.UUID(int=0)))),
        (0, ()),
    )
    repository = SqlAlchemyRequirementVersionValidationRepository()
    for count, items in cases:
        snapshot = SimpleNamespace(declared_acceptance_count=count)
        rows = tuple(SimpleNamespace(ordinal=ordinal,
                                     acceptance_criterion_id=value)
                     for ordinal, value in items)
        monkeypatch.setattr(repository, "_lock_snapshot_and_rows",
                            lambda *_a, **_k: (snapshot, rows))
        assert repository.lock_snapshot_and_acceptance_refs(
            object(), project_id=uuid.uuid4(), requirement_id=uuid.uuid4(),
            requirement_version_id=uuid.uuid4(),
        ) is None
