"""Disposable Win11 PG proof for atomic OutlineVersion create Owner."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_outline_version import (
    CreateOutlineVersion, OutlineVersionCreateError, OutlineVersionCreateService,
)
from plm_assistant.modules.solution.application.outline_version_input import OutlineVersionDraftInput
from plm_assistant.modules.solution.application.prove_outline_section_use import OutlineSectionUseProofService
from plm_assistant.modules.solution.application.prove_outline_version_input import OutlineVersionInputProofService
from plm_assistant.modules.solution.infrastructure.outline_version_base import SqlAlchemyCurrentOutlineVersionBase
from plm_assistant.modules.solution.infrastructure.outline_version_create_repository import SqlAlchemyOutlineVersionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_owner_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _UnusedSource:
    def prove(self, *_args, **_kwargs):
        raise AssertionError("unexpected Requirement/Reference proof")


class _BrokenAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


class _DeniedLicense:
    def require_valid(self, *, trace_id):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def rejects(code: str, operation) -> None:
    try:
        operation()
    except OutlineVersionCreateError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               token, csrf, member_token, member_csrf, manager, **_unused):
    outline, section = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            # Only synthetic upstream identities are seeded; the tested
            # OutlineVersion collection uses its real SQL Guard and Owner.
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,"
                "created_by) VALUES (%s,%s,'Version target',%s)",
                (outline, project, manager))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'Overview',%s)",
                (section, outline, project, manager))
    inputs = OutlineVersionInputProofService(
        bases=SqlAlchemyCurrentOutlineVersionBase(),
        sections=OutlineSectionUseProofService(
            sections=SqlAlchemySectionReadRepository()),
        requirements=_UnusedSource(), references=_UnusedSource())
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        inputs=inputs,
        repository=SqlAlchemyOutlineVersionCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(),
    )
    service = OutlineVersionCreateService(**dependencies, audit=audit)
    draft = OutlineVersionDraftInput(
        project, outline, (section,), (), (), ({"note": "pending source"},), ())
    cmd = CreateOutlineVersion(token, csrf, uuid.uuid4(), draft, "v" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.create(replace(
        cmd, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, session_token=b"u" * 32, csrf_token=b"v" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, draft=replace(draft, project_id=other_project))))
    denied = OutlineVersionCreateService(
        **{**dependencies, "license_guard": _DeniedLicense()}, audit=audit)
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    first = service.create(cmd)
    assert first.version_no == 1 and first.version_state == "DRAFT"
    assert service.create(replace(cmd, trace_id=uuid.uuid4())) == first
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(
        cmd, draft=replace(draft, missing_declarations=({"note": "changed"},)))))
    member = service.create(CreateOutlineVersion(
        member_token, member_csrf, uuid.uuid4(), draft, "m" * 16))
    assert member.version_no == 2 and member.supersedes_version_ref == first.solution_outline_version_id
    broken = OutlineVersionCreateService(**dependencies, audit=_BrokenAudit())
    rejects("SOLUTION_UNAVAILABLE", lambda: broken.create(replace(
        cmd, idempotency_key="f" * 16)))
    parallel = replace(cmd, idempotency_key="p" * 16)
    with ThreadPoolExecutor(max_workers=2) as pool:
        parallel_results = tuple(pool.map(service.create, (parallel, parallel)))
    assert parallel_results[0] == parallel_results[1]
    assert parallel_results[0].version_no == 3
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_outline_versions "
                          "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.sol_outline_sections "
                          "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.sol_outline_version_create_results "
                          "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                          "WHERE operation='V1_SOL_OUTLINE_VERSION_CREATE'").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_OUTLINE_VERSION_CREATED'").fetchone()[0] == 3
    print("SOL_03_A04_P03_P03_P04_A02_OUTLINE_CREATE_OWNER_PG_PASS: real "
          "Auth/Project/License/Section/PG18, replay, parallel key, next version, rollback, "
          "single receipt and audit")
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
