"""Windows/PG18 PlanVersion Create + readback HTTP verification with synthetic source proof."""
from __future__ import annotations
import argparse, uuid
from unittest.mock import Mock
import psycopg
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.create_plan_version import create_plan_version_create_router
from plm_assistant.modules.plan.api.read_plan_version import create_plan_version_read_router
from plm_assistant.modules.plan.application.create_plan_version import PlanVersionCreateService
from plm_assistant.modules.plan.application.prove_approved_solution_input import ApprovedSolutionInputProof
from plm_assistant.modules.plan.infrastructure.plan_version_create_repository import SqlAlchemyPlanVersionCreateRepository
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import SqlAlchemyPlanVersionReadRepository
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction

PROJECT, USER, PLAN, OUTLINE, SECTION, OUTLINE_VERSION = (uuid.uuid4() for _ in range(6))
class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32 or require_csrf and csrf_token != b"c" * 32: raise SessionError("AUTH_SESSION_EXPIRED")
class Proof:
    def prove(self, _tx, *, command):
        return ApprovedSolutionInputProof(command.project_id, OUTLINE, OUTLINE_VERSION,
            b"o" * 32, (), (), b"r" * 32)
class SourceProofs:
    def validate(self, *_args, **_kwargs): return None
class Audit:
    def append(self, *_args, **_kwargs): return None

