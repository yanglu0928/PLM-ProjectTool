"""Plugin-owned persistence contract for signed import staging metadata."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.plugin.application.package_archive_inspector import MAX_PACKAGE_BYTES


@dataclass(frozen=True, slots=True)
class StorePluginPackageImportStaging:
    package_upload_id: uuid.UUID
    package_sha256: bytes = field(repr=False)
    package_size_bytes: int
    detached_signature: bytes = field(repr=False)
    signer_key_ref: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.package_upload_id) is not uuid.UUID
                or self.package_upload_id.int == 0
                or type(self.package_sha256) is not bytes
                or len(self.package_sha256) != 32
                or type(self.package_size_bytes) is not int
                or not 0 < self.package_size_bytes <= MAX_PACKAGE_BYTES
                or type(self.detached_signature) is not bytes
                or len(self.detached_signature) != 64
                or type(self.signer_key_ref) is not str
                or not self.signer_key_ref
                or self.signer_key_ref != self.signer_key_ref.strip()
                or len(self.signer_key_ref.encode("utf-8", "strict")) > 512):
            raise ValueError("Invalid Plugin package import staging metadata")


class PluginPackageImportStagingRepositoryPort(Protocol):
    def add(self, transaction: object, *, request: StorePluginPackageImportStaging) -> None: ...
