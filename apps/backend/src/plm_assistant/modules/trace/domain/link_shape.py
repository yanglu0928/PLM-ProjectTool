"""Frozen TraceLink version-reference and edge-shape validation only.

This module never proves target existence, approval, authorization, or acyclicity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


_TYPES: dict[str, frozenset[str]] = {
    "document": frozenset({"DOC-02"}),
    "capability": frozenset({"CAP-02"}),
    "handover": frozenset({"HND-02"}),
    "survey": frozenset({"SRV-02", "SRV-05"}),
    "requirement": frozenset({"REQ-03"}),
    "prototype": frozenset({"PRT-03", "PRT-04"}),
    "solution": frozenset({"SOL-01", "SOL-03", "SOL-05", "SOL-06"}),
    "plan": frozenset({"PLN-02", "PLN-03"}),
    "output": frozenset({"OUT-02"}),
}
_RELATIONS = frozenset({
    "DERIVED_FROM", "REFINES", "IMPLEMENTS", "VALIDATES",
    "GENERATED_FROM", "REFERENCES_CAPABILITY", "SUPERSEDES",
})
_GLOBAL_PROJECT_SOURCES = frozenset({
    ("capability", "CAP-02"), ("document", "DOC-02"),
    ("prototype", "PRT-04"), ("solution", "SOL-01"),
    ("plan", "PLN-03"),
})


class TraceShapeError(ValueError):
    """Safe, non-enumerating invalid TraceLink shape."""

    def __init__(self) -> None:
        super().__init__("invalid TraceLink shape")


@dataclass(frozen=True, slots=True)
class TraceVersionRef:
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if (type(self.owner_module) is not str
                or type(self.object_type) is not str
                or self.object_type not in _TYPES.get(self.owner_module, ())
                or type(self.object_id) is not uuid.UUID or self.object_id.int == 0
                or type(self.version_id) is not uuid.UUID or self.version_id.int == 0
                or not (self.scope == "GLOBAL" and self.project_id is None
                        or self.scope == "PROJECT"
                        and type(self.project_id) is uuid.UUID
                        and self.project_id.int != 0)):
            raise TraceShapeError()


@dataclass(frozen=True, slots=True)
class TraceEdgeShape:
    source: TraceVersionRef
    target: TraceVersionRef
    relation_type: str
    scope: str = ""
    project_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (type(self.source) is not TraceVersionRef
                or type(self.target) is not TraceVersionRef
                or type(self.relation_type) is not str
                or self.relation_type not in _RELATIONS
                or self.source == self.target):
            raise TraceShapeError()
        if self.source.scope == "PROJECT":
            if (self.target.scope != "PROJECT"
                    or self.source.project_id != self.target.project_id
                    or self.relation_type == "REFERENCES_CAPABILITY"):
                raise TraceShapeError()
            expected_scope, expected_project = "PROJECT", self.source.project_id
        elif self.target.scope == "GLOBAL":
            if self.relation_type == "REFERENCES_CAPABILITY":
                raise TraceShapeError()
            expected_scope, expected_project = "GLOBAL", None
        else:
            if ((self.source.owner_module, self.source.object_type)
                    not in _GLOBAL_PROJECT_SOURCES
                    or self.relation_type not in (
                        "DERIVED_FROM", "REFERENCES_CAPABILITY")
                    or self.relation_type == "REFERENCES_CAPABILITY"
                    and (self.source.owner_module, self.source.object_type)
                    != ("capability", "CAP-02")):
                raise TraceShapeError()
            expected_scope, expected_project = "PROJECT", self.target.project_id
        if self.scope not in ("", expected_scope) or self.project_id not in (None, expected_project):
            raise TraceShapeError()
        object.__setattr__(self, "scope", expected_scope)
        object.__setattr__(self, "project_id", expected_project)
