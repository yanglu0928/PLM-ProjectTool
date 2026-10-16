"""Windows 11/PostgreSQL 18 proof for RequirementVersion HTTP."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.requirement_validation_source import SqlAlchemyRequirementValidationAuditSource
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import SqlAlchemyEvidenceRequirementSourceProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.api.version_cursor import RequirementVersionCursorCodec
from plm_assistant.modules.requirement.api.versions import create_requirement_version_router
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.create_version import RequirementVersionCreateService
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.application.validate_version import RequirementVersionValidationService
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.requirement.infrastructure.version_validation_repository import SqlAlchemyRequirementVersionValidationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
evidence_helpers = runpy.run_path(
    str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))
seed_evidence = evidence_helpers["seed_evidence"]
TOKENS = {"pm": b"p" * 32, "impl": b"i" * 32, "customer": b"c" * 32}


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token not in TOKENS.values() or require_csrf and csrf_token != CSRF):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers(name="pm", *, key=None, etag=None):
    result = {
        "origin": "https://plm.example.test",
        "cookie": "plm_session=" + TOKENS[name].hex(),
        "x-csrf-token": CSRF.hex(),
    }
    if key is not None:
        result["idempotency-key"] = key
    if etag is not None:
        result["if-match"] = etag
    return result


def expect(response, status):
    if response.status_code != status:
        raise AssertionError((response.status_code, response.text))
    return response.json()["data"]


def body(*, evidence, initial=True, base=None, title="Initial draft"):
    return {
        "initial": initial,
        "base_version_ref": None if base is None else str(base),
        "title": title,
        "statement": "The system shall export an approved package.",
        "rationale": "Controlled project delivery requires an immutable package.",
        "domain_name": "OUTPUT", "priority": "HIGH", "risk": "MEDIUM",
        "classification": "PENDING_CONFIRMATION",
        "sources": [{
            "source_type": "PROJECT_EVIDENCE",
            "source_object_id": str(evidence), "source_version_ref": None,
            "evidence_refs": [str(evidence)],
        }],
        "acceptance_criteria": [{
            "observable_result": "An approved package is produced",
            "verification_method": "Run release validation",
            "required_data": "Approved project data",
            "required_environment": "Windows 11",
            "evidence_requirement": "Signed release report",
        }],
        "capability_assessments": [], "assumptions": [], "exclusions": [],
        "dependencies": [], "ai_task_refs": [],
        "client_reason": "Create immutable Requirement draft",
    }


def main() -> None:
    database = "req01a10a05_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        try:
            with connect(database) as db:
                actors = {
                    name: seed_user(db, "Version HTTP " + name, "NONE", token)
                    for name, token in TOKENS.items()
                }
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQVHTTP','reqvhttp','Version HTTP Project',%s) RETURNING project_id",
                    (actors["pm"],)).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)).fetchone()[0]
                for name, role in (
                    ("pm", "PROJECT_MANAGER"),
                    ("impl", "IMPLEMENTATION_MEMBER"),
                    ("customer", "CUSTOMER_MANAGER"),
                ):
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,%s)",
                        (project, actors[name], department, role))
                evidence_one = seed_evidence(db, project, actors["pm"])
                evidence_two = seed_evidence(db, project, actors["pm"])

            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository())
            receipts = SqlAlchemyIdempotencyReceipts()
            common = dict(
                unit_of_work=runtime.unit_of_work, license_guard=guard,
                authorization=authorization, receipts=receipts,
                clock=lambda: datetime.now(timezone.utc))
            audit = AuditService(SqlAlchemyAuditRepository())
            identity = RequirementIdentityCreateService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                repository=SqlAlchemyRequirementIdentityCreateRepository(), audit=audit)
            root = identity.create_requirement(CreateRequirementIdentity(
                TOKENS["pm"], CSRF, uuid.uuid4(), project, "REQ-VERSION-HTTP",
                str(uuid.uuid4())))

            project_sources = SqlAlchemyEvidenceRequirementSourceProof()
            fixed_sources = SqlAlchemyEvidenceFixedSourceRepository()
            creates = RequirementVersionCreateService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                repository=SqlAlchemyRequirementVersionCreateRepository(), audit=audit,
                survey_sources=object(), handover_sources=object(),
                human_decisions=object(), project_evidence=project_sources,
                capability_sources=object(), fixed_evidence=fixed_sources)
            validations = RequirementVersionValidationService(
                **common, access=SqlAlchemyProjectWriteAccess(), audit=audit,
                survey_sources=object(), handover_sources=object(),
                human_decisions=object(), project_evidence=project_sources,
                capability_sources=object(), fixed_evidence=fixed_sources,
                repository=SqlAlchemyRequirementVersionValidationRepository(),
                audit_source=SqlAlchemyRequirementValidationAuditSource())
            reads = RequirementVersionReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectReadAccess(), license_guard=guard,
                authorization=authorization,
                repository=SqlAlchemyRequirementVersionReadRepository(),
                clock=lambda: datetime.now(timezone.utc))
            router = create_requirement_version_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                reads=reads, creates=creates, validations=validations,
                cursors=RequirementVersionCursorCodec(b"v" * 32))
            app = create_app(requirement_version_router=router)
            path = (f"/api/v1/projects/{project}/requirements/"
                    f"{root.requirement_id}/versions")

            with TestClient(app, base_url="https://plm.example.test") as client:
                first_key = str(uuid.uuid4())
                first = expect(client.post(
                    path, headers=headers("impl", key=first_key, etag='"v0"'),
                    json=body(evidence=evidence_one)), 201)
                replayed = expect(client.post(
                    path, headers=headers("impl", key=first_key, etag='"v0"'),
                    json=body(evidence=evidence_one)), 201)
                assert replayed == first and first["requirement_etag"] == '"v1"'

                second = expect(client.post(
                    path, headers=headers(
                        "impl", key=str(uuid.uuid4()), etag='"v1"'),
                    json=body(
                        evidence=evidence_two, initial=False,
                        base=uuid.UUID(first["requirement_version_id"]),
                        title="Second draft")), 201)
                assert second["version_no"] == 2 and second["requirement_etag"] == '"v2"'

                page_one = expect(client.get(
                    path + "?page_size=1", headers=headers("customer")), 200)
                assert page_one["has_more"] and page_one["items"][0]["version_no"] == 2
                page_two = expect(client.get(
                    path + "?page_size=1&cursor=" + page_one["next_cursor"],
                    headers=headers("customer")), 200)
                assert page_two["items"][0]["version_no"] == 1

                detail_path = path + "/" + first["requirement_version_id"]
                detail = expect(client.get(
                    detail_path, headers=headers("customer")), 200)
                assert detail["statement"].startswith("The system shall")
                assert detail["sources"][0]["source_object_id"] == str(evidence_one)
                assert len(detail["acceptance_criteria"]) == 1

                validation_key = str(uuid.uuid4())
                report = expect(client.post(
                    detail_path + ":validate",
                    headers=headers("impl", key=validation_key)), 200)
                report_replay = expect(client.post(
                    detail_path + ":validate",
                    headers=headers("impl", key=validation_key)), 200)
                assert report_replay == report
                assert not report["valid"]
                assert report["blocking_issues"] == ["PENDING_CONFIRMATION"]
                assert report["coverage_summary"]["sources"] == 1

                denied = client.post(
                    detail_path + ":validate",
                    headers=headers("customer", key=str(uuid.uuid4())))
                assert denied.status_code == 404
                guard.enabled = False
                assert client.get(path, headers=headers("customer")).status_code == 403
                guard.enabled = True

            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirement_versions"
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirement_version_create_results"
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events "
                    "WHERE action='REQUIREMENT_VERSION_VALIDATED'"
                ).fetchone()[0] == 1
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts "
                    "WHERE operation='V1_REQ_VERSION_VALIDATE'"
                ).fetchone()[0] == 1
            command.check(cfg)
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "REQ_01_A10_A05_VERSION_HTTP_PASS: four frozen HTTP operations, dedicated "
        "cursor, complete fixed snapshot, root ETag, create/validate replay, current-fact "
        "report, denials, Audit and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
