"""Hosted PostgreSQL proof for Output job/request/snapshot admission binding."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import URL, update

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.output.application.job_admission import (
    OutputJobAdmissionError, OutputJobExecutionAdmissionOwner,
)
from plm_assistant.modules.output.application.resolve_context import PluginOperationCapability
from plm_assistant.modules.output.infrastructure.job_admission_repository import (
    SqlAlchemyOutputJobAdmissionRepository,
)
from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextSnapshotRow, OutputRequestRow,
)
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


def database_url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def admin_dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def create_database(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(
            sql.Identifier(name)))


def drop_database(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(name)))


class SyntheticCapabilities:
    def __init__(self, capability: PluginOperationCapability) -> None:
        self.capability = capability

    def get_operation(self, transaction: object, *, operation_id: str):
        if self.capability.operation_id != operation_id:
            return None
        return self.capability


def expect_denied(owner: OutputJobExecutionAdmissionOwner, claim) -> None:
    try:
        owner.admit(claim)
    except OutputJobAdmissionError:
        return
    raise AssertionError("invalid Output admission was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    runner_temp = os.environ.get("RUNNER_TEMP", "")
    if (sys.platform != "win32" or not 1 <= args.port <= 65535
            or not re.fullmatch(r"[0-9]{1,12}", args.run_id)
            or Path(runner_temp).drive.casefold() != "d:"):
        raise ValueError("Windows hosted PostgreSQL and D-drive runner temp required")

    database = "plm_out_p27_" + args.run_id[-10:]
    created = False
    runtime = None
    try:
        create_database(args.port, database)
        created = True
        upgrade_database(database_url(database, args.port), "head")
        runtime = create_database_runtime(database_url(database, args.port))
        actor_id, project_id = uuid.uuid4(), uuid.uuid4()
        job_id, request_id, snapshot_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        source_id, template_id = uuid.uuid4(), uuid.uuid4()
        plugin_operation = "synthetic.doc.generate"
        context = {"synthetic": {"title": "P27 fixture"}}
        fingerprint = canonical_payload_fingerprint(context)
        capability = PluginOperationCapability(
            operation_id=plugin_operation, output_types=("DOCX",),
            enabled=True, trusted=True,
        )

        with runtime.unit_of_work() as uow:
            uow.session.add(UserRow(
                user_id=actor_id, username_display="synthetic-output-admission",
                username_normalized="synthetic-output-admission", state="DISABLED",
                deployment_role="NONE",
            ))
            uow.session.add(ProjectRow(
                project_id=project_id, project_code="P27-SYNTHETIC",
                project_code_normalized="P27-SYNTHETIC",
                name="Synthetic Output Admission", created_by=actor_id,
            ))
            uow.session.flush()
            uow.session.add(OutputContextSnapshotRow(
                context_snapshot_id=snapshot_id, project_id=project_id,
                source_version_refs=[str(source_id)], context_payload=context,
                context_fingerprint=fingerprint, created_by=actor_id,
            ))
            uow.session.add(JobRow(
                job_id=job_id, owner_module="output", job_type="OUTPUT_GENERATE",
                scope="PROJECT", project_id=project_id, actor_ref=actor_id,
                trace_id=str(uuid.uuid4()),
                payload_refs={"output_request_id": str(request_id),
                              "context_snapshot_id": str(snapshot_id)},
                idempotency_key="p27-" + str(job_id), max_attempts=3,
            ))
            uow.session.flush()
            uow.session.add(OutputRequestRow(
                output_request_id=request_id, project_id=project_id,
                output_type="DOCX", template_version_ref=template_id,
                source_version_refs=[str(source_id)], output_policy_ref="synthetic-policy",
                plugin_operation=plugin_operation, context_snapshot_id=snapshot_id,
                input_fingerprint=fingerprint, generation_no=1,
                request_state="QUEUED", job_ref=job_id,
                idempotency_key="p27-request-" + str(request_id),
                trace_id=uuid.uuid4(), requested_by=actor_id,
            ))
            uow.commit()

        lease_service = JobLeaseService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyJobLeaseRepository(),
        )
        claim = lease_service.claim_next_output(
            worker_ref="p27-synthetic-output-worker", lease_seconds=60,
        )
        if claim is None or claim.job_id != job_id:
            raise AssertionError("P27 fixture was not claimed through Output-specific lease")
        repository = SqlAlchemyOutputJobAdmissionRepository()
        capabilities = SyntheticCapabilities(capability)
        owner = OutputJobExecutionAdmissionOwner(
            unit_of_work=runtime.unit_of_work, repository=repository,
            plugin_capabilities=capabilities,
        )
        admission = owner.admit(claim)
        if (admission.job_id != job_id or admission.output_request_id != request_id
                or admission.context_snapshot_id != snapshot_id
                or admission.context_fingerprint != fingerprint
                or hasattr(admission, "context_payload")):
            raise AssertionError("P27 valid admission facts do not match persisted binding")

        wrong_snapshot = uuid.uuid4()
        tampered_claim = replace(claim, payload_refs={
            **claim.payload_refs, "context_snapshot_id": str(wrong_snapshot),
        })
        expect_denied(owner, tampered_claim)

        capabilities.capability = replace(capability, enabled=False)
        expect_denied(owner, claim)
        capabilities.capability = replace(capability, trusted=False)
        expect_denied(owner, claim)
        capabilities.capability = replace(capability, output_types=("PPTX",))
        expect_denied(owner, claim)

        with runtime.unit_of_work() as uow:
            uow.session.execute(
                update(OutputContextSnapshotRow)
                .where(OutputContextSnapshotRow.context_snapshot_id == snapshot_id)
                .values(context_fingerprint=b"x" * 32)
            )
            uow.commit()
        expect_denied(owner, claim)

        result = {
            "status": "PASS_SCOPE_LIMITED",
            "wbs": "OUT-01-A01-P27",
            "valid_binding_admitted": True,
            "mismatched_snapshot_denied": True,
            "disabled_or_untrusted_or_wrong_type_denied": True,
            "altered_context_fingerprint_denied": True,
            "context_payload_returned": False,
            "schema_changed": False,
            "plugin_executed": False,
            "output_files_generated": False,
            "external_api_calls": 0,
            "customer_data": False,
            "runner_drive": "D:",
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_database(args.port, database)


if __name__ == "__main__":
    raise SystemExit(main())
