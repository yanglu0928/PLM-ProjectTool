"""Capability-owned validation through the Document public read Port."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.document.application.read_documents import (
    DocumentVersionView,
    DocumentView,
)

from ..domain.source_collection import canonical_source_collection_ref


class CapabilitySourceValidationError(RuntimeError):
    """Fail-closed source observation failure without leaking document details."""


@dataclass(frozen=True, slots=True)
class CapabilityDocumentRef:
    document_id: uuid.UUID
    document_version_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.document_id) is not uuid.UUID or self.document_id.int == 0
                or type(self.document_version_id) is not uuid.UUID
                or self.document_version_id.int == 0):
            raise CapabilitySourceValidationError("invalid Capability document reference")


@dataclass(frozen=True, slots=True)
class ValidatedCapabilitySourceSet:
    source_collection_ref: str
    documents: tuple[CapabilityDocumentRef, ...]


class CapabilityDocumentPort(Protocol):
    def get_version_for_trace(
        self, transaction: object, *, scope: str,
        project_id: uuid.UUID | None, document_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> DocumentVersionView | None: ...

    def get(
        self, transaction: object, *, scope: str,
        project_id: uuid.UUID | None, document_id: uuid.UUID,
    ) -> DocumentView | None: ...


class CapabilitySourceValidator:
    def __init__(self, documents: CapabilityDocumentPort) -> None:
        if documents is None:
            raise ValueError("Capability Document Port is required")
        self._documents = documents

    def validate(
        self, transaction: object,
        references: tuple[CapabilityDocumentRef, ...],
    ) -> ValidatedCapabilitySourceSet:
        if (transaction is None or type(references) is not tuple
                or not 1 <= len(references) <= 500
                or any(type(item) is not CapabilityDocumentRef for item in references)
                or len({item.document_version_id for item in references}) != len(references)
                or len({item.document_id for item in references}) != len(references)):
            raise CapabilitySourceValidationError("CAPABILITY_SOURCE_UNAVAILABLE")
        ordered = tuple(sorted(references, key=lambda item: str(item.document_version_id)))
        for reference in ordered:
            try:
                version = self._documents.get_version_for_trace(
                    transaction, scope="GLOBAL", project_id=None,
                    document_id=reference.document_id,
                    document_version_id=reference.document_version_id,
                )
                document = self._documents.get(
                    transaction, scope="GLOBAL", project_id=None,
                    document_id=reference.document_id,
                )
            except Exception:
                raise CapabilitySourceValidationError(
                    "CAPABILITY_SOURCE_UNAVAILABLE"
                ) from None
            if (type(version) is not DocumentVersionView
                    or version.document_id != reference.document_id
                    or version.document_version_id != reference.document_version_id
                    or version.availability_state != "AVAILABLE"
                    or type(document) is not DocumentView
                    or document.document_id != reference.document_id
                    or document.scope != "GLOBAL" or document.project_id is not None
                    or document.document_category != "STANDARD_CAPABILITY"
                    or document.document_state != "ACTIVE"):
                raise CapabilitySourceValidationError("CAPABILITY_SOURCE_UNAVAILABLE")
        source_ref = canonical_source_collection_ref(
            tuple(item.document_version_id for item in ordered)
        )
        return ValidatedCapabilitySourceSet(source_ref, ordered)
