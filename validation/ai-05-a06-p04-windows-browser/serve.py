"""Owned Windows 11 browser/PG fixture for AI Task submission validation."""

from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
import uvicorn
from alembic import command
from psycopg import sql
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
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, ADMIN = "127.0.0.1", 55434, "poc_admin"
PASSWORD = "synthetic-ai-browser-password"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


auth_fixture = load(
    ROOT / "validation/aut-03-a07-p03-production-login/verify.py", "ai05_auth_fixture",
)
document_fixture = load(
    ROOT / "validation/ai-04-a06-p03-p02-a03-document-content-pg/verify.py",
    "ai05_document_fixture",
)


class SyntheticGuard:
    def require_valid(self, *, trace_id):
        assert isinstance(trace_id, uuid.UUID)
        return object()


def connect(database: str, *, user: str = ADMIN, password: str | None = None):
    return psycopg.connect(
        host=HOST, port=PORT, user=user, password=password, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reserve_port() -> int:
    with socket.socket() as candidate:
        candidate.bind((HOST, 0))
        return candidate.getsockname()[1]


def insert_user(db, password_hash: bytes, algorithm_id: str) -> uuid.UUID:
    user = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES ('Synthetic AI Manager','synthetic ai manager') RETURNING user_id",
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
        "password_hash,algorithm_id,parameter_set) VALUES "
        "(%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
        (user, password_hash, algorithm_id,
         '{"n":131072,"r":8,"p":1,"dklen":32}'),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,"
        "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
        (credential, user),
    )
    return user


def seed(db, data_root: Path, password_hash: bytes, algorithm_id: str) -> dict[str, uuid.UUID]:
    actor = insert_user(db, password_hash, algorithm_id)
    project = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES ('AI05P04','ai05p04','Synthetic AI Browser Project',%s) RETURNING project_id",
        (actor,),
    ).fetchone()[0]
    department = db.execute(
        "INSERT INTO plm.prj_departments(project_id,department_code,"
        "department_code_normalized,name) VALUES (%s,'DEL','del','Delivery') "
        "RETURNING department_id", (project,),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
        "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, actor, department),
    )
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
        (actor,),
    ).fetchone()[0]
    provider, provider_config = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
            "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
            (provider, provider_config, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,"
            "ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,"
            "secret_ref,data_region,egress_class,can_chat,can_structured_output,"
            "can_embedding,can_rerank,created_by) VALUES (%s,%s,1,'OPENAI_COMPATIBLE',"
            "'Synthetic Local Route','endpoint.ai05.browser.v1',%s,'cn-beijing',"
            "'EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
            (provider_config, provider, secret, actor),
        )
    model = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,model_state,created_by) VALUES "
        "(%s,'synthetic-browser-chat','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.ai_model_capabilities(ai_model_id,capability_code,value_bool) "
        "VALUES (%s,'STRUCTURED_OUTPUT',true)", (model,),
    )
    prompt = uuid.uuid4()
    system_text, user_text = "System {parameters}", "Input {input}"
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,"
            "template_state,active_version_no,created_by) "
            "VALUES (%s,'GAP_ANALYSIS','ACTIVE',1,%s)", (prompt, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
            "system_template,user_template,system_template_hash,user_template_hash,"
            "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,created_by) "
            "VALUES (%s,1,%s,%s,%s,%s,'gap-output.v1',1,'no-retrieval.v1',"
            "'content-plan-chat.v1',%s)",
            (prompt, system_text, user_text,
             hashlib.sha256(system_text.encode()).hexdigest(),
             hashlib.sha256(user_text.encode()).hexdigest(), actor),
        )
    source = "合成项目需求：识别标准功能与差异项。".encode()
    source_sha = hashlib.sha256(source).digest()
    document = db.execute(
        "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
        "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
        "'Synthetic AI Source','synthetic-ai-source.txt',%s) RETURNING document_id",
        (project, actor),
    ).fetchone()[0]
    file_id = uuid.uuid4()
    db.execute(
        "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
        "storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,"
        "detected_mime,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,"
        "'synthetic-ai-source.txt',%s,'AVAILABLE',%s,%s,'text/plain',statement_timestamp())",
        (file_id, project, f"projects/{project.hex}/synthetic-ai-source.txt", actor,
         source_sha, len(source)),
    )
    version = db.execute(
        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
        "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
        "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
        "RETURNING document_version_id",
        (document, project, file_id, source_sha, len(source), Jsonb({"synthetic": True}), actor),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
        "WHERE document_id=%s", (version, version, document),
    )
    document_fixture.seed_result(
        db, LocalParseResultStorage(data_root), actor=actor, project=project,
        document=document, version=version, source_sha=source_sha, attempt=1,
        text=source.decode(), completed_at=datetime.now(timezone.utc),
    )
    return {"actor": actor, "project": project, "provider": provider,
            "model": model, "prompt": prompt, "document": document, "version": version}


