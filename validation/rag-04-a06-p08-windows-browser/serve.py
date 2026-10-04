"""Owned Windows 11 browser/HTTP/Worker/PostgreSQL Retrieval validation."""

from __future__ import annotations

import importlib.util
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch

import uvicorn
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.windows_ai_read_cursor import WindowsAIReadCursorCodecs
from plm_assistant.modules.ai.api.invocation_list_cursor import AIInvocationListCursorCodec
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "synthetic-rag-browser-password"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p06 = load(
    ROOT / "validation/rag-04-a06-p06-windows-composition/verify.py",
    "rag_p08_p06_fixture",
)
browser_fixture = load(
    ROOT / "validation/ai-05-a06-p04-windows-browser/serve.py",
    "rag_p08_browser_fixture",
)
begin_fixture = p06.begin_fixture


def reserve_port() -> int:
    with socket.socket() as candidate:
        candidate.bind((begin_fixture.HOST, 0))
        return candidate.getsockname()[1]


def install_browser_credential(database: str, actor: uuid.UUID) -> None:
    clear = bytearray(PASSWORD.encode())
    try:
        with memoryview(clear) as view:
            hashed = browser_fixture.auth_fixture.ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    with begin_fixture.connect(database) as db:
        with db.transaction():
            version = db.execute(
                "SELECT credential_version+1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",
                (actor,),
            ).fetchone()[0]
            credential = db.execute(
                "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
                "password_hash,algorithm_id,parameter_set) VALUES (%s,%s,%s,%s,%s) "
                "RETURNING password_credential_id",
                (actor, version, hashed.password_hash, hashed.algorithm_id,
                 Jsonb({"n": 131072, "r": 8, "p": 1, "dklen": 32})),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.auth_users SET username_display='Synthetic Retrieval Manager',"
                "username_normalized='synthetic retrieval manager',credential_version=%s,"
                "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                (version, credential, actor),
            )


def settings(root: Path, origin: str) -> BootstrapSettings:
    return BootstrapSettings(
        data_root=root, trusted_origins=(origin,),
        rag_retrieval_policies=({
            "reference": "fts.project.v1", "scope": "PROJECT",
            "rerank_policy_ref": "none.v1",
            "context_policy_ref": "project-documents.v1",
        },),
    )


