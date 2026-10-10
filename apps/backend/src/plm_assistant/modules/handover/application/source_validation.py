"""Handover-owned validation through the Document public read Port."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.document.application.read_documents import (
    DocumentVersionView, DocumentView,
)

from ..domain.source_set import canonical_handover_source_set_ref


class HandoverSourceValidationError(RuntimeError):
    """Fail-closed source observation failure without leaking document details."""


@dataclass(frozen=True, slots=True)
class HandoverDocumentRef:
    document_id: uuid.UUID
    document_version_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.document_id) is not uuid.UUID or self.document_id.int == 0
                or type(self.document_version_id) is not uuid.UUID
                or self.document_version_id.int == 0):
            raise HandoverSourceValidationError("invalid Handover document reference")


@dataclass(frozen=True, slots=True)
class ValidatedHandoverSourceSet:
    source_set_ref: str
    documents: tuple[HandoverDocumentRef, ...]


class HandoverDocumentPort(Protocol):
    def get_version_for_trace(
        self, transaction: object, *, scope: str,
        project_id: uuid.UUID | None, document_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> DocumentVersionView | None: ...

    def get(
        self, transaction: object, *, scope: str,
        project_id: uuid.UUID | None, document_id: uuid.UUID,
    ) -> DocumentView | None: ...


class HandoverSourceValidator:
    def __init__(self, documents: HandoverDocumentPort) -> None:
        if documents is None:
            raise ValueError("Handover Document Port is required")
        self._documents = documents

    def validate(
        self, transaction: object, *, project_id: uuid.UUID,
        references: tuple[HandoverDocumentRef, ...],
    ) -> ValidatedHandoverSourceSet:
        if (transaction is None or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(references) is not tuple or not 1 <= len(references) <= 500
                or any(type(item) is not HandoverDocumentRef for item in references)
                or len({item.document_version_id for item in references}) != len(references)
                or len({item.document_id for item in references}) != len(references)):
            raise HandoverSourceValidationError("HANDOVER_SOURCE_UNAVAILABLE")
        ordered = tuple(sorted(references, key=lambda item: str(item.document_version_id)))
        for reference in ordered:
            try:
                version = self._documents.get_version_for_trace(
                    transaction, scope="PROJECT", project_id=project_id,
                    document_id=reference.document_id,
                    document_version_id=reference.document_version_id,
                )
                document = self._documents.get(
                    transaction, scope="PROJECT", project_id=project_id,
                    document_id=reference.document_id,
                )
            except Exception:
                raise HandoverSourceValidationError("HANDOVER_SOURCE_UNAVAILABLE") from None
            if (type(version) is not DocumentVersionView
                    or version.document_id != reference.document_id
                    or version.document_version_id != reference.document_version_id
                    or version.availability_state != "AVAILABLE"
                    or type(document) is not DocumentView
                    or document.document_id != reference.document_id
                    or document.scope != "PROJECT" or document.project_id != project_id
                    or document.document_state != "ACTIVE"):
                raise HandoverSourceValidationError("HANDOVER_SOURCE_UNAVAILABLE")
        return ValidatedHandoverSourceSet(
            canonical_handover_source_set_ref(tuple(
                item.document_version_id for item in ordered
            )), ordered,
        )
