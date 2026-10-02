"""Fail-closed Owner resolution for frozen AI Task input version references."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol


_PUBLIC_TYPE = re.compile(r"^[A-Z][A-Z0-9-]{0,63}$")
_OWNER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OBJECT_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class AIInputResolutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIInputResolutionQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AIInputResourceVersionRef:
    resource_type: str
    resource_id: uuid.UUID
    version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AIResolvedInputVersionRef:
    resource_type: str
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None


class AIInputOwnerPort(Protocol):
    def resolve(self, transaction: object, query: AIInputResolutionQuery,
                path_project_id: uuid.UUID,
                ref: AIInputResourceVersionRef) -> AIResolvedInputVersionRef: ...


class AIInputVersionResolver:
    """Resolve only registered public types and prove exact same-project versions."""

    def __init__(self, owners: Mapping[str, AIInputOwnerPort]) -> None:
        if type(owners) is not dict or any(
            type(resource_type) is not str
            or _PUBLIC_TYPE.fullmatch(resource_type) is None
            or owner is None
            for resource_type, owner in owners.items()
        ):
            raise ValueError("AI input owners must be explicitly registered")
        self._owners = dict(owners)

    def resolve_all(
        self, transaction: object, query: AIInputResolutionQuery,
        project_id: uuid.UUID, refs: tuple[AIInputResourceVersionRef, ...],
    ) -> tuple[AIResolvedInputVersionRef, ...]:
        if (transaction is None or type(query) is not AIInputResolutionQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(refs) is not tuple or not 1 <= len(refs) <= 1000):
            raise AIInputResolutionError("VALIDATION_FAILED")
        keys: set[tuple[str, uuid.UUID, uuid.UUID]] = set()
        for ref in refs:
            if (type(ref) is not AIInputResourceVersionRef
                    or type(ref.resource_type) is not str
                    or _PUBLIC_TYPE.fullmatch(ref.resource_type) is None
                    or type(ref.resource_id) is not uuid.UUID or ref.resource_id.int == 0
                    or type(ref.version_id) is not uuid.UUID or ref.version_id.int == 0):
                raise AIInputResolutionError("VALIDATION_FAILED")
            key = (ref.resource_type, ref.resource_id, ref.version_id)
            if key in keys:
                raise AIInputResolutionError("VALIDATION_FAILED")
            keys.add(key)
        resolved: list[AIResolvedInputVersionRef] = []
        for ref in refs:
            owner = self._owners.get(ref.resource_type)
            if owner is None:
                raise AIInputResolutionError("RESOURCE_NOT_FOUND")
            try:
                item = owner.resolve(transaction, query, project_id, ref)
            except AIInputResolutionError:
                raise
            except Exception:
                raise AIInputResolutionError("AI_INPUT_UNAVAILABLE") from None
            if (type(item) is not AIResolvedInputVersionRef
                    or item.resource_type != ref.resource_type
                    or item.object_id != ref.resource_id
                    or item.version_id != ref.version_id
                    or type(item.owner_module) is not str
                    or _OWNER.fullmatch(item.owner_module) is None
                    or type(item.object_type) is not str
                    or _OBJECT_TYPE.fullmatch(item.object_type) is None):
                raise AIInputResolutionError("AI_INPUT_UNAVAILABLE")
            if item.scope != "PROJECT" or item.project_id != project_id:
                raise AIInputResolutionError("RESOURCE_NOT_FOUND")
            resolved.append(item)
        return tuple(resolved)
