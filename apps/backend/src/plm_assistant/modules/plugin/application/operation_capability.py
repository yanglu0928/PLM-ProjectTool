"""Read-only Plugin operation capability owner projection."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_OPERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,254}", re.ASCII)
_OUTPUT_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,31}", re.ASCII)


@dataclass(frozen=True, slots=True)
class PluginOperationCapabilityView:
    """Minimal public facts needed by Output; contains no package or runtime data."""

    operation_id: str
    output_types: tuple[str, ...]
    enabled: bool
    trusted: bool


class PluginOperationCapabilityRepositoryPort(Protocol):
    def get_operation(
        self, transaction: object, *, operation_id: str,
    ) -> PluginOperationCapabilityView | None: ...


class PluginOperationCapabilityReader:
    """Queries the Plugin-owned read projection inside the caller transaction."""

    def __init__(self, repository: PluginOperationCapabilityRepositoryPort) -> None:
        if repository is None:
            raise ValueError("Plugin operation capability repository is required")
        self._repository = repository

    def get_operation(
        self, transaction: object, *, operation_id: str,
    ) -> PluginOperationCapabilityView | None:
        if (transaction is None or type(operation_id) is not str
                or _OPERATION.fullmatch(operation_id) is None):
            return None
        try:
            result = self._repository.get_operation(
                transaction, operation_id=operation_id,
            )
            if result is None:
                return None
            if (type(result) is not PluginOperationCapabilityView
                    or result.operation_id != operation_id
                    or type(result.output_types) is not tuple
                    or not result.output_types
                    or len(result.output_types) > 32
                    or any(type(value) is not str
                           or _OUTPUT_TYPE.fullmatch(value) is None
                           for value in result.output_types)
                    or len(set(result.output_types)) != len(result.output_types)
                    or type(result.enabled) is not bool
                    or type(result.trusted) is not bool):
                return None
            return result
        except Exception:
            # Output treats unavailable or malformed owner facts as absent.
            return None
