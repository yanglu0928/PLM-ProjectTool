"""SQLAlchemy persistence for the initial PluginExecution admission Owner."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.execution_admission import (
    PluginExecutionAdmissionError,
    PluginExecutionAdmissionSnapshot,
    PluginExecutionTarget,
    AdmitPluginExecutionCommand,
)
from plm_assistant.modules.output.application.job_admission import (
    OutputExecutionAdmission,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginEnabledOperationRow,
    PluginExecutionRow,
    PluginExecutionStateEventRow,
    PluginInstallationRow,
    PluginManifestOperationRow,
    PluginPackageRow,
)


class SqlAlchemyPluginExecutionAdmissionRepository:
    """Uses only the caller's transaction; all writes stay owner controlled."""

    def get_execution_target(
        self, transaction: object, *, operation_id: str,
    ) -> PluginExecutionTarget | None:
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
            .with_for_update(of=[PluginManifestOperationRow, PluginPackageRow])
        ).all()
        if len(rows) != 1:
            return None
        manifest_operation, package = rows[0]
        if package.package_state != "VERIFIED":
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
        if (len(installations) != 1
                or installations[0].plugin_package_id != package.plugin_package_id):
            return None
        enabled = session.execute(
            select(PluginEnabledOperationRow.plugin_installation_id)
            .where(
                PluginEnabledOperationRow.plugin_installation_id
                == installations[0].plugin_installation_id,
                PluginEnabledOperationRow.plugin_package_id
                == package.plugin_package_id,
                PluginEnabledOperationRow.plugin_id_normalized
                == package.plugin_id_normalized,
                PluginEnabledOperationRow.operation_id == operation_id,
            )
            .limit(2)
        ).scalars().all()
        if len(enabled) != 1:
            return None
        return PluginExecutionTarget(
            plugin_installation_id=installations[0].plugin_installation_id,
            plugin_package_id=package.plugin_package_id,
            plugin_id_normalized=package.plugin_id_normalized,
            operation_id=manifest_operation.operation_id,
        )

    def find_by_job(
        self, transaction: object, *, job_id: uuid.UUID,
    ) -> PluginExecutionAdmissionSnapshot | None:
        row = self._session(transaction).execute(
            select(PluginExecutionRow).where(
                PluginExecutionRow.job_id == job_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return None
        return PluginExecutionAdmissionSnapshot(
            plugin_execution_id=row.plugin_execution_id,
            project_id=row.project_id,
            output_request_id=row.output_request_id,
            output_context_snapshot_id=row.output_context_snapshot_id,
            plugin_installation_id=row.plugin_installation_id,
            plugin_package_id=row.plugin_package_id,
            plugin_id_normalized=row.plugin_id_normalized,
            operation_id=row.operation_id,
            context_fingerprint=bytes(row.context_fingerprint),
            job_id=row.job_id,
            attempt_no=row.attempt_no,
            execution_state=row.execution_state,
        )

    def authorize_owner_writes(self, transaction: object) -> None:
        self._session(transaction).execute(
            text("SELECT set_config('plm.plugin_execution_owner_write','on',true)")
        )

    def create_pending(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        command: AdmitPluginExecutionCommand,
        admission: OutputExecutionAdmission, target: PluginExecutionTarget,
        trace_id: uuid.UUID, idempotency_key: str,
    ) -> PluginExecutionAdmissionSnapshot:
        session = self._session(transaction)
        claim = command.claim
        row = PluginExecutionRow(
            plugin_execution_id=plugin_execution_id,
            project_id=admission.project_id,
            output_request_id=admission.output_request_id,
            output_context_snapshot_id=admission.context_snapshot_id,
            plugin_installation_id=target.plugin_installation_id,
            plugin_package_id=target.plugin_package_id,
            plugin_id_normalized=target.plugin_id_normalized,
            operation_id=target.operation_id,
            context_fingerprint=admission.context_fingerprint,
            job_id=claim.job_id,
            attempt_no=claim.attempt_no,
            idempotency_key=idempotency_key,
            execution_state="PENDING",
            trace_id=trace_id,
        )
        session.add(row)
        session.flush([row])
        return PluginExecutionAdmissionSnapshot(
            plugin_execution_id=plugin_execution_id,
            project_id=admission.project_id,
            output_request_id=admission.output_request_id,
            output_context_snapshot_id=admission.context_snapshot_id,
            plugin_installation_id=target.plugin_installation_id,
            plugin_package_id=target.plugin_package_id,
            plugin_id_normalized=target.plugin_id_normalized,
            operation_id=target.operation_id,
            context_fingerprint=admission.context_fingerprint,
            job_id=claim.job_id,
            attempt_no=claim.attempt_no,
            execution_state="PENDING",
        )

    def append_pending_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, trace_id: uuid.UUID,
    ) -> None:
        session = self._session(transaction)
        session.add(PluginExecutionStateEventRow(
            plugin_execution_id=plugin_execution_id,
            project_id=project_id,
            from_state=None,
            to_state="PENDING",
            reason_code="ADMITTED",
            actor_id=None,
            trace_id=trace_id,
        ))
        session.flush()

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginExecutionAdmissionError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginExecutionAdmissionError()
        return session
