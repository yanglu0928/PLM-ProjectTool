"""Read-only fixed-version registry for built-in Output template metadata."""

from __future__ import annotations

import uuid
from types import MappingProxyType
from typing import Mapping

from plm_assistant.modules.output.application.resolve_context import (
    OutputTemplateVersion,
)


BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID = uuid.UUID(
    "a1272ce0-01f0-5e6c-9706-000000000001"
)

BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID = uuid.UUID(
    "a1272ce0-01f0-5e6c-9706-000000000002"
)

_BUILTIN_VERSIONS = (
    OutputTemplateVersion(
        template_version_ref=BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
        output_type="DOCX",
        source_kinds=("REQUIREMENT_VERSION",),
        immutable=True,
        published=True,
    ),
    OutputTemplateVersion(
        template_version_ref=BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID,
        output_type="DOCX",
        source_kinds=("PLAN_VERSION",),
        immutable=True,
        published=True,
    ),
)
_SUPPORTED_OUTPUT_TYPES = frozenset({"DOCX"})


class BuiltinOutputTemplateRegistry:
    """Resolve immutable template metadata shipped with this application version.

    The registry contains metadata only. It does not render a document, read
    files, access a customer database, discover a current template, or run code.
    New versions are appended while existing fixed refs remain available.
    """

    def __init__(
        self, entries: tuple[OutputTemplateVersion, ...] | None = None,
    ) -> None:
        values = _BUILTIN_VERSIONS if entries is None else entries
        if type(values) is not tuple:
            raise ValueError("builtin output template catalog is invalid")
        catalog: dict[uuid.UUID, OutputTemplateVersion] = {}
        for item in values:
            if (type(item) is not OutputTemplateVersion
                    or type(item.template_version_ref) is not uuid.UUID
                    or item.template_version_ref.int == 0
                    or type(item.output_type) is not str
                    or item.output_type not in _SUPPORTED_OUTPUT_TYPES
                    or type(item.source_kinds) is not tuple
                    or not item.source_kinds
                    or any(type(kind) is not str or not kind for kind in item.source_kinds)
                    or len(set(item.source_kinds)) != len(item.source_kinds)
                    or item.immutable is not True
                    or item.published is not True
                    or item.template_version_ref in catalog):
                raise ValueError("builtin output template catalog is invalid")
            catalog[item.template_version_ref] = item
        if not catalog:
            raise ValueError("builtin output template catalog is empty")
        self._catalog: Mapping[uuid.UUID, OutputTemplateVersion] = (
            MappingProxyType(catalog)
        )

    def get_immutable_version(
        self, transaction: object, *, template_version_ref: uuid.UUID,
    ) -> OutputTemplateVersion | None:
        del transaction  # Static package data; the port keeps transaction shape.
        if (type(template_version_ref) is not uuid.UUID
                or template_version_ref.int == 0):
            return None
        return self._catalog.get(template_version_ref)