def settings(data_root: Path, origin: str, prompt: uuid.UUID) -> BootstrapSettings:
    return BootstrapSettings(
        data_root=data_root, trusted_origins=(origin,),
        ai_task_policies=({
            "reference": "gap-analysis.v1", "policy_version": 1,
            "task_type": "GAP_ANALYSIS", "prompt_template_id": str(prompt),
            "purpose_ref": "project-gap-analysis.v1", "output_schema_ref": "gap-output.v1",
            "context_policy_ref": "no-retrieval.v1", "parameter_fields": ({
                "name": "language", "value_type": "STRING", "required": True,
                "max_length": 16, "minimum": None, "maximum": None,
                "allowed_values": ("zh-CN",),
            },),
        },),
        ai_egress_policies=({
            "reference": "minimum.document.text.v1", "operation_types": ("AI_TASK",),
            "data_categories": ("DOCUMENT_TEXT",), "ttl_minutes": 30,
            "max_record_count": 10, "max_payload_bytes": 131072,
            "max_input_tokens": 32768, "max_retry_attempts": 2,
            "risk_codes": ("EXTERNAL_PROVIDER", "CUSTOMER_DATA"),
            "approval_roles": ("PROJECT_MANAGER",), "data_regions": ("cn-beijing",),
        },),
        ai_execution_policies=({
            "reference": "endpoint.ai05.browser.v1", "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://provider.synthetic.invalid/v1/chat/completions",
            "data_region": "cn-beijing", "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
            "allowed_model_keys": ("synthetic-browser-chat",), "max_response_bytes": 1000000,
            "connect_timeout_seconds": 3, "read_timeout_seconds": 10,
            "total_timeout_seconds": 20,
        },),
    )


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    database = role = "ai05a06p04_" + suffix
    role_password = uuid.uuid4().hex + uuid.uuid4().hex
    credential_target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    port = reserve_port()
    origin = f"http://127.0.0.1:{port}"
    backend = proxy = thread = listener = None
    logs = StringIO()
    temp_name = ""
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
            sql.Identifier(role), sql.Literal(role_password)))
        try:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(database), sql.Identifier(role)))
            try:
                url = URL.create("postgresql+psycopg", username=role, password=role_password,
                                 host=HOST, port=PORT, database=database)
                with connect(database) as db:
                    db.execute("CREATE EXTENSION IF NOT EXISTS vector")
                command.upgrade(create_migration_config(url), "head")
                clear = bytearray(PASSWORD.encode())
                try:
                    with memoryview(clear) as view:
                        hashed = auth_fixture.ScryptPasswordHasher().hash_password(view)
                finally:
                    clear[:] = b"\x00" * len(clear)
                auth_fixture.write_database_url(
                    url.render_as_string(hide_password=False), target=credential_target,
                )
                try:
                    with tempfile.TemporaryDirectory(prefix="plm-ai05-browser-") as directory, ExitStack() as stack:
                        temp_name = directory
                        root = Path(directory)
                        with connect(database) as db:
                            ids = seed(db, root, hashed.password_hash, hashed.algorithm_id)
                        config = settings(root, origin, ids["prompt"])
                        prefix = "plm_assistant.entrypoints.production_login."
                        stack.enter_context(patch(
                            "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                            return_value=SimpleNamespace(guard=SyntheticGuard()),
                        ))
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
                                key_ref="synthetic-ai-browser-upload-token",
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
                        listener = socket.socket()
                        listener.bind((HOST, 0))
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
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        ready = queue.Queue()
                        Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
                        if ready.get(timeout=20) != "OWNED_AI_PREVIEW_READY":
                            raise RuntimeError("owned frontend startup failed: " + proxy.stderr.read())
                        print(
                            f"AI_TASK_BROWSER_READY {origin}/login PROJECT={ids['project']} "
                            f"DOCUMENT={ids['document']} VERSION={ids['version']} "
                            f"USERNAME='Synthetic AI Manager' PASSWORD='{PASSWORD}'",
                            flush=True,
                        )
                        action = queue.Queue()
                        Thread(target=lambda: action.put(sys.stdin.readline().strip()), daemon=True).start()
                        assert action.get(timeout=3600) == "VERIFY", "browser verification not completed"
                        with connect(database) as db:
                            counts = db.execute(
                                "SELECT (SELECT count(*) FROM plm.ai_egress_previews),"
                                "(SELECT count(*) FROM plm.ai_egress_authorizations),"
                                "(SELECT count(*) FROM plm.ai_tasks),"
                                "(SELECT count(*) FROM plm.job_jobs WHERE job_type='AI_TASK_EXECUTE'),"
                                "(SELECT count(*) FROM plm.ai_invocations)"
                            ).fetchone()
                            assert counts == (1, 1, 1, 1, 0), counts
                            states = db.execute(
                                "SELECT a.authorization_state,t.task_state,j.state "
                                "FROM plm.ai_egress_authorizations a "
                                "JOIN plm.ai_egress_authorization_snapshots s ON s.authorization_ref=a.authorization_id "
                                "JOIN plm.ai_tasks t ON t.ai_task_id=s.ai_task_id "
                                "JOIN plm.job_jobs j ON j.job_id=t.job_ref"
                            ).fetchone()
                            assert states == ("AUTHORIZED", "QUEUED", "PENDING"), states
                        print(
                            "AI_05_A06_P04_WINDOWS_BROWSER_PASS: built Vue UI -> production FastAPI "
                            "-> PostgreSQL 18 Preview/Authorize/Task closed with one queued AI Task, "
                            "one pending Job and zero provider I/O",
                            flush=True,
                        )
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
                        proxy.stdin.close()
                        proxy.stdout.close()
                        proxy.stderr.close()
                    if backend is not None:
                        backend.should_exit = True
                    if thread is not None:
                        thread.join(timeout=10)
                        assert not thread.is_alive(), "owned backend did not stop"
                    if listener is not None:
                        listener.close()
                    auth_fixture.delete_test_credential(credential_target)
            finally:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))
        finally:
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        assert admin.execute(
            "SELECT count(*) FROM pg_database WHERE datname=%s", (database,),
        ).fetchone()[0] == 0
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    pointer = ctypes.c_void_p()
    found = library.CredReadW(credential_target, 1, 0, ctypes.byref(pointer))
    if found:
        library.CredFree(pointer)
    assert not found and ctypes.get_last_error() == 1168
    assert temp_name and not Path(temp_name).exists()
    print("AI_05_A06_P04_WINDOWS_BROWSER_CLEANUP_PASS", flush=True)


if __name__ == "__main__":
    main()
