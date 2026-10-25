"""Windows 11/PostgreSQL 18 proof for authorized Retrieval read projections."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.rag.application.retrieval_read import (
    GetRAGRetrieval,
    RAGRetrievalReadError,
    RAGRetrievalReadService,
)
from plm_assistant.modules.rag.infrastructure.retrieval_read_repository import (
    SqlAlchemyRAGRetrievalReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker_fixture = load(
    ROOT / "validation/rag-04-a05-p02-retrieval-worker-context/verify.py",
    "rag_read_worker_fixture",
)
create_fixture = worker_fixture.create_fixture
begin_fixture = worker_fixture.begin_fixture


def seed_user(db, *, display: str, normalized: str, token: bytes,
              project, department, role: str):
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (display, normalized),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
        "password_hash,algorithm_id,parameter_set) VALUES "
        "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,"
        "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
        (credential, actor),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) VALUES "
        "(%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
        "statement_timestamp()+interval '2 hours')",
        (hashlib.sha256(token).digest(), hashlib.sha256(b"c" * 32).digest(), actor),
    )
    db.execute(
        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
        "project_role) VALUES (%s,%s,%s,%s)",
        (project, actor, department, role),
    )
    return actor


def expect(code: str, action) -> None:
    try:
        action()
    except RAGRetrievalReadError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def execute(context, envelope, sender, adapter) -> None:
    worker_fixture.execute(context, envelope, sender, adapter)
    database, runtime = context["database"], context["runtime"]
    creator, project = context["actor"], context["project"]
    creator_token = b"z" * 32
    manager_token, member_token = b"m" * 32, b"n" * 32
    with begin_fixture.connect(database) as db:
        department = db.execute(
            "SELECT department_id FROM plm.prj_departments WHERE project_id=%s "
            "ORDER BY created_at LIMIT 1", (project,),
        ).fetchone()[0]
        manager = seed_user(
            db, display="RAG Read Manager", normalized="rag read manager",
            token=manager_token, project=project, department=department,
            role="PROJECT_MANAGER",
        )
        member = seed_user(
            db, display="RAG Read Member", normalized="rag read member",
            token=member_token, project=project, department=department,
            role="IMPLEMENTATION_MEMBER",
        )
        run_id = db.execute(
            "SELECT retrieval_run_id FROM plm.rag_retrieval_runs "
            "WHERE project_id=%s AND retrieval_state='SUCCEEDED' "
            "ORDER BY completed_at DESC LIMIT 1", (project,),
        ).fetchone()[0]

    guard = create_fixture.activation_fixture.quality_fixture.Guard()
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    service = RAGRetrievalReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=guard,
        authorization=authorization,
        repository=SqlAlchemyRAGRetrievalReadRepository(),
    )

    def query(token, project_id=project):
        return GetRAGRetrieval(token, uuid.uuid4(), project_id, run_id)

    run = service.get_run(query(creator_token))
    result = service.get_result(query(creator_token))
    bundle = service.get_context(query(creator_token))
    assert run.requested_by == creator and run.retrieval_state == "SUCCEEDED"
    assert len(result.candidates) == 1
    assert "PLM begin one" in result.candidates[0].snippet
    assert len(bundle.items) == 1 and "PLM begin one" in bundle.items[0].snippet
    assert service.get_result(query(manager_token)).retrieval_run_id == run_id
    assert service.get_context(query(manager_token)).retrieval_run_id == run_id
    expect("RESOURCE_NOT_FOUND", lambda: service.get_run(query(member_token)))
    expect(
        "RESOURCE_NOT_FOUND",
        lambda: service.get_run(query(manager_token, uuid.uuid4())),
    )

    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='SUSPENDED' "
            "WHERE project_id=%s AND user_id=%s", (project, creator),
        )
    expect("RESOURCE_NOT_FOUND", lambda: service.get_context(query(creator_token)))
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, creator),
        )
        document = db.execute(
            "SELECT document.document_id FROM plm.rag_context_items item "
            "JOIN plm.doc_document_versions version ON "
            "version.document_version_id=item.document_version_ref "
            "JOIN plm.doc_documents document ON document.document_id=version.document_id "
            "WHERE item.retrieval_run_id=%s LIMIT 1", (run_id,),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.doc_documents SET document_state='RESTRICTED',"
            "lock_version=lock_version+1 WHERE document_id=%s", (document,),
        )
    expect(
        "RAG_RETRIEVAL_READ_UNAVAILABLE",
        lambda: service.get_result(query(manager_token)),
    )
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.doc_documents SET document_state='ACTIVE',"
            "lock_version=lock_version+1 WHERE document_id=%s", (document,),
        )
    assert service.get_context(query(manager_token)).retrieval_run_id == run_id
    assert manager != creator and member != creator
    print(
        "RAG_04_A06_P03_RETRIEVAL_READ_OWNER_PASS: creator/oversight reads, "
        "current Session/License/membership, Project isolation, current document "
        "authority and safe Result/Context projections passed on Windows 11/"
        "PostgreSQL 18.6"
    )


def main() -> None:
    create_fixture.activation_fixture.send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