def main(port: int):
    def connect(name): return psycopg.connect(host="127.0.0.1", port=port, user="poc_admin", dbname=name, autocommit=True, connect_timeout=5)
    db_name = "plncreate_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        try:
            admin.execute(f'CREATE DATABASE "{db_name}"')
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=port, database=db_name)
            config = create_migration_config(url); command.upgrade(config, "head"); command.check(config)
            with connect(db_name) as db, db.transaction():
                db.execute("INSERT INTO plm.auth_users(user_id,username_display,username_normalized) VALUES (%s,%s,%s)", (USER, "synthetic manager", "synthetic manager"))
                suffix = db_name[-6:]; code = "PC" + suffix
                db.execute("INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)", (PROJECT, code, code.lower(), "Synthetic Plan Create", USER))
                db.execute("INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) VALUES (%s,%s,%s,%s)", (PLAN, PROJECT, "Synthetic plan", USER))
                db.execute("INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) SELECT plan_id,project_id,name,created_at FROM plm.pln_plans WHERE plan_id=%s", (PLAN,))
                db.execute("INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,outline_state,created_by) VALUES (%s,%s,%s,'ACTIVE',%s)", (OUTLINE, PROJECT, "Synthetic Approved Outline", USER))
                db.execute("INSERT INTO plm.sol_outline_create_results(solution_outline_id,project_id,name,created_at) SELECT solution_outline_id,project_id,name,created_at FROM plm.sol_outlines WHERE solution_outline_id=%s", (OUTLINE,))
                db.execute("INSERT INTO plm.sol_sections(solution_section_id,project_id,solution_outline_id,section_key,created_by) VALUES (%s,%s,%s,%s,%s)", (SECTION, PROJECT, OUTLINE, "synthetic-section", USER))
                db.execute("INSERT INTO plm.sol_section_create_results(solution_section_id,solution_outline_id,project_id,section_key,created_at) SELECT solution_section_id,solution_outline_id,project_id,section_key,created_at FROM plm.sol_sections WHERE solution_section_id=%s", (SECTION,))
                db.execute("INSERT INTO plm.sol_outline_versions(solution_outline_version_id,solution_outline_id,project_id,version_no,version_state,content_fingerprint,missing_declarations,conflict_declarations,declared_section_count,declared_requirement_count,declared_reference_count,created_by) VALUES (%s,%s,%s,1,'DRAFT',%s,'[{\"reason\":\"synthetic fixture\"}]','[]',1,0,0,%s)", (OUTLINE_VERSION, OUTLINE, PROJECT, b"o"*32, USER))
                db.execute("INSERT INTO plm.sol_outline_sections(solution_outline_version_id,solution_outline_id,project_id,solution_section_id,ordinal) VALUES (%s,%s,%s,%s,1)", (OUTLINE_VERSION, OUTLINE, PROJECT, SECTION))
                db.execute("INSERT INTO plm.sol_outline_version_create_results(solution_outline_version_id,solution_outline_id,project_id,version_no,content_fingerprint,missing_declarations,conflict_declarations,declared_section_count,declared_requirement_count,declared_reference_count,supersedes_version_ref,created_by,created_at) SELECT solution_outline_version_id,solution_outline_id,project_id,version_no,content_fingerprint,missing_declarations,conflict_declarations,declared_section_count,declared_requirement_count,declared_reference_count,supersedes_version_ref,created_by,created_at FROM plm.sol_outline_versions WHERE solution_outline_version_id=%s", (OUTLINE_VERSION,))
            engine = create_engine(url)
            try:
                uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine, expire_on_commit=False))
                access, licenses, authz = Mock(), Mock(), Mock(); access.authenticated_user.return_value = USER
                licenses.require_valid.return_value = object()
                authz.require_in_transaction.side_effect = lambda tx, *, user_id, project_id, operation: AuthorizedProjectAction(user_id, project_id, operation, "PROJECT_MANAGER")
                service = PlanVersionCreateService(unit_of_work=uow, access=access, license_guard=licenses,
                    authorization=authz, solution_proof=Proof(), source_proofs=SourceProofs(),
                    repository=SqlAlchemyPlanVersionCreateRepository(), receipts=SqlAlchemyIdempotencyReceipts(), audit=Audit())
                read_access, read_authz, read_license = Mock(), Mock(), Mock()
                read_access.authenticated_user.return_value = USER; read_license.require_valid.return_value = object()
                read_authz.require_in_transaction.side_effect = authz.require_in_transaction.side_effect
                sessions, origins = Sessions(), LoginOriginPolicy(["https://plm.example.test"])
                create_router = create_plan_version_create_router(sessions=sessions, origins=origins, creates=service)
                read_service = __import__("plm_assistant.modules.plan.application.read_plan_version", fromlist=["PlanVersionReadService"]).PlanVersionReadService(
                    unit_of_work=uow, access=read_access, license_guard=read_license, authorization=read_authz,
                    repository=SqlAlchemyPlanVersionReadRepository())
                read_router = create_plan_version_read_router(sessions=sessions, origins=origins, reads=read_service)
                body = {"approved_solution_refs":[{"resource_kind":"OUTLINE","resource_id":str(OUTLINE),"version_id":str(OUTLINE_VERSION),"spec_series_id":None,"spec_type":None}],
                    "wbs_items":[{"wbs_item_id":str(uuid.uuid4()),"parent_item_id":None,"wbs_code":"TASK-001","name":"Synthetic implementation task","level":1,"category":"IMPLEMENTATION","owner_ref":None,"support_role_refs":[],"planned_start":None,"planned_finish":None,"duration_minutes":None,"actual_start":None,"actual_finish":None,"item_state":"NOT_STARTED","entry_conditions":[],"acceptance_criteria":["Synthetic acceptance criterion"],"requirement_refs":[],"solution_refs":[{"resource_kind":"OUTLINE","resource_id":str(OUTLINE),"version_id":str(OUTLINE_VERSION),"spec_series_id":None,"spec_type":None}],"prototype_refs":[],"evidence_refs":[],"output_refs":[],"risk":None,"explicit_exclusion":None}],
                    "dependencies":[],"milestones":[],"calendar_ref":"CN_WORKDAY","exclusions":[]}
                headers = {"cookie":"plm_session="+(b"s"*32).hex(),"origin":"https://plm.example.test","x-csrf-token":(b"c"*32).hex(),"idempotency-key":"synthetic-plan-create-01"}
                with TestClient(create_app(plan_version_create_router=create_router, plan_version_read_router=read_router), base_url="https://plm.example.test") as client:
                    path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions"; created = client.post(path, headers=headers, json=body)
                    assert created.status_code == 201, created.text
                    version = created.json()["data"]["plan_version_id"]
                    fixed = client.get(path+"/"+version, headers={"cookie":headers["cookie"],"origin":headers["origin"]})
                    assert fixed.status_code == 200, fixed.text
                    data = fixed.json()["data"]
                    assert data["version_state"] == "DRAFT" and data["wbs_items"][0]["acceptance_criteria"] == ["Synthetic acceptance criterion"]
                    assert data["approved_solution_refs"][0]["version_id"] == str(OUTLINE_VERSION)
                print("PLAN_VERSION_CREATE Win11/PG18 SQL+HTTP+fixed readback PASS; source-proof/Session/License/Project policy synthetic")
            finally: engine.dispose()
        finally: admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, required=True); main(parser.parse_args().port)