def execute(context, envelope, sender, adapter) -> None:
    p06.create_fixture.execute(
        context, envelope, sender, adapter,
        query_text="legacy browser fixture is cancelled before UI validation",
    )
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
        legacy_run = db.execute(
            "SELECT retrieval_run_id FROM plm.rag_retrieval_runs WHERE project_id=%s "
            "AND retrieval_state='RUNNING' ORDER BY created_at LIMIT 1", (project,),
        ).fetchone()[0]

    port = reserve_port()
    origin = f"http://127.0.0.1:{port}"
    credential_target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    database_url = URL.create(
        "postgresql+psycopg", username=begin_fixture.USER,
        password=uuid.uuid4().hex + uuid.uuid4().hex,
        host=begin_fixture.HOST, port=begin_fixture.PORT, database=database,
    )
    backend = proxy = thread = listener = None
    keys = p06.Keys()
    logs = StringIO()
    temp_name = ""
    browser_fixture.auth_fixture.write_database_url(
        database_url.render_as_string(hide_password=False), target=credential_target,
    )
    try:
        with tempfile.TemporaryDirectory(prefix="plm-rag-p08-browser-") as directory, ExitStack() as stack:
            temp_name = directory
            config = settings(Path(directory), origin)
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                return_value=SimpleNamespace(guard=p06.create_fixture.activation_fixture.quality_fixture.Guard()),
            ))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_rag_retrieval.WindowsSecretKeyProvider",
                return_value=keys,
            ))
            prefix = "plm_assistant.entrypoints.production_login."
            codecs = (
                ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"s" * 32)),
                ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                ("create_windows_ai_provider_list_cursor_codec", ProviderListCursorCodec(b"r" * 32)),
                ("create_windows_ai_model_list_cursor_codec", ModelListCursorCodec(b"o" * 32)),
                ("create_windows_ai_prompt_list_cursor_codec", PromptListCursorCodec(b"m" * 32)),
                ("create_windows_ai_read_cursor_codecs", WindowsAIReadCursorCodecs(
                    AITaskListCursorCodec(b"t" * 32), AIInvocationListCursorCodec(b"i" * 32))),
            )
            for name, codec in codecs:
                stack.enter_context(patch(prefix + name, return_value=codec))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                return_value=object(),
            ))
            stack.enter_context(patch(
                prefix + "create_windows_document_upload_token_issuer",
                return_value=HmacUploadTokenIssuer(
                    provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                    key_ref="synthetic-rag-browser-upload-token",
                ),
            ))
            try:
                with redirect_stdout(logs):
                    app = production.create_production_platform_write_app(
                        config, credential_target=credential_target,
                    )
            except Exception:
                if logs.getvalue():
                    print(logs.getvalue(), file=sys.stderr, end="")
                raise

            token, csrf = b"z" * 32, p06.create_fixture.CSRF
            with TestClient(app, base_url=origin) as client:
                response = client.post(
                    f"/api/v1/projects/{project}/retrieval-runs/{legacy_run}:cancel",
                    headers={"origin": origin, "cookie": "plm_session=" + token.hex(),
                             "x-csrf-token": csrf.hex(), "if-match": '"v0"',
                             "idempotency-key": str(uuid.uuid4())},
                    json={"reason": "close legacy validation fixture"},
                )
                assert response.status_code == 200, response.text
                assert response.json()["data"]["state"] == "CANCELLED"
            install_browser_credential(database, actor)

            listener = socket.socket()
            listener.bind((begin_fixture.HOST, 0))
            listener.listen(128)
            backend = uvicorn.Server(uvicorn.Config(
                app, log_level="critical", access_log=False, proxy_headers=False,
                lifespan="on", timeout_graceful_shutdown=5,
            ))
            thread = Thread(target=lambda: backend.run(sockets=[listener]), daemon=False)
            thread.start()
            deadline = monotonic() + 15
            while not backend.started:
                if not thread.is_alive() or monotonic() > deadline:
                    raise RuntimeError("owned backend startup failed: " + logs.getvalue()[-1000:])
                sleep(.05)
            proxy = subprocess.Popen(
                ["node", str(Path(__file__).with_name("start-preview-proxy.mjs")),
                 str(port), str(listener.getsockname()[1])],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            ready = queue.Queue()
            Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
            if ready.get(timeout=20) != "OWNED_RAG_PREVIEW_READY":
                raise RuntimeError("owned frontend startup failed: " + proxy.stderr.read())
            print(
                f"RAG_BROWSER_READY {origin}/login PROJECT={project} INDEX={index_id} "
                f"USERNAME='Synthetic Retrieval Manager' PASSWORD='{PASSWORD}'",
                flush=True,
            )

            while True:
                action = sys.stdin.readline().strip()
                if action == "WORK":
                    guard = p06.create_fixture.activation_fixture.quality_fixture.Guard()
                    system_actor = p06.worker_fixture.FixedSystemActor(actor)
                    with patch(
                        "plm_assistant.entrypoints.windows_ai_provider_worker.read_database_url",
                        return_value=database_url,
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
                        owned, loop = p06.create_windows_ai_provider_loop(config)
                    try:
                        result = loop.run(max_cycles=1)
                        assert result.retrieval_succeeded == 1, result
                        assert result.task_succeeded == result.probe_succeeded == 0
                    finally:
                        with loop.quiescent():
                            owned.dispose()
                    print("RAG_BROWSER_WORKER_DONE", flush=True)
                elif action == "VERIFY":
                    with begin_fixture.connect(database) as db:
                        states = db.execute(
                            "SELECT retrieval_state,count(*) FROM plm.rag_retrieval_runs "
                            "GROUP BY retrieval_state ORDER BY retrieval_state",
                        ).fetchall()
                        assert dict(states) == {"CANCELLED": 2, "SUCCEEDED": 1}, states
                        counts = db.execute(
                            "SELECT (SELECT count(*) FROM plm.rag_retrieval_candidates),"
                            "(SELECT count(*) FROM plm.rag_context_bundles),"
                            "(SELECT count(*) FROM plm.rag_context_items),"
                            "(SELECT count(*) FROM plm.rag_retrieval_query_contents q JOIN "
                            "plm.rag_retrieval_runs r USING(retrieval_run_id) WHERE r.retrieval_state='SUCCEEDED')",
                        ).fetchone()
                        assert counts == (1, 1, 1, 1), counts
                    print(
                        "RAG_04_A06_P08_WINDOWS_BROWSER_PASS: built Vue UI -> production "
                        "FastAPI -> fourth Worker -> Result/Context/Cancel -> PostgreSQL 18 passed",
                        flush=True,
                    )
                    break
                elif action == "STOP" or not action:
                    raise RuntimeError("browser validation stopped before VERIFY")
                else:
                    raise RuntimeError("unknown validation action")
    finally:
        if proxy is not None:
            if proxy.poll() is None:
                try:
                    proxy.stdin.write("STOP\n")
                    proxy.stdin.flush()
                    proxy.wait(timeout=10)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    proxy.kill()
                    proxy.wait(timeout=10)
            for stream in (proxy.stdin, proxy.stdout, proxy.stderr):
                if stream is not None:
                    stream.close()
        if backend is not None:
            backend.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
            assert not thread.is_alive(), "owned backend did not stop"
        if listener is not None:
            listener.close()
        browser_fixture.auth_fixture.delete_test_credential(credential_target)
    assert not Path(temp_name).exists()


def main() -> None:
    p06.create_fixture.activation_fixture.send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )
    print("RAG_04_A06_P08_WINDOWS_BROWSER_CLEANUP_PASS", flush=True)


if __name__ == "__main__":
    main()
