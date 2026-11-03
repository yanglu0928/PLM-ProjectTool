"""Atomic internal registration of cryptographically verified Plugin package metadata."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.plugin.application.package_archive_inspector import (
    MAX_PACKAGE_BYTES,
    InspectedPluginPackage,
    PluginPackageArchiveInspector,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerification,
)
from plm_assistant.modules.plugin.application.manifest_parser import ParsedPluginManifest
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork

_POLICY_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$", re.ASCII)
_SUMMARY = (
    "Signature, ZIP envelope, Manifest, and compatibility checks passed; "
    "installation and runtime safety were not assessed."
)


class PluginPackageRegistrationError(RuntimeError):
    """Stable, non-sensitive package registration rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RegisterPluginPackageCommand:
    archive_bytes: bytes = field(repr=False)
    detached_signature: bytes = field(repr=False)
    signer_key_ref: str
    compatibility_policy_ref: str
    trace_id: uuid.UUID
    actor_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PluginPackageCompatibilityAssessment:
    compatible: bool
    failure_code: str | None = None


class PluginPackageCompatibilityPort(Protocol):
    def evaluate(
        self, manifest: ParsedPluginManifest, *, policy_ref: str,
    ) -> PluginPackageCompatibilityAssessment: ...


@dataclass(frozen=True, slots=True)
class PluginPackageIdentity:
    plugin_package_id: uuid.UUID
    plugin_id_normalized: str
    plugin_version: str
    package_sha256: bytes = field(repr=False)
    signature: bytes = field(repr=False)
    signer_key_ref: str
    compatibility_policy_ref: str
    manifest_snapshot: dict = field(repr=False)
    package_state: str


class PluginPackageRegistrationRepositoryPort(Protocol):
    def lock_identity(
        self, transaction: object, *, plugin_id: str, version: str,
    ) -> None: ...

    def find_by_identity(
        self, transaction: object, *, plugin_id: str, version: str,
    ) -> PluginPackageIdentity | None: ...

    def create_verified(
        self, transaction: object, *, package_id: uuid.UUID,
        manifest: ParsedPluginManifest, manifest_snapshot: dict,
        signature_verification: PluginPackageSignatureVerification,
        signature: bytes, compatibility_policy_ref: str,
        evidence_fingerprint: bytes, verified_at: datetime,
    ) -> PluginPackageIdentity: ...


