"""Transactional PostgreSQL persistence for verified Plugin package metadata."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.manifest_parser import (
    ParsedPluginManifest,
)
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageIdentity,
    PluginPackageRegistrationError,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerification,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginManifestDependencyRow,
    PluginManifestOperationRow,
    PluginPackageRow,
    PluginPackageVerificationRow,
)


class SqlAlchemyPluginPackageRegistrationRepository:
    """Persists metadata in the caller's transaction and never commits it."""

    def lock_identity(
        self, transaction: object, *, plugin_id: str, version: str,
    ) -> None:
        session = self._session(transaction)
        lock_key = f"plugin-package:{plugin_id}:{version}"
        session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )

    def find_by_identity(
        self, transaction: object, *, plugin_id: str, version: str,
    ) -> PluginPackageIdentity | None:
        row = self._session(transaction).execute(
            select(PluginPackageRow).where(
                PluginPackageRow.plugin_id_normalized == plugin_id,
                PluginPackageRow.plugin_version == version,
            ).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return None
        return PluginPackageIdentity(
            plugin_package_id=row.plugin_package_id,
            plugin_id_normalized=row.plugin_id_normalized,
            plugin_version=row.plugin_version,
            package_sha256=bytes(row.package_sha256),
            signature=bytes(row.signature),
            signer_key_ref=row.signer_key_ref,
            compatibility_policy_ref=row.compatibility_policy_ref,
            manifest_snapshot=dict(row.manifest_snapshot),
            package_state=row.package_state,
        )

    def create_verified(
        self, transaction: object, *, package_id: uuid.UUID,
        manifest: ParsedPluginManifest, manifest_snapshot: dict,
        signature_verification: PluginPackageSignatureVerification,
        signature: bytes, compatibility_policy_ref: str,
        evidence_fingerprint: bytes, verified_at: datetime,
    ) -> PluginPackageIdentity:
        session = self._session(transaction)
        summary = (
            "Signature, ZIP envelope, Manifest, and compatibility checks passed; "
            "installation and runtime safety were not assessed."
        )
        package = PluginPackageRow(
            plugin_package_id=package_id,
            plugin_id_normalized=manifest.plugin_id,
            plugin_version=manifest.version,
            package_sha256=signature_verification.package_sha256,
            manifest_snapshot=manifest_snapshot,
            signature=signature,
            signer_key_ref=signature_verification.signer_key_ref,
            compatibility_policy_ref=compatibility_policy_ref,
            package_state="VERIFIED",
            verified_at=verified_at,
            verification_summary=summary,
            lock_version=0,
        )
        session.add(package)
        session.add_all(
            PluginManifestOperationRow(
                plugin_package_id=package_id,
                operation_id=item.operation_id,
                output_types=list(item.output_types),
                plugin_api_version=manifest.plugin_api_version,
            )
            for item in manifest.operations
        )
        session.add_all(
            PluginManifestDependencyRow(
                dependency_id=uuid.uuid4(),
                plugin_package_id=package_id,
                dependency_name=item.name,
                version_spec=item.version_spec,
                dependency_kind=item.kind,
            )
            for item in manifest.dependencies
        )
        session.add(PluginPackageVerificationRow(
            verification_id=uuid.uuid4(),
            plugin_package_id=package_id,
            verification_state="PASSED",
            check_code="SIGNED_PACKAGE_VALID",
            summary=summary,
            evidence_fingerprint=evidence_fingerprint,
            verified_at=verified_at,
        ))
        session.flush()
        return PluginPackageIdentity(
            plugin_package_id=package_id,
            plugin_id_normalized=manifest.plugin_id,
            plugin_version=manifest.version,
            package_sha256=signature_verification.package_sha256,
            signature=signature,
            signer_key_ref=signature_verification.signer_key_ref,
            compatibility_policy_ref=compatibility_policy_ref,
            manifest_snapshot=dict(manifest_snapshot),
            package_state="VERIFIED",
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginPackageRegistrationError(
                "PLUGIN_PACKAGE_STORE_UNAVAILABLE"
            ) from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginPackageRegistrationError(
                "PLUGIN_PACKAGE_STORE_UNAVAILABLE"
            )
        return session
