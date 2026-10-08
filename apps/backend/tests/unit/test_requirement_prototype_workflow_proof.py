"""Stable Requirement acceptance refs cannot drift or skip ordinals."""

import uuid
from types import SimpleNamespace as Row

import pytest

from plm_assistant.modules.requirement.application.prototype_workflow_proof import (
    RequirementAcceptanceRefsProof,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.requirement.infrastructure.prototype_workflow_proof import (
    SqlAlchemyRequirementAcceptanceRefsProof,
)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self.value


class _Session:
    def __init__(self, count, rows):
        self.values = iter((count, rows))

    def execute(self, _query):
        return _Result(next(self.values))


def _prove(monkeypatch, count, rows):
    session = _Session(count, rows)
    monkeypatch.setattr(SqlAlchemyPrototypeApprovedRequirementVersionProof,
                        "_session", lambda _tx: session)
    ids = tuple(uuid.uuid4() for _ in range(3))
    return SqlAlchemyRequirementAcceptanceRefsProof().prove_current_acceptance_refs(
        object(), project_id=ids[0], requirement_id=ids[1],
        requirement_version_id=ids[2],
    )


def test_current_acceptance_refs_require_complete_order(monkeypatch):
    refs = (uuid.uuid4(), uuid.uuid4())
    proof = _prove(monkeypatch, 2, tuple(Row(ordinal=i,
                                           acceptance_criterion_id=value)
                                       for i, value in enumerate(refs)))
    assert type(proof) is RequirementAcceptanceRefsProof
    assert proof.criterion_refs == refs


@pytest.mark.parametrize("count,ordinals", [
    (None, (0,)), (0, ()), (2, (0,)), (2, (0, 2)),
])
def test_missing_or_noncontiguous_acceptance_fails(monkeypatch, count, ordinals):
    rows = tuple(Row(ordinal=ordinal, acceptance_criterion_id=uuid.uuid4())
                 for ordinal in ordinals)
    assert _prove(monkeypatch, count, rows) is None


def test_duplicate_acceptance_identity_fails(monkeypatch):
    identity = uuid.uuid4()
    rows = (Row(ordinal=0, acceptance_criterion_id=identity),
            Row(ordinal=1, acceptance_criterion_id=identity))
    assert _prove(monkeypatch, 2, rows) is None
