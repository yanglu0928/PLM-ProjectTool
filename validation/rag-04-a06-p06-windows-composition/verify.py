"""Windows 11/PostgreSQL 18 proof for production Retrieval composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_ai_provider_worker import (
    create_windows_ai_provider_loop,
)
from plm_assistant.entrypoints.windows_rag_retrieval import (
    RAG_RETRIEVAL_QUERY_KEY_REF,
    create_windows_rag_retrieval_api,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://plm.example.test"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker_fixture = load(
    ROOT / "validation/rag-04-a05-p02-retrieval-worker-context/verify.py",
    "rag_p06_worker_fixture",
)
create_fixture = worker_fixture.create_fixture
begin_fixture = worker_fixture.begin_fixture


class IssueAccess:
    def can_issue(self, *_args, **_kwargs): return False


class Keys:
    def __init__(self):
        self.key = b"r" * 32
        assert len(self.key) == 32
        self.refs = []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        return self.key if key_ref == RAG_RETRIEVAL_QUERY_KEY_REF else None


def execute(context, envelope, sender, adapter) -> None:
    create_fixture.execute(
        context, envelope, sender, adapter,
        query_text="legacy proof run remains isolated",
    )
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    token, csrf = b"z" * 32, create_fixture.CSRF
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
        legacy_run = db.execute(
            "SELECT retrieval_run_id FROM plm.rag_retrieval_runs WHERE "
            "project_id=%s AND retrieval_state='RUNNING' ORDER BY created_at "
            "LIMIT 1", (project,),
        ).fetchone()[0]
    guard = create_fixture.activation_fixture.quality_fixture.Guard()
    keys = Keys()
    audit = AuditService(SqlAlchemyAuditRepository())
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=IssueAccess(),
        audit=audit, idempotency=create_fixture.SqlAlchemyIdempotencyReceipts(),
    )
    origins = LoginOriginPolicy([ORIGIN])
    api = create_windows_rag_retrieval_api(
        runtime, sessions=sessions, origins=origins,
        license_guard=guard, key_resolver=keys,
    )
    app = create_app(
        rag_retrieval_router=api.router,
        rag_retrieval_cancel_router=api.cancel_router,
    )
    headers = {
        "origin": ORIGIN, "host": "plm.example.test",
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": csrf.hex(),
        "idempotency-key": str(uuid.uuid4()),
    }
    body = {
        "query": "PLM", "metadata_filter": {
            "source_type": ["PROJECT_RECORD"],
        },
        "project_index_ref": str(index_id), "global_index_ref": None,
        "retrieval_policy_ref": "fts.project.v1",
        "rerank_policy_ref": "none.v1", "top_k": 5,
    }
    with TestClient(app, base_url=ORIGIN) as client:
        cancelled_legacy = client.post(
            f"/api/v1/projects/{project}/retrieval-runs/{legacy_run}:cancel",
            headers={**headers, "if-match": '"v0"'},
            json={"reason": "remove prior isolated fixture from worker queue"},
        )
        assert cancelled_legacy.status_code == 200
        assert cancelled_legacy.json()["data"]["state"] == "CANCELLED"
        headers["idempotency-key"] = str(uuid.uuid4())
        created = client.post(
            f"/api/v1/projects/{project}/retrieval-runs",
            headers=headers, json=body,
        )
        assert created.status_code == 202, created.text
        run_id = uuid.UUID(created.json()["data"]["retrieval_run_id"])

        settings = BootstrapSettings(
            data_root=ROOT,
            rag_retrieval_policies=({
                "reference": "fts.project.v1", "scope": "PROJECT",
                "rerank_policy_ref": "none.v1",
                "context_policy_ref": "project-documents.v1",
            },),
        )
        system_actor = worker_fixture.FixedSystemActor(actor)
        worker_url = URL.create(
            "postgresql+psycopg", username=begin_fixture.USER,
            host=begin_fixture.HOST, port=begin_fixture.PORT,
            database=database,
        )
        with patch(
            "plm_assistant.entrypoints.windows_ai_provider_worker.read_database_url",
            return_value=worker_url,
        ), patch(
            "plm_assistant.entrypoints.windows_ai_provider_worker.create_windows_worker_license_services",
            return_value=SimpleNamespace(guard=guard),
        ), patch(
            "plm_assistant.entrypoints.windows_ai_provider_worker.create_windows_system_actor",
            return_value=system_actor,
        ), patch(
            "plm_assistant.entrypoints.windows_ai_provider_worker.WindowsSecretKeyProvider",
            return_value=keys,
        ):
            owned, loop = create_windows_ai_provider_loop(settings)
        assert owned is not runtime and owned.is_ready()
        result = loop.run(max_cycles=1)
        assert result.retrieval_succeeded == 1
        assert result.task_succeeded == result.probe_succeeded == 0

        status = client.get(
            f"/api/v1/projects/{project}/retrieval-runs/{run_id}",
            headers={"host": "plm.example.test", "cookie": headers["cookie"]},
        )
        result_response = client.get(
            f"/api/v1/projects/{project}/retrieval-runs/{run_id}/result",
            headers={"host": "plm.example.test", "cookie": headers["cookie"]},
        )
        context_response = client.get(
            f"/api/v1/projects/{project}/retrieval-runs/{run_id}/context",
            headers={"host": "plm.example.test", "cookie": headers["cookie"]},
        )
        assert status.status_code == result_response.status_code == 200
        assert context_response.status_code == 200
        assert status.json()["data"]["retrieval_state"] == "SUCCEEDED"
        assert len(result_response.json()["data"]["candidates"]) == 1
        assert len(context_response.json()["data"]["items"]) == 1

    with loop.quiescent():
        owned.dispose()

    assert keys.refs and set(keys.refs) == {RAG_RETRIEVAL_QUERY_KEY_REF}
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.job_jobs WHERE owner_module='rag' "
            "AND job_type='RAG_RETRIEVAL' AND state='SUCCEEDED'",
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.rag_retrieval_runs WHERE "
            "retrieval_state='CANCELLED'",
        ).fetchone()[0] == 1
    print(
        "RAG_04_A06_P06_WINDOWS_COMPOSITION_PASS: explicit Windows policy, "
        "dedicated query key, production HTTP, shared cancel Owner and fair "
        "fourth-role Retrieval cycle passed on Windows 11/PostgreSQL 18.6"
    )


def main() -> None:
    create_fixture.activation_fixture.send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
