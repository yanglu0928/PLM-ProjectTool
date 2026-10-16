"""Canonical immutable identity for one GLOBAL capability source set."""

from __future__ import annotations

import hashlib
import uuid


class CapabilitySourceCollectionError(ValueError):
    """Fixed-message source-set validation failure."""


def canonical_source_collection_ref(
    document_version_ids: tuple[uuid.UUID, ...],
) -> str:
    if (type(document_version_ids) is not tuple
            or not 1 <= len(document_version_ids) <= 500
            or any(type(value) is not uuid.UUID or value.int == 0
                   for value in document_version_ids)
            or len(set(document_version_ids)) != len(document_version_ids)):
        raise CapabilitySourceCollectionError("invalid Capability source collection")
    ordered = sorted(str(value) for value in document_version_ids)
    payload = ("capability-source-set.v1\n" + "\n".join(ordered)).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()