class PluginPackageRegistrationService:
    """Validate a signed archive, then atomically register only its metadata.

    ZIP bytes are processed in memory and never persisted. This internal owner is
    not an HTTP endpoint and does not install or execute the package.
    """

    def __init__(
        self, *, unit_of_work: Callable[[], UnitOfWork],
        inspector: PluginPackageArchiveInspector,
        compatibility: PluginPackageCompatibilityPort,
        repository: PluginPackageRegistrationRepositoryPort,
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, inspector, compatibility, repository, audit,
        )):
            raise ValueError("Plugin package registration dependencies are required")
        self._uow = unit_of_work
        self._inspector = inspector
        self._compatibility = compatibility
        self._repository = repository
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def register(
        self, command: RegisterPluginPackageCommand,
    ) -> PluginPackageIdentity:
        self._validate(command)
        try:
            inspected = self._inspector.inspect_and_verify(
                command.archive_bytes,
                detached_signature=command.detached_signature,
                signer_key_ref=command.signer_key_ref,
            )
            if type(inspected) is not InspectedPluginPackage:
                raise PluginPackageRegistrationError("PLUGIN_PACKAGE_INVALID")
            assessment = self._compatibility.evaluate(
                inspected.manifest,
                policy_ref=command.compatibility_policy_ref,
            )
            self._check_assessment(assessment)
            snapshot = self._manifest_snapshot(inspected.manifest)
            fingerprint = self._evidence_fingerprint(
                inspected, command.compatibility_policy_ref,
            )
            with self._uow() as transaction:
                self._repository.lock_identity(
                    transaction,
                    plugin_id=inspected.manifest.plugin_id,
                    version=inspected.manifest.version,
                )
                existing = self._repository.find_by_identity(
                    transaction,
                    plugin_id=inspected.manifest.plugin_id,
                    version=inspected.manifest.version,
                )
                if existing is not None:
                    if not self._same_package(
                        existing, inspected, command, snapshot,
                    ):
                        raise PluginPackageRegistrationError(
                            "PLUGIN_PACKAGE_VERSION_CONFLICT"
                        )
                    transaction.commit()
                    return existing

                package = self._repository.create_verified(
                    transaction,
                    package_id=uuid.uuid4(),
                    manifest=inspected.manifest,
                    manifest_snapshot=snapshot,
                    signature_verification=inspected.signature_verification,
                    signature=command.detached_signature,
                    compatibility_policy_ref=command.compatibility_policy_ref,
                    evidence_fingerprint=fingerprint,
                    verified_at=self._clock(),
                )
                self._audit.append(
                    transaction,
                    AuditEventDraft(
                        trace_id=command.trace_id,
                        event_scope="DEPLOYMENT",
                        target_project_id=None,
                        actor_type="USER",
                        actor_id=command.actor_id,
                        original_actor_id=None,
                        actor_hint_digest=None,
                        action="PLUGIN_PACKAGE_REGISTER",
                        outcome="SUCCESS",
                        target_owner_module="plugin",
                        target_object_type="PLG-01",
                        target_object_id=package.plugin_package_id,
                        after_state="VERIFIED",
                    ),
                )
                transaction.commit()
                return package
        except PluginPackageRegistrationError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if type(code) is str and code.startswith("PLUGIN_"):
                raise PluginPackageRegistrationError(code) from None
            raise PluginPackageRegistrationError(
                "PLUGIN_PACKAGE_STORE_UNAVAILABLE"
            ) from None

    @staticmethod
    def _validate(command: object) -> None:
        if (
            type(command) is not RegisterPluginPackageCommand
            or type(command.archive_bytes) is not bytes
            or not 1 <= len(command.archive_bytes) <= MAX_PACKAGE_BYTES
            or type(command.detached_signature) is not bytes
            or len(command.detached_signature) != 64
            or type(command.signer_key_ref) is not str
            or not command.signer_key_ref
            or command.signer_key_ref != command.signer_key_ref.strip()
            or len(command.signer_key_ref.encode("utf-8", "strict")) > 512
            or any(unicodedata.category(c) == "Cc" for c in command.signer_key_ref)
            or type(command.compatibility_policy_ref) is not str
            or _POLICY_REF.fullmatch(command.compatibility_policy_ref) is None
            or type(command.trace_id) is not uuid.UUID
            or not command.trace_id.int
            or type(command.actor_id) is not uuid.UUID
            or not command.actor_id.int
        ):
            raise PluginPackageRegistrationError("PLUGIN_PACKAGE_INVALID")

    @staticmethod
    def _check_assessment(assessment: object) -> None:
        if type(assessment) is not PluginPackageCompatibilityAssessment:
            raise PluginPackageRegistrationError(
                "PLUGIN_PACKAGE_POLICY_UNAVAILABLE"
            )
        if assessment.compatible is True and assessment.failure_code is None:
            return
        if (
            assessment.compatible is False
            and assessment.failure_code in {
                "PLUGIN_API_INCOMPATIBLE", "PLUGIN_OS_INCOMPATIBLE",
            }
        ):
            raise PluginPackageRegistrationError(assessment.failure_code)
        raise PluginPackageRegistrationError("PLUGIN_PACKAGE_POLICY_UNAVAILABLE")

    @staticmethod
    def _manifest_snapshot(manifest: ParsedPluginManifest) -> dict:
        return {
            "schema_version": "plm.plugin.manifest.v1",
            "plugin_id": manifest.plugin_id,
            "name": manifest.name,
            "version": manifest.version,
            "plugin_api_version": manifest.plugin_api_version,
            "supported_os": list(manifest.supported_os),
            "architecture": manifest.architecture,
            "entry_point": manifest.entry_point,
            "operations": [
                {
                    "operation_id": item.operation_id,
                    "output_types": list(item.output_types),
                }
                for item in manifest.operations
            ],
            "dependencies": [
                {
                    "name": item.name,
                    "version_spec": item.version_spec,
                    "kind": item.kind,
                }
                for item in manifest.dependencies
            ],
            "canonical_sha256": manifest.canonical_sha256.hex(),
        }

    @staticmethod
    def _evidence_fingerprint(
        inspected: InspectedPluginPackage, policy_ref: str,
    ) -> bytes:
        key_ref = inspected.signature_verification.signer_key_ref.encode("utf-8")
        policy = policy_ref.encode("ascii")
        message = (
            b"PLM-PLUGIN-REGISTRATION\x00v1\x00"
            + inspected.signature_verification.package_sha256
            + inspected.manifest.canonical_sha256
            + len(key_ref).to_bytes(2, "big")
            + key_ref
            + len(policy).to_bytes(2, "big")
            + policy
        )
        return hashlib.sha256(message).digest()

    @staticmethod
    def _same_package(
        existing: PluginPackageIdentity, inspected: InspectedPluginPackage,
        command: RegisterPluginPackageCommand, snapshot: dict,
    ) -> bool:
        return bool(
            existing.package_state == "VERIFIED"
            and existing.package_sha256
                == inspected.signature_verification.package_sha256
            and existing.signature == command.detached_signature
            and existing.signer_key_ref
                == inspected.signature_verification.signer_key_ref
            and existing.compatibility_policy_ref
                == command.compatibility_policy_ref
            and existing.manifest_snapshot == snapshot
        )
