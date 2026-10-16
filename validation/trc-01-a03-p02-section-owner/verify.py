"""Disposable Win11/PG18 proof of the SOL-05 Trace owner."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.read_section_version import SectionVersionReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.trace.application.target_proof import TraceProofQuery, TraceResourceVersionRef, TraceTargetProofError


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_create_for_trace",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def denied(code, action):
    try:
        action()
    except TraceTargetProofError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def on_trace(*, port, runtime, license_guard, project, other_project,
             token, member_token, section, **_unused):
    def reader(guard):
        return SectionVersionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(),
        )
    owner = SectionVersionTraceOwner(reader(license_guard))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        versions = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no", (section,),
        ).fetchall()
        assert len(versions) == 5
        before = db.execute(
            "SELECT (SELECT count(*) FROM plm.aud_events),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts)").fetchone()
    first = versions[0][0]
    public = TraceResourceVersionRef("SOL-05", section, first)
    query = TraceProofQuery(token, uuid.uuid4())
    with runtime.unit_of_work() as tx:
        ref = owner.resolve(tx, query, project, public)
        assert ref.object_id == section and ref.version_id == first
        assert owner.prove(tx, query, ref).ref == ref
        member = TraceProofQuery(member_token, uuid.uuid4())
        assert owner.prove(tx, member, ref).ref == ref
        denied("RESOURCE_NOT_FOUND", lambda: owner.resolve(tx, query, other_project, public))
        denied("RESOURCE_NOT_FOUND", lambda: owner.resolve(
            tx, query, project, TraceResourceVersionRef(
                "SOL-05", section, uuid.uuid4())))
        denied("RESOURCE_NOT_FOUND", lambda: owner.prove(
            tx, TraceProofQuery(b"x" * 32, uuid.uuid4()), ref))
        denied("LICENSE_OPERATION_DENIED", lambda: SectionVersionTraceOwner(
            reader(DeniedLicense())).prove(tx, query, ref))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        after = db.execute(
            "SELECT (SELECT count(*) FROM plm.aud_events),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts)").fetchone()
    assert after == before, (before, after)
    print("TRC_01_A03_P02_SECTION_OWNER_PG_PASS: fixed DRAFT, same transaction, member, isolation, missing/session/license denial, zero writes")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_trace))
