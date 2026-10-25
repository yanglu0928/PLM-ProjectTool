"""Owned Windows 11 browser/HTTP/PostgreSQL proof for Handover Action writes."""

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
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "synthetic-handover-browser-password"
USERNAME = "Synthetic Handover Manager"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py",
    "hnd_a06_source_fixture",
)
browser = load(
    ROOT / "validation/ai-05-a06-p04-windows-browser/serve.py",
    "hnd_a06_browser_fixture",
)


class Keys:
    def resolve_key(self, key_ref: str) -> bytes:
        assert type(key_ref) is str and key_ref
        return (key_ref.encode() + b"-" + b"k" * 64)[:32]


def reserve_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def install_credential(database: str, actor: uuid.UUID) -> None:
    clear = bytearray(PASSWORD.encode())
    try:
        with memoryview(clear) as view:
            hashed = browser.auth_fixture.ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    with fixture.connect(database) as db:
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
                "UPDATE plm.auth_users SET username_display=%s,username_normalized=%s,"
                "credential_version=%s,active_password_credential_id=%s,state='ENABLED' "
                "WHERE user_id=%s",
                (USERNAME, USERNAME.casefold(), version, credential, actor),
            )


def main() -> None:
    name = "hnd02a05a06_" + uuid.uuid4().hex[:8]
    credential_target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    backend = proxy = thread = listener = runtime = None
    temp_name = ""
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            database_url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            command.upgrade(create_migration_config(database_url), "head")
            command.check(create_migration_config(database_url))
            with fixture.connect(name) as db:
                actor = fixture.seed_user(db, USERNAME, "NONE", b"h" * 32)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('HNDBROWSER','hndbrowser','Synthetic Handover Browser',%s) "
                    "RETURNING project_id", (actor,),
                ).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') "
                    "RETURNING department_id", (project,),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                    "project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                    (project, actor, department),
                )
                source = fixture.seed_project_document(db, actor, project, "browser-response")
                submission, verification = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    for evidence_id, label in ((submission, "Browser submission"),
                                               (verification, "Browser verification")):
                        db.execute(
                            "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,"
                            "document_id,document_version_id,locator_type,locator_schema_version,"
                            "locator_payload,content_fingerprint,display_label,eligibility_state,"
                            "eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,"
                            "'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,%s,"
                            "'ELIGIBLE','fixture',%s)",
                            (evidence_id, project, source.document_id,
                             source.document_version_id, b"e" * 32, label, actor),
                        )
            install_credential(name, actor)
            port = reserve_port()
            origin = f"http://127.0.0.1:{port}"
            database_url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                password=uuid.uuid4().hex + uuid.uuid4().hex,
                host="127.0.0.1", port=55434, database=name,
            )
            browser.auth_fixture.write_database_url(
                database_url.render_as_string(hide_password=False), target=credential_target,
            )
            with tempfile.TemporaryDirectory(prefix="plm-hnd-a06-browser-") as directory, ExitStack() as stack:
                temp_name = directory
                config = BootstrapSettings(
                    data_root=Path(directory), trusted_origins=(origin,),
                )
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=SimpleNamespace(guard=fixture.Guard()),
                ))
                keys = Keys()
                for module in ("windows_capability", "windows_handover", "windows_handover_action_read"):
                    stack.enter_context(patch(
                        f"plm_assistant.entrypoints.{module}.WindowsSecretKeyProvider",
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
                    ("create_windows_ai_prompt_list_cursor_codec", PromptListCursorCodec(b"q" * 32)),
                    ("create_windows_ai_read_cursor_codecs", WindowsAIReadCursorCodecs(
                        AITaskListCursorCodec(b"t" * 32), AIInvocationListCursorCodec(b"i" * 32))),
                )
                for function, codec in codecs:
                    stack.enter_context(patch(prefix + function, return_value=codec))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                    return_value=object(),
                ))
                stack.enter_context(patch(
                    prefix + "create_windows_document_upload_token_issuer",
                    return_value=HmacUploadTokenIssuer(
                        provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                        key_ref="synthetic-handover-browser-upload-token",
                    ),
                ))
                logs = StringIO()
                with redirect_stdout(logs):
                    app = production.create_production_platform_write_app(
                        config, credential_target=credential_target,
                    )
                runtime = create_database_runtime(URL.create(
                    "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                    port=55434, database=name,
                ))
                listener = socket.socket()
                listener.bind(("127.0.0.1", 0)); listener.listen(128)
                backend = uvicorn.Server(uvicorn.Config(
                    app, log_level="critical", access_log=False, proxy_headers=False,
                    lifespan="on", timeout_graceful_shutdown=5,
                ))
                thread = Thread(target=lambda: backend.run(sockets=[listener]), daemon=False)
                thread.start(); deadline = monotonic() + 20
                while not backend.started:
                    if not thread.is_alive() or monotonic() > deadline:
                        raise RuntimeError("owned backend startup failed: " + logs.getvalue()[-1000:])
                    sleep(.05)
                proxy = subprocess.Popen(
                    ["node", str(ROOT / "validation/rag-04-a06-p08-windows-browser/start-preview-proxy.mjs"),
                     str(port), str(listener.getsockname()[1])],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                )
                ready = queue.Queue()
                Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
                if ready.get(timeout=20) != "OWNED_RAG_PREVIEW_READY":
                    raise RuntimeError("owned frontend startup failed: " + proxy.stderr.read())
                print(
                    f"HND_BROWSER_READY {origin}/login PROJECT={project} ACTOR={actor} "
                    f"DOCUMENT={source.document_id} VERSION={source.document_version_id} "
                    f"SUBMISSION={submission} VERIFICATION={verification} "
                    f"USERNAME='{USERNAME}' PASSWORD='{PASSWORD}'",
                    flush=True,
                )
                action = sys.stdin.readline().strip()
                if action != "VERIFY":
                    raise RuntimeError("browser validation stopped before VERIFY")
                with fixture.connect(name) as db:
                    rows = db.execute(
                        "SELECT action_state,lock_version,title,resolution_trace_ref "
                        "FROM plm.hnd_action_items ORDER BY created_at",
                    ).fetchall()
                    assert len(rows) == 2, rows
                    assert rows[0][0:2] == ("VERIFIED", 4), rows
                    assert rows[0][2] == "Browser final signed response" and rows[0][3] is None
                    assert rows[1][0:2] == ("CANCELLED", 1), rows
                    audits = db.execute(
                        "SELECT action,count(*) FROM plm.aud_events WHERE action LIKE 'HND_ACTION_%' "
                        "GROUP BY action ORDER BY action",
                    ).fetchall()
                    assert dict(audits) == {
                        "HND_ACTION_CANCELLED": 1, "HND_ACTION_CREATED": 2,
                        "HND_ACTION_PATCHED": 1, "HND_ACTION_STARTED": 1,
                        "HND_ACTION_SUBMITTED": 1, "HND_ACTION_VERIFIED": 1,
                    }, audits
                print(
                    "HND_02_A05_A06_WINDOWS_BROWSER_PASS: built Vue UI -> production "
                    "FastAPI -> PostgreSQL 18 CREATE/PATCH/START/SUBMIT/VERIFY/CANCEL "
                    "and fail-closed CLOSE display passed",
                    flush=True,
                )
        finally:
            if proxy is not None:
                if proxy.poll() is None:
                    try:
                        proxy.stdin.write("STOP\n"); proxy.stdin.flush(); proxy.wait(timeout=10)
                    except (BrokenPipeError, subprocess.TimeoutExpired):
                        proxy.kill(); proxy.wait(timeout=10)
                for stream in (proxy.stdin, proxy.stdout, proxy.stderr):
                    if stream is not None:
                        stream.close()
            if backend is not None:
                backend.should_exit = True
            if thread is not None:
                thread.join(timeout=10); assert not thread.is_alive()
            if listener is not None:
                listener.close()
            if runtime is not None:
                runtime.dispose()
            browser.auth_fixture.delete_test_credential(credential_target)
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    assert not temp_name or not Path(temp_name).exists()
    print("HND_02_A05_A06_WINDOWS_BROWSER_CLEANUP_PASS", flush=True)


if __name__ == "__main__":
    main()
