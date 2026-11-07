"""Read-only SQLAlchemy query for Plugin operation capability facts."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.operation_capability import (
    PluginOperationCapabilityView,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    TrustedPluginSigner,
    TrustedPluginSignerResolver,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginEnabledOperationRow,
    PluginInstallationRow,
    PluginManifestOperationRow,
    PluginPackageRow,
    PluginPackageVerificationRow,
    PluginRuntimeValidationRow,
)


class SqlAlchemyPluginOperationCapabilityRepository:
    """Fail-closed projection of one unambiguous manifest operation."""

    def __init__(self, signer_resolver: TrustedPluginSignerResolver) -> None:
        if signer_resolver is None:
            raise ValueError("Plugin signer resolver is required")
        self._signers = signer_resolver

    def get_operation(
        self, transaction: object, *, operation_id: str,
    ) -> PluginOperationCapabilityView | None:
        session = self._session(transaction)
        rows = session.execute(
            select(PluginManifestOperationRow, PluginPackageRow)
            .join(
                PluginPackageRow,
                PluginPackageRow.plugin_package_id
                == PluginManifestOperationRow.plugin_package_id,
            )
            .where(PluginManifestOperationRow.operation_id == operation_id)
            .limit(2)
        ).all()
        # Operation IDs are not globally unique in the schema. Ambiguity is unsafe.
        if len(rows) != 1:
            return None
        manifest, package = rows[0]
        output_types = manifest.output_types
        if (type(output_types) is not list or not output_types
                or len(output_types) > 32
                or any(type(value) is not str or not value for value in output_types)
                or len(set(output_types)) != len(output_types)):
            return None

        installations = session.execute(
            select(PluginInstallationRow)
            .where(
                PluginInstallationRow.plugin_id_normalized
                == package.plugin_id_normalized,
                PluginInstallationRow.installation_state == "ENABLED",
            )
            .order_by(PluginInstallationRow.plugin_installation_id)
            .limit(2)
            .with_for_update(of=PluginInstallationRow)
        ).scalars().all()
        enabled = False
        if (len(installations) == 1
                and installations[0].plugin_package_id == package.plugin_package_id):
            installation = installations[0]
            enabled_row = session.execute(
                select(PluginEnabledOperationRow.plugin_installation_id)
                .where(
                    PluginEnabledOperationRow.plugin_installation_id
                    == installation.plugin_installation_id,
                    PluginEnabledOperationRow.plugin_package_id
                    == package.plugin_package_id,
                    PluginEnabledOperationRow.plugin_id_normalized
                    == package.plugin_id_normalized,
                    PluginEnabledOperationRow.operation_id == operation_id,
                )
                .limit(2)
            ).scalars().all()
            latest_runtime = session.execute(
                select(PluginRuntimeValidationRow)
                .where(
                    PluginRuntimeValidationRow.plugin_installation_id
                    == installation.plugin_installation_id,
                )
                .order_by(
                    PluginRuntimeValidationRow.validated_at.desc(),
                    PluginRuntimeValidationRow.runtime_validation_id.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
            enabled = bool(
                len(enabled_row) == 1
                and latest_runtime is not None
                and latest_runtime.compatibility_state == "COMPATIBLE"
                and type(latest_runtime.runtime_snapshot) is dict
                and type(installation.validated_runtime_snapshot) is dict
                and latest_runtime.runtime_snapshot
                    == installation.validated_runtime_snapshot
            )

        latest_verification = session.execute(
            select(PluginPackageVerificationRow)
            .where(
                PluginPackageVerificationRow.plugin_package_id
                == package.plugin_package_id,
            )
            .order_by(
                PluginPackageVerificationRow.verified_at.desc(),
                PluginPackageVerificationRow.verification_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        trusted = False
        if (package.package_state == "VERIFIED"
                and latest_verification is not None
                and latest_verification.verification_state == "PASSED"
                and latest_verification.check_code == "SIGNED_PACKAGE_VALID"):
            try:
                signer = self._signers.resolve_trusted_signer(package.signer_key_ref)
                trusted = bool(
                    isinstance(signer, TrustedPluginSigner)
                    and signer.signer_key_ref == package.signer_key_ref
                    and signer.state == "ACTIVE"
                    and type(signer.public_key_raw) is bytes
                    and len(signer.public_key_raw) == 32
                )
            except Exception:
                trusted = False

        return PluginOperationCapabilityView(
            operation_id=operation_id,
            output_types=tuple(output_types),
            enabled=enabled,
            trusted=trusted,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise ValueError("Plugin operation capability transaction unavailable") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise ValueError("Plugin operation capability transaction unavailable")
        return session
